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


class TypeMotion(str, Enum):
    """Motion qui **inverse le sens** de son propre résultat.

    Sur ces votes-là, le vocabulaire du scrutin dit le contraire de ce qui
    arrive au texte : voter *pour* une motion de rejet préalable, c'est demander
    la mort du texte, et l'*adopter*, c'est le rejeter. Affichés sans mention,
    le verdict (« Adopté »), l'écart de voix et la ligne de fracture (« Ont voté
    pour ») se lisent donc tous à l'envers — vécu : 8 dossiers annonçaient
    « Adopté » sur un texte que la motion venait de rejeter.

    Liste **fermée**, comme `_PHRASES_CONDUITE_DE_SEANCE` : un objet non reconnu
    ne produit pas de valeur, et l'app n'affiche alors aucune mention plutôt
    qu'une conséquence devinée (§2.5). Chaque valeur porte ci-dessous la
    conséquence de son ADOPTION, telle que la fixe le Règlement — c'est elle que
    l'app écrit à l'écran (`src/constants/motions.ts`).

    ⚠️ La **motion de censure** n'en fait pas partie : elle ne rejette aucun
    texte, elle renverse un gouvernement, et elle a déjà son traitement propre
    (`TypeVote.motion_censure`).
    """

    # Art. 91 RAN — adoptée, le texte est rejeté sans examen de ses articles.
    rejet_prealable = "rejet_prealable"
    # Art. 44 RS — l'équivalent sénatorial : adoptée, elle entraîne le rejet.
    question_prealable = "question_prealable"
    # Art. 44 RS également — le texte est jugé contraire à la Constitution ou à
    # une règle de recevabilité : adoptée, elle entraîne aussi son rejet. Forme
    # constatée sur 7 scrutins du Sénat, tous vérifiés à la source.
    exception_irrecevabilite = "exception_irrecevabilite"
    # Adoptée, le texte retourne en commission et son examen en séance s'arrête.
    renvoi_en_commission = "renvoi_en_commission"
    # Art. 122 RAN — adoptée, l'examen est suspendu, le texte étant proposé au
    # référendum.
    referendaire = "referendaire"
    # Révision constitutionnelle — adoptée, l'examen est reporté.
    ajournement = "ajournement"


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
