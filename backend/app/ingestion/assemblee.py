"""Ingestion open data Assemblée nationale (§5.1).

Sources (licence ouverte, 17e législature) :
- Scrutins publics : archive ZIP de fichiers JSON (un par scrutin).
- Organes (AMO) : pour résoudre les groupes politiques par nom.

`parse_scrutin` est une fonction pure (dict brut → `ScrutinParse`), testable sans
réseau. Elle produit un scrutin au niveau du vote **plus** les métadonnées du
dossier auquel il se rattache (le regroupement en `Dossier` a lieu dans `sync`).
Le résumé IA n'étant pas encore généré, il est laissé vide au niveau du dossier
avec une confiance « faible » (règle d'or §2.5 : jamais de comblement).
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass

import httpx

from app.ingestion.normalize import (
    as_list,
    guess_theme,
    map_position,
    map_statut,
    texte_de_rattachement,
    to_int,
    truncate,
)
from app.utils.text import fold
from app.ingestion.dossiers_legislatifs import Reconciliation
from app.ingestion.organes import GroupResolver
from app.schemas import (
    PositionGroupe,
    ResultatGlobal,
    Scrutin,
    SourceOfficielle,
)

SCRUTINS_URL = (
    "https://data.assemblee-nationale.fr/static/openData/repository/"
    "{leg}/loi/scrutins/Scrutins.json.zip"
)
ORGANES_URL = (
    "https://data.assemblee-nationale.fr/static/openData/repository/"
    "{leg}/amo/deputes_actifs_mandats_actifs_organes/"
    "AMO10_deputes_actifs_mandats_actifs_organes.json.zip"
)
DOSSIERS_URL = (
    "https://data.assemblee-nationale.fr/static/openData/repository/"
    "{leg}/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip"
)
# Comptes rendus des débats en séance (« SyceronBrut ») : un XML par séance.
# Fournit les explications de vote par groupe (§ « principal désaccord »).
DEBATS_URL = (
    "https://data.assemblee-nationale.fr/static/openData/repository/"
    "{leg}/vp/syceronbrut/syseron.xml.zip"
)


@dataclass
class ScrutinParse:
    """Résultat du parsing d'un scrutin : le vote + son rattachement au dossier."""

    scrutin: Scrutin
    dossier_id: str
    dossier_titre: str
    dossier_ref: str | None
    theme: str
    legislature: str
    numero: str


