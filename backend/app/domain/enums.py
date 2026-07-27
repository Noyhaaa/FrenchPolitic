"""Énumérations du domaine — miroir des types TypeScript du frontend (src/types)."""
from __future__ import annotations

from enum import Enum


class StatutScrutin(str, Enum):
    adopte = "adopte"
    rejete = "rejete"
    en_cours = "en_cours"


class PositionVote(str, Enum):
    pour = "pour"
    contre = "contre"
    abstention = "abstention"
    non_votant = "non_votant"


class Chambre(str, Enum):
    """Chambre du Parlement d'où vient un vote, un parlementaire ou une étape.

    Discriminant introduit avec l'ingestion du Sénat : un dossier agrège
    désormais les votes des DEUX chambres, et rien à l'écran ne doit laisser
    croire qu'un vote sénatorial est un vote de l'Assemblée (§2.5). Les données
    antérieures sont toutes `assemblee` (défaut des colonnes).
    """

    assemblee = "assemblee"
    senat = "senat"


class ObjetVote(str, Enum):
    """Nature de ce sur quoi portait un vote, pour situer une entrée
    d'historique de député (§5.2)."""

    dossier = "dossier"
    amendement = "amendement"
    sous_amendement = "sous_amendement"


class NiveauConfiance(str, Enum):
    haute = "haute"
    moyenne = "moyenne"
    faible = "faible"


class SortAmendement(str, Enum):
    adopte = "adopte"
    rejete = "rejete"
    retire = "retire"


class TypeSource(str, Enum):
    texte = "texte"
    scrutin = "scrutin"
    debats = "debats"
    amendements = "amendements"


class StatutRevue(str, Enum):
    """Statut de la revue humaine d'un résumé (§4.6 du MVP)."""

    publie = "publie"          # validé, affiché dans l'app
    en_attente = "en_attente"  # en file de revue humaine
    rejete = "rejete"          # bloqué par un garde-fou / relecteur
