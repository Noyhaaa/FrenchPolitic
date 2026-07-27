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
# `normalize` ne dépend que de `domain` et `utils` : pas de cycle avec les schémas.
from app.ingestion.normalize import nature_texte


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


class Votant(CamelModel):
    """Un député nommé dans la ventilation nominative d'un scrutin (§5.2).

    `depute_id` n'est renseigné **que** si l'acteur figure dans le référentiel
    des députés servi par l'API : c'est lui qui autorise l'app à ouvrir la fiche
    du député, et un lien ne doit jamais mener à un 404. Un ancien député (mandat
    terminé en cours de législature) garde donc son nom, sans identifiant.
    """

    nom: str
    depute_id: str | None = None


class PositionGroupe(CamelModel):
    groupe_id: str
    groupe_nom: str
    couleur: str
    position_majoritaire: PositionVote
    pour: int
    contre: int
    abstention: int
    cohesion: float | None = None
    # Vote nominatif (§5.2) : les députés du groupe, par position.
    # None si la source ne le fournit pas (§2.5 : jamais de comblement).
    votants_pour: list[Votant] | None = None
    votants_contre: list[Votant] | None = None
    votants_abstention: list[Votant] | None = None


class Amendement(CamelModel):
    id: str
    # Numéro officiel (« 80 » pour « l'amendement n° 80 »), si identifiable.
    numero: str | None = None
    objet: str
    auteur: str | None = None
    sort: SortAmendement
    # Article/division visé (« Article 2 », « Article unique ») — factuel, neutre.
    cible: str | None = None
    # Contenu de l'amendement : ce qu'il propose de changer (extrait officiel).
    dispositif: str | None = None
    # Exposé sommaire = le « pourquoi », côté AUTEUR (non neutre, §4.3) : à
    # afficher en bloc cité et attribué, jamais fondu dans le résumé neutre.
    expose_sommaire: str | None = None
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
    # Objet officiel du vote d'où viennent les `sens` de `desaccord` — le vote
    # conclusif du texte. À AFFICHER avec les positions : « pour » sur une motion
    # de rejet préalable veut dire « pour le rejet du texte », l'inverse de ce que
    # le seul mot « pour » laisserait croire (§7.4). Absent = ligne masquée (§2.5).
    desaccord_objet: str | None = None
    desaccord_source: SourceOfficielle | None = None
    resultat: str | None = None
    changement: str | None = None
    # Renseignée quand `changement` vient du **dispositif officiel** (fait) et
    # non de l'exposé (point de vue de l'auteur, signalé par son préfixe) :
    # renvoie au texte déposé (réversibilité §7.5).
    changement_source: SourceOfficielle | None = None


class QuestionsAmendement(CamelModel):
    """Les questions citoyennes d'un vote d'amendement (fiche vote, §2.2).

    Adaptation aux amendements des 4 questions de la fiche dossier. Chaque
    réponse est optionnelle : absente = « information non disponible » (§2.5).
    - `pourquoi` est généré par LLM depuis l'**exposé sommaire** (validé par les
      mêmes contrôles déterministes que les questions dossier). Il commence
      toujours par « Selon l'auteur de l'amendement » : c'est le point de vue du
      déposant, jamais un fait neutre (§4.3).
    - `changement` est généré par LLM depuis le **dispositif** (l'extrait
      officiel de ce que l'amendement change), au conditionnel — validé
      déterministiquement contre ce dispositif.
    - `resultat` est composé de façon **déterministe** depuis le vote.
    - Le « qui était pour / contre » n'a pas de champ ici : il est rendu côté
      app depuis `positions_groupes` (déterministe, sourcé par le scrutin).
    """

    pourquoi: str | None = None
    changement: str | None = None
    resultat: str | None = None


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
    # Pour un vote d'amendement/sous-amendement : son contenu enrichi (open data
    # AN). `cible`/`dispositif` sont factuels ; `expose_sommaire` est le point de
    # vue de l'auteur (non neutre, §4.3) → bloc attribué sur la fiche vote.
    cible: str | None = None
    dispositif: str | None = None
    expose_sommaire: str | None = None
    # Pour un vote d'amendement : ses questions citoyennes (générées à
    # l'ingestion, affichées en tête de fiche vote). None sur un vote de texte.
    questions: QuestionsAmendement | None = None
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


class DispositifTexte(CamelModel):
    """Dispositif du texte déposé — ses **articles**, tels que publiés (§5.1).

    Contrairement à l'exposé des motifs, c'est un **fait officiel** : ce que le
    texte écrit, pas ce que son auteur en dit. Sert de source vérifiable à la
    réponse « qu'est-ce que ça change » (contrôlée déterministiquement, cf.
    `app.ai.questions`). Non affiché tel quel : c'est du droit codifié, le
    lecteur l'atteint par `source` (§7.5).
    """

    texte: str
    source: SourceOfficielle


class Dossier(CamelModel):
    """Entité centrale : un dossier législatif (un texte) et sa trajectoire."""

    id: str
    titre_officiel: str
    titre_clair: str
    # Le but du texte en une phrase, tiré de la Q1 (« pourquoi ont-ils
    # débattu ? »). Absente tant que la Q1 ne l'est pas — on ne comble pas (§2.5).
    accroche: str | None = None
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
    # Dispositif du texte déposé (fait officiel), extrait du même PDF. Sert de
    # source à la réponse « qu'est-ce que ça change » ; jamais affiché brut.
    dispositif: DispositifTexte | None = None


class DossierListItem(CamelModel):
    """Version allégée pour le fil et la recherche (§3.1 / §3.3).

    Suffit à afficher une carte sans transférer tout le détail.
    """

    id: str
    date: str
    titre_clair: str
    accroche: str | None = None
    # Nature du texte (« Projet de loi »…), affichée en label à part : le titre
    # court ne la porte plus. None quand le titre officiel ne la porte pas (§2.5).
    nature_texte: str | None = None
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
            accroche=d.accroche or None,
            nature_texte=nature_texte(d.titre_officiel),
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


class ThemeListItem(CamelModel):
    """Un thème tel qu'exposé par le filtre de la recherche (§3.3).

    Seuls les thèmes **réellement présents** sont listés, avec leur nombre de
    dossiers : un filtre qui ne ramènerait rien n'a pas à être proposé (§2.5).
    """

    nom: str
    nombre: int


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
