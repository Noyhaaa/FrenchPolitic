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


class TypeVote(str, Enum):
    """Forme du scrutin public — ce qui explique le nombre de votants (§7.4).

    Liste **fermée**, miroir exact des `codeTypeVote` de l'archive des scrutins
    (`SPO` / `SPS` / `MOC`, seuls codes présents). Un code inconnu ne produit
    pas de valeur : mieux vaut ne rien dire du type que le deviner (§2.5).

    C'est la réponse à « 42 voix contre 0, pourquoi seulement 42 ? » : un vote
    **ordinaire** se tient en séance, au moment où le texte est examiné, parmi
    les députés alors présents ; un vote **solennel** est annoncé à l'avance.
    Mesuré sur la 17e législature : médiane de 132 votants contre 528.

    ⚠️ Ce n'est PAS un taux de présence, et on n'en dérivera jamais un — voir
    le refus de la participation sur la fiche député (§7.4).
    """

    ordinaire = "ordinaire"
    solennel = "solennel"
    # Article 49 de la Constitution : seules les voix FAVORABLES à la motion
    # sont recensées. `contre` et `abstention` y valent donc 0 **par
    # construction** (vérifié : les 23 motions de la législature), et les lire
    # comme une quasi-unanimité est le contresens que ce type existe pour
    # éviter. Le seul rapport qui décide est voix recueillies / requises.
    motion_censure = "motion_censure"


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
