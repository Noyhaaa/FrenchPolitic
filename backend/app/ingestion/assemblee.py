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
    to_int,
    truncate,
)
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
    def __init__(self, legislature: int = 17, timeout: float = 120.0) -> None:
        self.legislature = legislature
        self._timeout = timeout

    async def _download_zip(self, url: str) -> zipfile.ZipFile:
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as c:
            resp = await c.get(url)
            resp.raise_for_status()
            return zipfile.ZipFile(io.BytesIO(resp.content))

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
    raw: dict, resolver: GroupResolver, acteurs: dict[str, str] | None = None
) -> ScrutinParse:
    """Convertit un scrutin open data en `ScrutinParse` (fonction pure).

    `acteurs` (annuaire PA… → nom) active l'extraction du vote nominatif.
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
    # Titre du dossier (souvent plus clair) ; sinon on retombe sur l'objet.
    dossier_titre = dossier_titre_raw or objet.get("libelle") or objet_libelle
    # Pas de dossierRef → le scrutin est son propre dossier (singleton).
    dossier_id = dossier_ref or s["uid"]

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
