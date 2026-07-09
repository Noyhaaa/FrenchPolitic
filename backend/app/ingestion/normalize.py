"""Helpers de normalisation open data → schéma `Scrutin`."""
from __future__ import annotations

from app.domain.enums import PositionVote
from app.utils.text import fold

# Devine le thème à partir de mots-clés du titre (heuristique, pas d'opinion).
# L'open data ne fournit pas de thème ; à terme, un classifieur plus fin.
_THEME_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Logement", ("logement", "loyer", "habitat", "bail", "locati", "hlm")),
    ("Santé", ("sante", "soin", "hopital", "medecin", "medical", "hospital")),
    ("Fiscalité", ("impot", "fiscal", "taxe", "budget", "finances", "tva")),
    ("Énergie", ("energie", "electricite", "gaz", "nucleaire", "carburant", "petrol")),
    ("Éducation", ("ecole", "education", "enseign", "universit", "scolaire", "eleve", "etudiant")),
    ("Environnement", ("environnement", "climat", "ecolog", "pollution", "biodiversite", "pesticide")),
    ("Justice", ("justice", "penal", "peine", "tribunal", "delit", "criminel", "prison", "victim")),
    ("Travail", ("travail", "emploi", "salari", "chomage", "retraite", "syndic")),
]


def guess_theme(*textes: str) -> str:
    blob = fold(" ".join(t for t in textes if t))
    for theme, mots in _THEME_KEYWORDS:
        if any(m in blob for m in mots):
            return theme
    return "Autre"


def map_statut(sort_code: str) -> str:
    """« adopté » → adopte, sinon rejete (un scrutin a toujours un résultat)."""
    return "adopte" if "adopt" in fold(sort_code) else "rejete"


def map_position(position_majoritaire: str | None) -> PositionVote:
    """Position majoritaire d'un groupe → enum interne."""
    p = fold(position_majoritaire or "")
    if p.startswith("pour"):
        return PositionVote.pour
    if p.startswith("contre"):
        return PositionVote.contre
    if p.startswith("abstention"):
        return PositionVote.abstention
    # « absent », « nonVotant »… : le groupe n'a majoritairement pas pris part.
    return PositionVote.non_votant


def truncate(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def to_int(value: object, default: int = 0) -> int:
    """Les décomptes open data sont des chaînes ; conversion robuste."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def as_list(value: object) -> list:
    """L'open data sérialise « 1 élément » comme objet, « n » comme liste."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
