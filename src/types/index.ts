/**
 * Modèle de données du MVP (cf. §5.3).
 * Ces types décrivent le contrat que le backend/API expose.
 *
 * Unité centrale : le **Dossier** (un texte de loi), qui agrège les
 * **scrutins** (les votes successifs de la navette) et ses amendements.
 * Le frontend et le backend en sont des miroirs (camelCase des deux côtés).
 */

export type StatutScrutin = 'adopte' | 'rejete' | 'en_cours';

export type PositionVote = 'pour' | 'contre' | 'abstention' | 'non_votant';

/**
 * Chambre du Parlement d'où vient un vote, un parlementaire ou une étape de la
 * navette. Un dossier agrège les votes des DEUX assemblées : rien à l'écran ne
 * doit laisser croire qu'un vote sénatorial est un vote de l'Assemblée (§2.5).
 */
export type Chambre = 'assemblee' | 'senat';

export type NiveauConfiance = 'haute' | 'moyenne' | 'faible';

// Miroir de `THEMES` dans backend/app/ingestion/normalize.py — à garder synchronisé.
export type ThemeScrutin =
  | 'Logement'
  | 'Santé'
  | 'Fiscalité'
  | 'Énergie'
  | 'Éducation'
  | 'Environnement'
  | 'Justice'
  | 'Travail'
  | 'Économie'
  | 'Institutions'
  | 'Vie parlementaire'
  | 'International & Défense'
  | 'Agriculture'
  | 'Transports'
  | 'Culture'
  | 'Sport'
  | 'Immigration'
  | 'Sécurité'
  | 'Autre';

/** Une phrase du résumé, systématiquement rattachée à une source (§4). */
export interface PhraseSourcee {
  phrase: string;
  sourceId: string;
}

/** Résultat global d'un scrutin (§3.2 point 4). */
export interface ResultatGlobal {
  pour: number;
  contre: number;
  abstention: number;
  nonVotants: number;
}

/** Position majoritaire d'un groupe politique sur un scrutin (§3.2 point 5). */
export interface PositionGroupe {
  groupeId: string;
  groupeNom: string;
  couleur: string;
  positionMajoritaire: PositionVote;
  pour: number;
  contre: number;
  abstention: number;
  /** Taux de cohésion 0..1, optionnel si non disponible. */
  cohesion?: number;
  /**
   * Vote nominatif (§5.2, scrutins publics uniquement) : les députés du groupe
   * par position. Absent si la donnée n'est pas fournie par la source
   * (§2.5 : on n'invente pas — le bloc est alors masqué).
   */
  votantsPour?: Votant[];
  votantsContre?: Votant[];
  votantsAbstention?: Votant[];
}

/**
 * Un parlementaire nommé dans la ventilation nominative d'un scrutin (§5.2).
 *
 * `deputeId` n'est présent que si la personne figure au référentiel servi par
 * l'API : c'est lui, et lui seul, qui autorise à ouvrir sa fiche depuis son
 * vote — un lien ne doit jamais mener à un 404. Un ancien député garde donc son
 * nom, sans lien. Le champ garde son nom historique alors qu'il porte aussi des
 * sénateurs (`SEN-…`) : c'est la clé du référentiel commun, pas une assertion
 * sur la chambre — celle-ci est portée par `Scrutin.chambre`.
 */
export interface Votant {
  nom: string;
  deputeId?: string;
}

/**
 * Un amendement du texte (§4.5). Quand il a fait l'objet d'un scrutin public,
 * `scrutinId` pointe vers ce vote (détail + nominatif via la fiche vote) — c'est
 * là que le vote de l'amendement s'affiche, pas dans la liste des votes du texte.
 */
export interface Amendement {
  id: string;
  /** Numéro officiel (« 80 » pour « l'amendement n° 80 »), si identifiable. */
  numero?: string;
  objet: string;
  auteur?: string;
  sort: 'adopte' | 'rejete' | 'retire';
  /** Article/division visé (« Article 2 », « Article unique ») — factuel, neutre. */
  cible?: string;
  /** Contenu de l'amendement : ce qu'il propose de changer (extrait officiel). */
  dispositif?: string;
  /**
   * Exposé sommaire = le « pourquoi », côté AUTEUR (non neutre, §4.3). À afficher
   * en bloc cité et attribué, jamais fondu dans un texte neutre (comme l'exposé
   * des motifs du dossier).
   */
  exposeSommaire?: string;
  /** Scrutin public correspondant, si l'amendement a été mis aux voix. */
  scrutinId?: string;
  /**
   * Sous-amendements rattachés (« … à l'amendement n° X »). Affichés dans leur
   * propre section de la fiche dossier ET sur la fiche vote de leur parent.
   */
  sousAmendements?: Amendement[];
}

