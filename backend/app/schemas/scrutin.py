"""Contrat d'API — miroir exact des types du frontend (src/types/index.ts).

Unité centrale : le `Dossier` (un texte de loi), qui agrège les `Scrutin`
(votes successifs) et ses amendements. Sérialisé en camelCase pour que l'app
mobile consomme l'API sans transformation. Le §5.3 du MVP décrit ce modèle.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.domain.enums import (
    NiveauConfiance,
    PositionVote,
    SortAmendement,
    StatutScrutin,
    TypeSource,
)


class CamelModel(BaseModel):
    """Base : champs Python en snake_case, JSON en camelCase."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class PhraseSourcee(CamelModel):
    """Une phrase du résumé, systématiquement rattachée à une source (§4)."""

    phrase: str
    source_id: str


class ResultatGlobal(CamelModel):
    pour: int
    contre: int
    abstention: int
    non_votants: int


class PositionGroupe(CamelModel):
    groupe_id: str
    groupe_nom: str
    couleur: str
    position_majoritaire: PositionVote
    pour: int
    contre: int
    abstention: int
    cohesion: float | None = None
    # Vote nominatif (§5.2) : noms des députés du groupe par position.
    # None si la source ne le fournit pas (§2.5 : jamais de comblement).
    noms_pour: list[str] | None = None
    noms_contre: list[str] | None = None
    noms_abstention: list[str] | None = None


class Amendement(CamelModel):
    id: str
    # Numéro officiel (« 80 » pour « l'amendement n° 80 »), si identifiable.
    numero: str | None = None
    objet: str
    auteur: str | None = None
    sort: SortAmendement
    # Scrutin public de l'amendement, si mis aux voix (détail + nominatif là-bas).
    scrutin_id: str | None = None
    # Sous-amendements rattachés (« … à l'amendement n° X »). Un sous-amendement
    # dont le parent n'est pas identifiable reste au niveau amendement du dossier.
    sous_amendements: list["Amendement"] = []


class SourceOfficielle(CamelModel):
    type: TypeSource
    libelle: str
    url: str


class ChangementTexte(CamelModel):
    avant: str
    apres: str


class PhaseScrutin(CamelModel):
    label: str
    statut: StatutScrutin


class ArgumentGroupe(CamelModel):
    """La position d'un groupe dans le débat : son sens de vote (factuel, issu
    du scrutin) et l'argument qu'il a lui-même donné (§7.4).

    `argument` est une paraphrase courte et neutre de l'**explication de vote**
    du groupe (ses propres mots au compte rendu), validée par des contrôles
    déterministes. `sens` vient du **scrutin** (le vote enregistré), jamais du
    LLM : le « pour/contre » n'est donc pas une interprétation.
    """

    groupe: str  # nom complet du groupe (pas d'abréviation jargon, §8)
    sens: PositionVote
    argument: str


class QuestionsCitoyennes(CamelModel):
    """Les 4 questions citoyennes de la fiche dossier (§2.2 : comprendre en 30 s).

    Chaque réponse est optionnelle : absente = « information non disponible »
    (§2.5, jamais de comblement).
    - `resultat` est composé de façon **déterministe** depuis le vote décisif.
    - `pourquoi` et `changement` sont générés par LLM depuis l'**exposé des
      motifs**, puis validés par des contrôles déterministes (chiffres, nature
      du texte, lexique, attribution) — repli sur None en cas d'échec.
      `changement` commence toujours par « Selon l'auteur du texte » : c'est le
      point de vue du déposant, jamais un fait neutre (§4.3).
    - `desaccord` est la **juxtaposition des positions que les groupes formulent
      eux-mêmes** en explication de vote (jamais une synthèse éditoriale). Vide
      tant que le compte rendu de la séance n'est pas relié au dossier (§2.5).
      `desaccord_source` renvoie au compte rendu officiel (réversibilité §7.5).
    """

    pourquoi: str | None = None
    desaccord: list[ArgumentGroupe] | None = None
    desaccord_source: SourceOfficielle | None = None
    resultat: str | None = None
    changement: str | None = None


class ResumeScrutin(CamelModel):
    """Résumé neutre du texte (au niveau du dossier)."""

    titre_clair: str
    resume: list[PhraseSourcee]
    questions: QuestionsCitoyennes | None = None
    contexte: str | None = None
    objectif: str | None = None
    historique: str | None = None
    changement: ChangementTexte | None = None
    public_concerne: list[str] = []
    confiance: NiveauConfiance
    relu_par_humain: bool
    champs_non_documentes: list[str] = []


class Scrutin(CamelModel):
    """Un vote public précis rattaché à un dossier (objet + résultat + groupes).

    Servi par `GET /scrutins/{id}` — la fiche dossier n'embarque que des
    `ScrutinResume` (le nominatif rendrait le payload dossier illisible/lourd).
    """

    id: str
    dossier_id: str
    date: str  # ISO 8601
    objet: str
    statut: StatutScrutin
    scrutin_public: bool
    resultat: ResultatGlobal
    positions_groupes: list[PositionGroupe] = []
    # Pour le vote d'un amendement : ses sous-amendements (chacun lié à son
    # propre scrutin) — la fiche vote de l'amendement peut ainsi les lister.
    sous_amendements: list[Amendement] = []
    sources: list[SourceOfficielle] = []