class AssembleeOpenDataClient:
    # Les archives volumineuses (scrutins, débats ~55 Mo) subissent parfois une
    # coupure serveur en cours de transfert (« peer closed connection ») ou un
    # ZIP tronqué. On réessaie du début plutôt que de laisser tomber tout le run.
    _ZIP_TENTATIVES = 4
    _ZIP_ATTENTES_S = (3.0, 8.0, 20.0)

    def __init__(self, legislature: int = 17, timeout: float = 120.0) -> None:
        self.legislature = legislature
        self._timeout = timeout

    async def _download_zip(self, url: str) -> zipfile.ZipFile:
        """Télécharge un ZIP avec retries sur coupure réseau / archive tronquée.

        Relève la dernière exception si toutes les tentatives échouent (à
        l'appelant de décider si c'est fatal — les débats, best-effort, ne le
        sont pas)."""
        derniere: Exception | None = None
        for tentative in range(self._ZIP_TENTATIVES):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout, follow_redirects=True
                ) as c:
                    resp = await c.get(url)
                    resp.raise_for_status()
                    return zipfile.ZipFile(io.BytesIO(resp.content))
            except (httpx.HTTPError, zipfile.BadZipFile) as exc:
                derniere = exc
                if tentative < len(self._ZIP_ATTENTES_S):
                    await asyncio.sleep(self._ZIP_ATTENTES_S[tentative])
        assert derniere is not None
        raise derniere

    async def download_scrutins(self, limit: int | None = None) -> list[dict]:
        """Télécharge l'archive des scrutins et renvoie les JSON bruts."""
        zf = await self._download_zip(SCRUTINS_URL.format(leg=self.legislature))
        names = [n for n in zf.namelist() if n.endswith(".json")]
        names.sort()
        if limit is not None:
            names = names[-limit:]  # les plus récents (tri par numéro croissant)
        out: list[dict] = []
        for name in names:
            with zf.open(name) as f:
                out.append(json.load(f))
        return out

    async def download_dossiers(self) -> list[dict]:
        """Télécharge l'archive des dossiers législatifs et renvoie les JSON des
        **documents** (titre + dossierRef, pour la réconciliation)."""
        zf = await self._download_zip(DOSSIERS_URL.format(leg=self.legislature))
        out: list[dict] = []
        for name in zf.namelist():
            if name.endswith(".json") and "/document/" in name:
                with zf.open(name) as f:
                    out.append(json.load(f))
        return out

    async def download_texte_pdf(self, url_pdf: str) -> bytes | None:
        """Télécharge le PDF d'un texte (exposé des motifs). None si absent ou
        non-PDF — l'enrichissement est best-effort (§2.5 : on n'attache rien en
        cas d'échec, pas de comblement)."""
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            ) as c:
                resp = await c.get(url_pdf)
            if resp.status_code != 200:
                return None
            if "pdf" not in resp.headers.get("content-type", "").lower():
                return None
            return resp.content
        except httpx.HTTPError:
            return None

    async def download_debats(self) -> list[str]:
        """Télécharge l'archive des comptes rendus de séance (XML bruts).

        Renvoie le contenu XML de chaque compte rendu (un par séance). Best-effort
        au niveau de l'appelant : l'archive est volumineuse (~55 Mo) mais ne sert
        qu'à enrichir les dossiers d'un « principal désaccord » (§2.5)."""
        zf = await self._download_zip(DEBATS_URL.format(leg=self.legislature))
        out: list[str] = []
        for name in zf.namelist():
            if name.endswith(".xml"):
                with zf.open(name) as f:
                    out.append(f.read().decode("utf-8"))
        return out

    async def download_amo(self) -> tuple[list[dict], list[dict]]:
        """Télécharge l'archive AMO une seule fois : (organes, acteurs).

        Les organes donnent les groupes politiques ; les acteurs, l'annuaire
        des députés pour le vote nominatif (§5.2).
        """
        zf = await self._download_zip(ORGANES_URL.format(leg=self.legislature))
        organes: list[dict] = []
        acteurs: list[dict] = []
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            if "/organe/" in name:
                with zf.open(name) as f:
                    organes.append(json.load(f))
            elif "/acteur/" in name:
                with zf.open(name) as f:
                    acteurs.append(json.load(f))
        return organes, acteurs


def scrutin_source(legislature: str, numero: str) -> SourceOfficielle:
    return SourceOfficielle(
        type="scrutin",
        libelle="Scrutin",
        url=f"https://www.assemblee-nationale.fr/dyn/{legislature}/scrutins/{numero}",
    )


def dossier_source(legislature: str, dossier_ref: str) -> SourceOfficielle:
    return SourceOfficielle(
        type="texte",
        libelle="Dossier législatif",
        url=f"https://www.assemblee-nationale.fr/dyn/{legislature}/dossiers/{dossier_ref}",
    )


def _noms_votants(
    bloc: object, acteurs: dict[str, str] | None
) -> list[str] | None:
    """Noms des votants d'un bloc `decompteNominatif` (pours/contres/abstentions).

    None si l'annuaire ou le bloc manque (§2.5 : le détail est alors masqué,
    jamais inventé). Acteur inconnu de l'annuaire → on garde sa référence PA…
    (factuel) plutôt que d'inventer un nom.
    """
    if acteurs is None or not isinstance(bloc, dict):
        return None
    noms: list[str] = []
    for votant in as_list(bloc.get("votant")):
        if not isinstance(votant, dict):
            continue
        ref = votant.get("acteurRef") or ""
        if ref:
            noms.append(acteurs.get(ref, ref))
    return noms or None