export type TypeSource = 'texte' | 'scrutin' | 'debats' | 'amendements';

export interface SourceOfficielle {
  type: TypeSource;
  libelle: string;
  url: string;
}

/** Bloc « Ce que prévoit le texte » (§4.5) — descriptif, non comparatif. */
export interface ChangementTexte {
  avant: string;
  apres: string;
}

/**
 * La position d'un groupe dans le débat : son sens de vote (factuel, issu du
 * scrutin) et l'argument qu'il a lui-même donné en explication de vote (§7.4).
 * `argument` est une paraphrase courte et neutre de ses propres mots (validée
 * côté backend) ; `sens` vient du scrutin, jamais d'une interprétation.
 */
export interface ArgumentGroupe {
  groupe: string;
  sens: PositionVote;
  argument: string;
}

/**
 * Les 4 questions citoyennes de la fiche dossier (§2.2 : comprendre en 30 s).
 *
 * Chaque réponse est optionnelle : absente = « information non disponible »
 * (§2.5, jamais de comblement).
 * - `resultat` est composé de façon déterministe depuis le vote décisif.
 * - `pourquoi` / `changement` viennent de l'exposé des motifs (validés par des
 *   contrôles déterministes côté backend). `changement` commence toujours par
 *   « Selon l'auteur du texte » : point de vue du déposant, pas un fait (§4.3).
 * - `desaccord` est la juxtaposition des positions que les groupes formulent
 *   eux-mêmes en explication de vote ; `desaccordSource` renvoie au compte rendu
 *   officiel (§7.5). Vide tant que la séance n'est pas reliée au dossier (§2.5).
 */
export interface QuestionsCitoyennes {
  pourquoi?: string;
  desaccord?: ArgumentGroupe[];
  /**
   * Objet officiel du vote d'où viennent les `sens` de `desaccord` — le vote qui
   * conclut le texte. À afficher AVEC les positions : « pour » sur une motion de
   * rejet préalable veut dire « pour le rejet du texte » (§7.4). Absent → ligne
   * masquée (§2.5).
   */
  desaccordObjet?: string;
  desaccordSource?: SourceOfficielle;
  resultat?: string;
  changement?: string;
  /**
   * Présente quand `changement` vient du **dispositif officiel** (un fait) et
   * non de l'exposé (point de vue de l'auteur, signalé par son préfixe) :
   * renvoie au texte déposé (§7.5).
   */
  changementSource?: SourceOfficielle;
}

/**
 * Les questions citoyennes d'un vote d'amendement (fiche vote, §2.2) —
 * adaptation aux amendements des 4 questions de la fiche dossier.
 *
 * Chaque réponse est optionnelle : absente = « information non disponible »
 * (§2.5, jamais de comblement).
 * - `pourquoi` vient de l'exposé sommaire (validé côté backend) et commence
 *   toujours par « Selon son auteur » : point de vue du déposant (§4.3).
 * - `changement` vient du dispositif (l'extrait officiel), au conditionnel.
 * - `resultat` est composé de façon déterministe depuis le vote.
 * - Le « qui était pour / contre » n'a pas de champ ici : il est rendu depuis
 *   `positionsGroupes` du scrutin (déterministe, sourcé par le vote).
 */
export interface QuestionsAmendement {
  pourquoi?: string;
  changement?: string;
  resultat?: string;
}

/**
 * Résumé neutre du texte, généré et ancré aux sources (§4).
 * `champsNonDocumentes` liste les champs non renseignés par les sources
 * (règle d'or §2.5 : « information non disponible », jamais de supposition).
 */
