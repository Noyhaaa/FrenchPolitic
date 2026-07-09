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