def parse_scrutin(
    raw: dict,
    resolver: GroupResolver,
    acteurs: dict[str, str] | None = None,
    reconciliation: Reconciliation | None = None,
) -> ScrutinParse:
    """Convertit un scrutin open data en `ScrutinParse` (fonction pure).

    `acteurs` (annuaire PA… → nom) active l'extraction du vote nominatif.
    `reconciliation` (titre ↔ dossierRef) permet, quand le scrutin n'a pas de
    dossierRef, de retrouver son vrai dossier via le titre cité dans l'objet.
    """
    s = raw["scrutin"]
    legislature = str(s.get("legislature", ""))
    numero = str(s.get("numero", ""))

    objet = s.get("objet") or {}
    dossier = objet.get("dossierLegislatif") or {}
    dossier_titre_raw = dossier.get("libelle")
    dossier_ref = dossier.get("dossierRef")

    # Objet du vote (« l'amendement n° 80… », « l'ensemble du texte »…).
    objet_libelle = s.get("titre") or objet.get("libelle") or ""
    # Rattachement au dossier, par ordre de fiabilité :
    # 1) dossierRef officiel ;
    # 2) sinon, le texte de loi cité dans l'objet même du vote (« … de la
    #    proposition de loi visant à… ») — tous les votes d'un même texte
    #    (articles, amendements, motions liées) se regroupent ainsi sous un
    #    dossier reconstitué, au lieu de polluer le fil en singletons ;
    # 3) sinon (motion de censure, déclaration…), le scrutin est son propre
    #    dossier : c'est un événement autonome, légitime dans le fil.
    reco = reconciliation

    if dossier_ref:
        dossier_id = dossier_ref
        dossier_titre = dossier_titre_raw or objet.get("libelle") or objet_libelle
    else:
        rattachement = texte_de_rattachement(objet_libelle)
        ref_retrouve = reco.ref_pour_titre(rattachement) if reco else None
        if ref_retrouve:
            # Réconciliation : le titre cité correspond exactement à un dossier
            # officiel → le vote rejoint son vrai dossier (et son lien officiel).
            # On garde notre libellé (bien casé), pas celui de l'archive.
            dossier_ref = ref_retrouve
            dossier_id = ref_retrouve
            dossier_titre = rattachement or objet_libelle
        elif rattachement:
            # Id stable entre runs : dérivé du titre plié (insensible aux
            # accents / à la casse) — l'upsert fusionne les runs successifs.
            cle = fold(rattachement)
            dossier_id = "TXT-" + hashlib.sha1(cle.encode()).hexdigest()[:16]
            dossier_titre = rattachement
        else:
            dossier_id = s["uid"]
            dossier_titre = dossier_titre_raw or objet.get("libelle") or objet_libelle

    decompte = (s.get("syntheseVote") or {}).get("decompte") or {}
    resultat = ResultatGlobal(
        pour=to_int(decompte.get("pour")),
        contre=to_int(decompte.get("contre")),
        abstention=to_int(decompte.get("abstentions")),
        non_votants=to_int(decompte.get("nonVotants")),
    )

    positions: list[PositionGroupe] = []
    ventilation = (s.get("ventilationVotes") or {}).get("organe") or {}
    for g in as_list((ventilation.get("groupes") or {}).get("groupe")):
        ref = g.get("organeRef", "")
        info = resolver.resolve(ref)
        vote = g.get("vote") or {}
        dv = vote.get("decompteVoix") or {}
        dn = vote.get("decompteNominatif") or {}
        positions.append(
            PositionGroupe(
                groupe_id=info.id,
                groupe_nom=info.nom,
                couleur=info.couleur,
                position_majoritaire=map_position(vote.get("positionMajoritaire")),
                pour=to_int(dv.get("pour")),
                contre=to_int(dv.get("contre")),
                abstention=to_int(dv.get("abstentions")),
                cohesion=None,
                noms_pour=_noms_votants(dn.get("pours"), acteurs),
                noms_contre=_noms_votants(dn.get("contres"), acteurs),
                noms_abstention=_noms_votants(dn.get("abstentions"), acteurs),
            )
        )

    scrutin = Scrutin(
        id=s["uid"],
        dossier_id=dossier_id,
        date=str(s.get("dateScrutin", "")),
        objet=truncate(objet_libelle or dossier_titre, 120),
        statut=map_statut((s.get("sort") or {}).get("code", "")),
        scrutin_public=True,  # l'archive ne contient que des scrutins publics (§5.2)
        resultat=resultat,
        positions_groupes=positions,
        sources=[scrutin_source(legislature, numero)],
    )

    return ScrutinParse(
        scrutin=scrutin,
        dossier_id=dossier_id,
        dossier_titre=truncate(dossier_titre, 160),
        dossier_ref=dossier_ref,
        theme=guess_theme(dossier_titre, objet_libelle),
        legislature=legislature,
        numero=numero,
    )