export interface ResumeScrutin {
  titreClair: string;
  resume: PhraseSourcee[];
  questions?: QuestionsCitoyennes;
  contexte?: string;
  objectif?: string;
  historique?: string;
  changement?: ChangementTexte;
  publicConcerne: string[];
  confiance: NiveauConfiance;
  reluParHumain: boolean;
  champsNonDocumentes: string[];
}

/**
 * Exposé des motifs du texte, tel que rédigé par l'auteur du dépôt (§5.1).
 *
 * ⚠️ C'est le **point de vue du déposant**, PAS un fait neutre (§4.3) : à
 * afficher comme un bloc **cité et attribué** (« Ce que dit l'auteur du texte »),
 * jamais fondu dans le résumé neutre. `source` renvoie au texte officiel (§7.5).
 */
export interface ExposeMotifs {
  texte: string;
  source: SourceOfficielle;
}

/**
 * Dispositif du texte déposé — ses **articles**, tels que publiés (§5.1).
 *
 * Contrairement à l'exposé des motifs, c'est un **fait officiel** : ce que le
 * texte écrit. Sert de source à la réponse « qu'est-ce que ça change »
 * (`QuestionsCitoyennes.changementSource`). Non affiché tel quel : c'est du
 * droit codifié, le lecteur l'atteint par `source`.
 */
export interface DispositifTexte {
  texte: string;
  source: SourceOfficielle;
}

/**
 * Une étape de la trajectoire du texte au Parlement (frise de la fiche).
 *
 * Documentée par les **actes législatifs officiels** du dossier (Assemblée,
 * Sénat, CMP, Conseil constitutionnel) quand l'archive les fournit, sinon par
 * les mentions de navette portées par les objets de vote. Calculée côté
 * backend : l'app ne la déduit plus des scrutins, qui ne voient qu'une chambre.
 *
 * `statut` reste optionnel — il n'est posé que si un vote sur l'ensemble de
 * CETTE étape le documente. Une étape connue mais pas encore conclue s'affiche
 * donc avec sa seule date, plutôt qu'avec un statut deviné (§2.5). `chambre`
 * est absente pour les étapes communes aux deux assemblées (CMP) ou extérieures
 * au Parlement (Conseil constitutionnel).
 */
export interface PhaseScrutin {
  label: string;
  chambre?: Chambre;
  /** Statut utilisé pour le style du badge (absent = non documenté). */
  statut?: StatutScrutin;
  /** Date de l'étape (ISO). */
  date?: string;
}

/**
 * Un scrutin = un vote public précis rattaché à un dossier (§5.3).
 * Porte l'objet du vote (« Vote sur l'ensemble », « Amendement n° 80… »),
 * son résultat et la ventilation par groupe (avec le nominatif si disponible).
 * Le résumé du texte, lui, vit au niveau du dossier.
 * Servi par `GET /scrutins/{id}` (la fiche dossier ne transporte que des
 * `ScrutinResume` pour rester légère et lisible).
 */
export interface Scrutin {
  id: string;
  /** Dossier (texte de loi) auquel ce vote se rattache. */
  dossierId: string;
  date: string; // ISO
  /** Ce sur quoi les parlementaires ont voté (objet du scrutin). */
  objet: string;
  statut: StatutScrutin;
  /**
   * Chambre où le vote a eu lieu. À afficher : un dossier agrège les votes des
   * deux assemblées, et « 214 pour » n'a pas le même sens selon l'hémicycle.
   */
  chambre: Chambre;
  /** true = scrutin public (vote nominatif dispo), false = à main levée (§5.2). */
  scrutinPublic: boolean;
  resultat: ResultatGlobal;
  positionsGroupes: PositionGroupe[];
  /** Pour un vote d'amendement : article visé (« Article 2 ») — factuel, neutre. */
  cible?: string;
  /** Pour un vote d'amendement : ce qu'il propose de changer (extrait officiel). */
  dispositif?: string;
  /**
   * Pour un vote d'amendement : exposé sommaire = le « pourquoi », côté AUTEUR
   * (non neutre, §4.3) → bloc cité et attribué, jamais présenté comme neutre.
   */
  exposeSommaire?: string;
  /**
   * Pour un vote d'amendement : ses questions citoyennes (générées à
   * l'ingestion, affichées en tête de fiche vote). Absent sur un vote de texte.
   */
  questions?: QuestionsAmendement;
  /**
   * Pour le vote d'un amendement : ses sous-amendements (chacun lié à son
   * propre scrutin) — la fiche vote de l'amendement les liste.
   */
  sousAmendements?: Amendement[];
  sources: SourceOfficielle[];
}

