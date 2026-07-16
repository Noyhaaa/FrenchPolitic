"""Helpers de normalisation open data → schéma `Scrutin`."""
from __future__ import annotations

import re

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


def est_amendement(objet: str) -> bool:
    """Le scrutin porte-t-il sur un amendement (vs. le texte : ensemble, article,
    motion) ? Heuristique sur l'objet du vote (couvre « amendement »,
    « sous-amendement », « amendements identiques »)."""
    return "amendement" in fold(objet)


def est_sous_amendement(objet: str) -> bool:
    """Le scrutin porte-t-il sur un sous-amendement (amendement à un amendement) ?"""
    return "sous-amendement" in fold(objet)


# « (sous-)amendement … n° 80 » — fold() transforme « º » en « o », d'où [°o].
# Le remplissage [^,]*? tolère « amendement de suppression n° 25 ».
_RE_NUMERO = re.compile(r"(?:sous-)?amendements?[^,]*?n[°o]\s*(\d+)")
# Numéro de l'amendement PARENT d'un sous-amendement (« … à l'amendement n° X ») :
# on exclut le mot « amendement » contenu dans « sous-amendement ».
_RE_NUMERO_PARENT = re.compile(r"(?<!sous-)amendements?[^,]*?n[°o]\s*(\d+)")
# « de M. Léaument » / « de Mme K/Bidi » — nom en un token, tel qu'écrit.
_RE_AUTEUR = re.compile(r"\bde\s+(M\.|Mme)\s+([A-ZÀ-Þ][\w'’/-]*)")


def numero_amendement(objet: str) -> str | None:
    """Numéro de l'amendement (ou du sous-amendement) voté, extrait de l'objet
    officiel. None si non identifiable (§2.5 : on n'invente pas)."""
    m = _RE_NUMERO.search(fold(objet))
    return m.group(1) if m else None


def numero_amendement_parent(objet: str) -> str | None:
    """Pour un sous-amendement : numéro de l'amendement visé
    (« le sous-amendement n° 3 … à l'amendement n° 80 » → « 80 »)."""
    m = _RE_NUMERO_PARENT.search(fold(objet))
    return m.group(1) if m else None


def auteur_amendement(objet: str) -> str | None:
    """Auteur (« M. X » / « Mme Y ») si l'objet officiel en désigne un seul.

    Plusieurs auteurs (amendements identiques) → None : pas d'ambiguïté (§2.5).
    Pour un sous-amendement, la mention de l'amendement parent (« … à
    l'amendement n° X de Mme Y ») est ignorée.
    """
    zone = re.split(r"(?:à\s+l['’]|aux\s+)amendements?\b", objet, flags=re.IGNORECASE)[0]
    auteurs = {f"{civ} {nom}" for civ, nom in _RE_AUTEUR.findall(zone)}
    return auteurs.pop() if len(auteurs) == 1 else None


# Texte de loi cité dans l'objet d'un vote (« … à l'article 2 de la proposition
# de loi visant à … ») : nature reconnue puis tout ce qui suit. Seule
# « résolution » porte un accent → classe [ée] (pas de fold : on veut retrouver
# la casse/les accents d'origine pour le titre affiché).
_RE_TEXTE_RATTACHEMENT = re.compile(
    r"(?:projet de loi|proposition de loi|proposition de r[ée]solution)\b.*$",
    re.IGNORECASE | re.DOTALL,
)
# Mention finale de procédure entre parenthèses (« (deuxième lecture) »,
# « (texte de la commission mixte paritaire) ») : à retirer de la clé de
# regroupement pour qu'un même texte ne soit pas éclaté par lecture.
_RE_MENTION_FINALE = re.compile(r"\s*\([^()]*\)\s*$")


def texte_de_rattachement(objet: str) -> str | None:
    """Titre du texte de loi auquel se rattache un vote, extrait de son objet
    officiel (sous-chaîne telle quelle, §2.5 : rien n'est reformulé).

    Sert à regrouper sous un même dossier les scrutins dépourvus de
    `dossierRef` (amendements, articles, motions liées à un texte). None si
    l'objet ne cite aucun texte (motion de censure, déclaration…).
    """
    m = _RE_TEXTE_RATTACHEMENT.search(objet)
    if not m:
        return None
    titre = m.group(0).strip().rstrip(".").strip()
    titre = _RE_MENTION_FINALE.sub("", titre).strip()
    if not titre:
        return None
    return titre[0].upper() + titre[1:]


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
