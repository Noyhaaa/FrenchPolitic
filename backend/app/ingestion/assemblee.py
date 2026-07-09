"""Ingestion open data Assemblée nationale (§5.1).

Sources (licence ouverte, 17e législature) :
- Scrutins publics : archive ZIP de fichiers JSON (un par scrutin).
- Organes (AMO) : pour résoudre les groupes politiques par nom.

`parse_scrutin` est une fonction pure (dict brut → `Scrutin`), testable sans
réseau. Le résumé IA n'étant pas encore généré, il est laissé vide avec une
confiance « faible » et les champs non documentés listés (règle d'or §2.5 :
jamais de comblement).
"""
from __future__ import annotations

import io
import json
import zipfile

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
    ResumeScrutin,
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

    async def download_organes(self) -> list[dict]:
        """Télécharge l'archive AMO et renvoie les JSON d'organes bruts."""
        zf = await self._download_zip(ORGANES_URL.format(leg=self.legislature))
        out: list[dict] = []
        for name in zf.namelist():
            if "/organe/" in name and name.endswith(".json"):
                with zf.open(name) as f:
                    out.append(json.load(f))
        return out


def _sources(legislature: str, numero: str, dossier_ref: str | None) -> list[SourceOfficielle]:
    sources = [
        SourceOfficielle(
            type="scrutin",
            libelle="Scrutin",
            url=f"https://www.assemblee-nationale.fr/dyn/{legislature}/scrutins/{numero}",
        )
    ]
    if dossier_ref:
        sources.append(
            SourceOfficielle(
                type="texte",
                libelle="Dossier législatif",
                url=f"https://www.assemblee-nationale.fr/dyn/{legislature}/dossiers/{dossier_ref}",
            )
        )
    return sources


def parse_scrutin(raw: dict, resolver: GroupResolver) -> Scrutin:
    """Convertit un scrutin open data en `Scrutin` (fonction pure)."""
    s = raw["scrutin"]
    legislature = str(s.get("legislature", ""))
    numero = str(s.get("numero", ""))

    objet = s.get("objet") or {}
    dossier = objet.get("dossierLegislatif") or {}
    dossier_titre = dossier.get("libelle")
    dossier_ref = dossier.get("dossierRef")

    titre_officiel = s.get("titre") or objet.get("libelle") or ""
    # En attendant la reformulation IA, on prend le libellé du dossier (souvent
    # plus clair que « l'amendement n° 80… »), sinon le titre officiel.
    titre_clair = truncate(dossier_titre or objet.get("libelle") or titre_officiel, 90)
    accroche = truncate(objet.get("libelle") or dossier_titre or titre_officiel, 160)

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
            )
        )

    resume = ResumeScrutin(
        titre_clair=titre_clair,
        resume=[],
        public_concerne=[],
        confiance="faible",
        relu_par_humain=False,
        # Ces champs viendront de la génération IA (Phase 2) — non comblés ici.
        champs_non_documentes=["resume", "contexte", "objectif", "public_concerne"],
    )

    return Scrutin(
        id=s["uid"],
        date=str(s.get("dateScrutin", "")),
        titre_officiel=titre_officiel,
        titre_clair=titre_clair,
        accroche=accroche,
        statut=map_statut((s.get("sort") or {}).get("code", "")),
        phase=None,
        theme=guess_theme(titre_clair, accroche, dossier_titre or ""),
        scrutin_public=True,  # l'archive ne contient que des scrutins publics (§5.2)
        temps_lecture_sec=30,
        resultat=resultat,
        positions_groupes=positions,
        amendements=[],  # nécessite les données d'amendements du dossier (Phase 2)
        sources=_sources(legislature, numero, dossier_ref),
        resume=resume,
    )