/**
 * Version allégée d'un scrutin, embarquée dans la fiche dossier : de quoi
 * afficher une ligne de la liste des votes (objet + statut + micro-résultat).
 * Le détail complet (groupes, nominatif) se charge au tap via `Scrutin`.
 */
export interface ScrutinResume {
  id: string;
  date: string;
  objet: string;
  statut: StatutScrutin;
  chambre: Chambre;
  scrutinPublic: boolean;
  resultat: ResultatGlobal;
}

/**
 * Indicateur « mis à jour » d'un dossier (§7.7) : un dossier remonte dans le
 * fil quand un nouveau scrutin s'y rattache. Le label reste factuel.
 */
export interface MiseAJourDossier {
  date: string; // ISO — date de la dernière évolution
  label: string; // ex. « Nouveau vote »
}

/**
 * Entité centrale : un dossier législatif (un texte) et sa trajectoire.
 * Agrège les scrutins successifs, les amendements clés et un résumé neutre.
 */
export interface Dossier {
  id: string;
  titreOfficiel: string;
  /**
   * Titre d'affichage : le titre officiel sans la nature (rendue en label à
   * part) ni son connecteur (« visant à »…). Voir `titre_court` côté backend.
   */
  titreClair: string;
  /**
   * Le but du texte en une phrase, tiré de la Q1 « pourquoi ont-ils débattu ? ».
   * Absente tant que la Q1 l'est : on masque plutôt que de combler (§2.5).
   */
  accroche?: string;
  statut: StatutScrutin;
  phase?: PhaseScrutin;
  /**
   * Trajectoire du texte au Parlement, dans l'ordre chronologique (frise de la
   * fiche). Calculée côté backend depuis les actes législatifs officiels : elle
   * couvre les deux chambres, ce que les seuls scrutins ne permettaient pas.
   * Vide quand aucune étape n'est documentée → frise masquée (§2.5).
   */
  trajectoire: PhaseScrutin[];
  theme: ThemeScrutin;
  tempsLectureSec: number;
  /** Date du scrutin le plus récent du dossier (ISO). */
  dateDernierScrutin: string;
  /** Présent si le dossier a évolué depuis une consultation précédente (§7.7). */
  miseAJour?: MiseAJourDossier;
  /** Votes du dossier (allégés), du plus récent au plus ancien. */
  scrutins: ScrutinResume[];
  amendements: Amendement[];
  sources: SourceOfficielle[];
  resume: ResumeScrutin;
  /**
   * Exposé des motifs du texte (point de vue de l'auteur, bloc attribué).
   * Absent tant que le PDF officiel n'a pas pu être récupéré (§2.5).
   */
  exposeMotifs?: ExposeMotifs;
  /**
   * Dispositif du texte déposé (fait officiel), extrait du même PDF que
   * l'exposé. Source de la réponse Q4 ; jamais affiché brut.
   */
  dispositif?: DispositifTexte;
  /**
   * Ce dossier n'est pas un texte de loi mais un **événement autonome** :
   * motion de censure, déclaration du Gouvernement. Il n'a ni articles, ni
   * exposé des motifs — non pas parce qu'on ne les a pas trouvés, mais parce
   * qu'ils n'existent pas. On masque alors les questions sans objet
   * (« pourquoi ce texte ? », « qu'est-ce que ça change ? ») au lieu d'afficher
   * « information non disponible », qui laisserait croire à une lacune (§2.5).
   */
  estEvenementAutonome?: boolean;
}

/**
 * Version allégée renvoyée par le fil et la recherche (§3.1 / §3.3).
 * Suffit à afficher une carte sans transférer tout le détail du dossier.
 * Miroir de `DossierListItem` côté backend.
 */
