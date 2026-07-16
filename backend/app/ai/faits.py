"""Faits d'un dossier, extraits des scrutins déjà en base (§4.1).

Le résumé neutre de Phase 2 se construit **uniquement** à partir de ces faits
officiels (aucune source externe, aucune invention, §2.5). On isole ici la
lecture des scrutins pour que le RAG et le gabarit consomment une structure
stable et testable, sans dépendre de la forme brute de l'open data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingestion.normalize import nature_texte
from app.schemas import ResultatGlobal, Scrutin
from app.utils.text import fold

# Nom de groupe non résolu (identifiant d'organe brut « PO847173 »).
_REF_BRUTE = re.compile(r"^PO\d+$")

_MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def date_fr(iso: str) -> str:
    """« 2026-07-16… » → « 16 juillet 2026 ». Chaîne d'origine si non datable."""
    partie = iso[:10]
    try:
        annee, mois, jour = (int(x) for x in partie.split("-"))
        return f"{jour} {_MOIS_FR[mois - 1]} {annee}"
    except (ValueError, IndexError):
        return iso


@dataclass
class FaitsDossier:
    """Vue factuelle d'un dossier pour la génération du résumé."""

    titre_clair: str
    titre_officiel: str
    theme: str
    nature: str | None
    # Votes sur le texte (ensemble, articles, motions) — pas les amendements.
    nb_votes_texte: int
    date_premier: str | None
    date_dernier: str | None
    # Le vote « décisif » (sur l'ensemble si présent, sinon le plus récent).
    decisif: Scrutin | None
    # Décomptes d'amendements mis aux voix.
    nb_amendements: int
    nb_amendements_adoptes: int
    nb_amendements_rejetes: int

    @property
    def resultat_reference(self) -> ResultatGlobal:
        """Résultat servant au garde-fou des chiffres (§4.4) : celui du vote
        décisif, ou un décompte nul à défaut."""
        if self.decisif is not None:
            return self.decisif.resultat
        return ResultatGlobal(pour=0, contre=0, abstention=0, non_votants=0)

    @property
    def groupes_pour(self) -> list[str]:
        return self._groupes("pour")

    @property
    def groupes_contre(self) -> list[str]:
        return self._groupes("contre")

    def _groupes(self, position: str) -> list[str]:
        if self.decisif is None:
            return []
        return [
            g.groupe_nom
            for g in self.decisif.positions_groupes
            if g.position_majoritaire.value == position
            # Écarte un groupe dont le nom n'a pas pu être résolu (ref brute
            # « PO… ») : on ne cite pas un identifiant technique (§2.5).
            and not _REF_BRUTE.match(g.groupe_nom)
        ]


def _vote_decisif(votes_texte: list[Scrutin]) -> Scrutin | None:
    """Le vote sur l'ensemble si on le repère, sinon le plus récent des votes
    sur le texte (liste déjà triée du plus récent au plus ancien)."""
    for s in votes_texte:
        if "ensemble" in fold(s.objet):
            return s
    return votes_texte[0] if votes_texte else None


def construire_faits(
    titre_clair: str,
    titre_officiel: str,
    theme: str,
    votes_texte: list[Scrutin],
    votes_amendement: list[Scrutin],
) -> FaitsDossier:
    dates = sorted(s.date for s in votes_texte if s.date)
    return FaitsDossier(
        titre_clair=titre_clair,
        titre_officiel=titre_officiel,
        theme=theme,
        nature=nature_texte(titre_officiel) or nature_texte(titre_clair),
        nb_votes_texte=len(votes_texte),
        date_premier=dates[0] if dates else None,
        date_dernier=dates[-1] if dates else None,
        decisif=_vote_decisif(votes_texte),
        nb_amendements=len(votes_amendement),
        nb_amendements_adoptes=sum(
            1 for s in votes_amendement if s.statut.value == "adopte"
        ),
        nb_amendements_rejetes=sum(
            1 for s in votes_amendement if s.statut.value == "rejete"
        ),
    )