class ScrutinResume(CamelModel):
    """Version allégée d'un scrutin, embarquée dans la fiche dossier."""

    id: str
    date: str
    objet: str
    statut: StatutScrutin
    scrutin_public: bool
    resultat: ResultatGlobal

    @classmethod
    def from_scrutin(cls, s: Scrutin) -> "ScrutinResume":
        return cls(
            id=s.id,
            date=s.date,
            objet=s.objet,
            statut=s.statut,
            scrutin_public=s.scrutin_public,
            resultat=s.resultat,
        )


class MiseAJourDossier(CamelModel):
    """Indicateur « mis à jour » d'un dossier (§7.7)."""

    date: str  # ISO 8601
    label: str


class RecapMensuel(CamelModel):
    """Récapitulatif d'activité du dernier mois **actif** (carte de l'accueil).

    Compte des **votes** (scrutins tenus dans le mois) — pas des dossiers, dont
    le statut évolue au fil de la navette. Purement descriptif (§7.8).
    """

    annee: int
    mois: int  # 1–12
    votes: int
    adoptes: int
    rejetes: int
    # Nombre de dossiers (textes) ayant connu au moins un vote dans le mois.
    textes: int


class ExposeMotifs(CamelModel):
    """Exposé des motifs du texte, rédigé par l'auteur du dépôt (§5.1).

    ⚠️ C'est le **point de vue du déposant**, PAS un fait neutre (§4.3) : à
    présenter comme un bloc **cité et attribué** (« Ce que dit l'auteur du
    texte »), jamais fondu dans le résumé neutre. `source` renvoie au texte
    officiel (réversibilité §7.5).
    """

    texte: str
    source: SourceOfficielle


class Dossier(CamelModel):
    """Entité centrale : un dossier législatif (un texte) et sa trajectoire."""

    id: str
    titre_officiel: str
    titre_clair: str
    accroche: str
    statut: StatutScrutin
    phase: PhaseScrutin | None = None
    theme: str
    temps_lecture_sec: int
    date_dernier_scrutin: str
    mise_a_jour: MiseAJourDossier | None = None
    scrutins: list[ScrutinResume] = []
    amendements: list[Amendement] = []
    sources: list[SourceOfficielle] = []
    resume: ResumeScrutin
    # Exposé des motifs (point de vue de l'auteur, bloc attribué). Absent tant
    # qu'on n'a pas pu récupérer le PDF officiel du texte (§2.5 : pas comblé).
    expose_motifs: ExposeMotifs | None = None


class DossierListItem(CamelModel):
    """Version allégée pour le fil et la recherche (§3.1 / §3.3).

    Suffit à afficher une carte sans transférer tout le détail.
    """

    id: str
    date: str
    titre_clair: str
    accroche: str
    statut: StatutScrutin
    theme: str
    temps_lecture_sec: int
    nombre_scrutins: int
    mise_a_jour: MiseAJourDossier | None = None
    # Résultat du dernier scrutin **public** (voix pour/contre) pour la barre de
    # la carte. None si le dernier vote n'est pas nominatif (§5.2, §2.5).
    resultat_dernier_scrutin: ResultatGlobal | None = None

    @staticmethod
    def _resultat_dernier(scrutins: list[ScrutinResume]) -> ResultatGlobal | None:
        # `scrutins` est ordonné du plus récent au plus ancien : on prend le
        # résultat du premier vote nominatif (les votes à main levée n'ont pas de
        # décompte affichable, §5.2).
        for s in scrutins:
            if s.scrutin_public:
                return s.resultat
        return None

    @classmethod
    def from_dossier(cls, d: Dossier) -> "DossierListItem":
        return cls(
            id=d.id,
            date=d.date_dernier_scrutin,
            titre_clair=d.titre_clair,
            accroche=d.accroche,
            statut=d.statut,
            theme=d.theme,
            temps_lecture_sec=d.temps_lecture_sec,
            nombre_scrutins=len(d.scrutins),
            mise_a_jour=d.mise_a_jour,
            resultat_dernier_scrutin=cls._resultat_dernier(d.scrutins),
        )


class SectionTheme(CamelModel):
    """Une rangée thématique de l'accueil (façon « catégorie » Netflix)."""

    theme: str
    dossiers: list[DossierListItem] = []


class Accueil(CamelModel):
    """Écran d'accueil complet, servi en UNE réponse.

    Construire les rangées côté serveur évite le remplissage désordonné qu'on
    aurait en les dérivant d'un fil paginé : le client affiche tout d'un coup.
    « Aujourd'hui » / « Hier » sont factuels (date du dernier scrutin) et vides
    hors jours de séance — le client masque alors la rangée (§2.5).
    """

    a_la_une: DossierListItem | None = None
    aujourdhui: list[DossierListItem] = []
    hier: list[DossierListItem] = []
    sections: list[SectionTheme] = []