export interface DossierListItem {
  id: string;
  /** Date du dernier scrutin (tri du fil). */
  date: string;
  titreClair: string;
  /** Le but du texte en une phrase (tiré de la Q1) — absente si pas de Q1 (§2.5). */
  accroche?: string;
  /**
   * Nature du texte (« Projet de loi »…), affichée en label : le titre court ne
   * la porte plus. Absente quand le titre officiel ne la porte pas (§2.5).
   */
  natureTexte?: string;
  statut: StatutScrutin;
  theme: ThemeScrutin;
  tempsLectureSec: number;
  /** Nombre de scrutins rattachés (affiché sur la carte). */
  nombreScrutins: number;
  miseAJour?: MiseAJourDossier;
  /**
   * Chambres qui ont voté ce texte, dans l'ordre chronologique. Une carte du
   * fil doit dire d'où vient le vote qu'elle résume : sans ça, un texte encore
   * au Sénat se lirait comme un vote de l'Assemblée (§2.5).
   */
  chambres: Chambre[];
  /**
   * Résultat du dernier scrutin **public** du dossier (voix pour/contre) —
   * alimente la barre de résultat de la carte. Absent si le dernier vote n'est
   * pas nominatif (à main levée) : on n'affiche alors pas de barre (§2.5, §5.2).
   */
  resultatDernierScrutin?: ResultatGlobal;
}

/** Une rangée thématique de l'accueil (façon « catégorie » Netflix). */
export interface SectionTheme {
  theme: ThemeScrutin;
  dossiers: DossierListItem[];
}

/**
 * Un thème proposé en filtre de recherche (§3.3, miroir backend).
 *
 * Seuls les thèmes qui ont réellement des dossiers sont servis : on ne propose
 * pas un filtre qui ne ramènerait rien (§2.5).
 */
export interface ThemeListItem {
  nom: ThemeScrutin;
  nombre: number;
}

/**
 * Écran d'accueil complet, servi en UNE réponse (miroir backend).
 * Construit côté serveur pour un affichage atomique — pas de remplissage
 * progressif des rangées. « Aujourd'hui » / « Hier » vides hors jours de
 * séance (rangée masquée, §2.5).
 */
/**
 * Un vote de la rangée « Les votes les plus disputés » (accueil).
 * Miroir de `VoteDisputeItem` côté backend.
 *
 * ⚠️ « Disputé » qualifie **l'arithmétique du scrutin** — écart de voix,
 * abstention, groupes divisés —, jamais la mesure votée (§4.3). C'est pourquoi
 * la carte affiche toujours les décomptes officiels à côté du rang : le lecteur
 * voit le fait, pas seulement le classement.
 *
 * `groupesDisperses` est **absent au Sénat** (délégation de vote par groupe,
 * même doctrine que « contre son groupe ») : la mention est alors masquée (§2.5).
 */
export interface VoteDisputeItem {
  scrutinId: string;
  dossierId: string;
  /** Titre d'affichage du texte : un vote seul ne se situe pas. */
  dossierTitre: string;
  objet: string;
  date: string;
  chambre: Chambre;
  statut: StatutScrutin;
  resultat: ResultatGlobal;
  /** Écart de voix entre le pour et le contre. */
  ecart: number;
  /** Positions majoritaires distinctes parmi les groupes (1 = unanimité). */
  camps: number;
  groupesDisperses?: number | null;
}

export interface Accueil {
  aLaUne: DossierListItem | null;
  aujourdhui: DossierListItem[];
  hier: DossierListItem[];
  /** Vide = aucun vote récent classable → la rangée est masquée (§2.5). */
  votesDisputes?: VoteDisputeItem[];
  sections: SectionTheme[];
}

/**
 * Activité du dernier mois **actif** (carte récap de l'accueil, §7.8).
 * Compte des votes (scrutins tenus dans le mois), pas des dossiers.
 * Miroir de `RecapMensuel` côté backend.
 */
export interface RecapMensuel {
  annee: number;
  /** 1–12. */
  mois: number;
  votes: number;
  adoptes: number;
  rejetes: number;
  /** Nombre de dossiers (textes) ayant connu au moins un vote dans le mois. */
  textes: number;
}

// ---------------------------------------------------------------------------
// Parlementaires (annuaire, fiche, historique de votes)
//
// Le sens de vote n'existe que pour les scrutins PUBLICS (nominatifs, §5.2) :
// c'est la seule source de l'historique. « Contre son groupe » est un fait
// déduit (position ≠ `positionMajoritaire` de son groupe sur le même scrutin),
// jamais une interprétation (§7.4).
//
// ⚠️ Le référentiel est COMMUN aux deux chambres (les noms `Depute`/`deputeId`
// sont historiques, `chambre` est le discriminant). Mais au Sénat, les
// bulletins d'un scrutin public ordinaire sont déposés par un délégué de groupe
// pour l'ensemble de ses membres : le nominatif y reflète la position du
// GROUPE, pas l'acte individuel — et la source ne permet pas de distinguer ces
// scrutins de ceux à la tribune. `contreSonGroupe` et `cohesionGroupe` sont
// donc TOUJOURS absents pour un sénateur (§7.4).
// Miroir de `backend/app/schemas/depute.py`.
// ---------------------------------------------------------------------------

/** Un parlementaire (« acteur » de l'open data AN, ou sénateur senat.fr). */
export interface Depute {
  /** Référence acteur AMO (« PA841605 ») ou matricule Sénat (« SEN-08061X »). */
  id: string;
  nom: string;
  chambre: Chambre;
  groupeId: string;
  groupeNom: string;
  /** Couleur du groupe (même source que `PositionGroupe.couleur`). */
  groupeCouleur: string;
  circonscription: string;
  /**
   * Début de mandat (ISO), absent si non documenté.
   * ⚠️ Toujours absent au Sénat : l'annuaire senat.fr ne publie pas de date de
   * mandat. Ce n'est pas un trou d'ingestion — le champ est simplement masqué.
   */
  depuis?: string;
  /** Photo officielle si disponible — sinon l'app affiche les initiales. */
  portraitUrl?: string;
  /**
   * Commission permanente. Servie pour les **sénateurs** (l'annuaire senat.fr
   * la publie) ; absente côté Assemblée pour l'instant. Absente = masquée (§2.5).
   */
  commission?: string;
}

/**
 * Version allégée pour l'annuaire — photo comprise : c'est elle qui rend la
 * liste identifiable d'un coup d'œil (absente → initiales).
 */
export interface DeputeListItem {
  id: string;
  nom: string;
  chambre: Chambre;
  groupeNom: string;
  groupeCouleur: string;
  circonscription: string;
  portraitUrl?: string;
}

/**
 * Statistiques agrégées du député (12 derniers mois). Champs absents =
 * « information non disponible » (§2.5), jamais comblés.
 *
 * PAS de taux de participation : l'open data ne recense que les votants
 * physiques d'un scrutin public, si bien qu'un ratio de présence se lirait
 * comme un score d'absentéisme que la source ne soutient pas (§7.4).
 */
export interface PortraitVote {
  /**
   * Part de ses votes alignés sur la majorité de son groupe (0..1). Toujours
   * absent pour un sénateur (délégation de vote par groupe, cf. ci-dessus).
   */
  cohesionGroupe?: number;
  /** Nombre de scrutins publics où il a exprimé un vote. */
  votes: number;
  pour: number;
  contre: number;
  abstention: number;
}

/** Nature de ce sur quoi portait un vote (situe une entrée d'historique). */
export type ObjetVote = 'dossier' | 'amendement' | 'sous_amendement';

/** Un vote du député dans l'historique. */
export interface VoteDepute {
  scrutinId: string;
  date: string;
  objetType: ObjetVote;
  /** Titre clair du dossier, ou objet du vote d'amendement. */
  titre: string;
  /** Dossier à ouvrir au tap (absent si le vote n'en a pas). */
  dossierId?: string;
  position: PositionVote;
  /**
   * True si la position diffère de la majorité de son groupe sur ce scrutin.
   * Absent quand le groupe n'a pas de position majoritaire documentée (§2.5),
   * et TOUJOURS absent au Sénat (délégation de vote, cf. ci-dessus).
   */
  contreSonGroupe?: boolean;
}

/**
 * Fiche complète renvoyée par `GET /deputes/{id}`. `historique` est paginé
 * (du plus récent au plus ancien) : une page plus courte que la limite
 * demandée signale la fin de l'historique.
 */
export interface DeputeDetail extends Depute {
  portrait: PortraitVote;
  historique: VoteDepute[];
}

/** Groupe politique tel qu'exposé par les filtres de l'annuaire. */
export interface GroupeListItem {
  id: string;
  nom: string;
  abrev: string;
  couleur: string;
  chambre: Chambre;
}
