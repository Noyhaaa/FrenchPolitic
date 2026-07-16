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

export type NiveauConfiance = 'haute' | 'moyenne' | 'faible';

export type ThemeScrutin =
  | 'Logement'
  | 'Santé'
  | 'Fiscalité'
  | 'Énergie'
  | 'Éducation'
  | 'Environnement'
  | 'Justice'
  | 'Travail'
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
   * Vote nominatif (§5.2, scrutins publics uniquement) : noms des députés du
   * groupe par position. Absent si la donnée n'est pas fournie par la source
   * (§2.5 : on n'invente pas — le bloc est alors masqué).
   */
  nomsPour?: string[];
  nomsContre?: string[];
  nomsAbstention?: string[];
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
 * Résumé neutre du texte, généré et ancré aux sources (§4).
 * `champsNonDocumentes` liste les champs non renseignés par les sources
 * (règle d'or §2.5 : « information non disponible », jamais de supposition).
 */
export interface ResumeScrutin {
  titreClair: string;
  resume: PhraseSourcee[];
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
 * Étape précise de la navette affichée sur la fiche
 * (ex. « Adopté en 1re lecture » alors que le fil affiche « En discussion »).
 */
export interface PhaseScrutin {
  label: string;
  /** Statut utilisé pour le style du badge. */
  statut: StatutScrutin;
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
  /** Ce sur quoi les députés ont voté (objet du scrutin). */
  objet: string;
  statut: StatutScrutin;
  /** true = scrutin public (vote nominatif dispo), false = à main levée (§5.2). */
  scrutinPublic: boolean;
  resultat: ResultatGlobal;
  positionsGroupes: PositionGroupe[];
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
  titreClair: string;
  /** Description courte affichée sur la carte du fil (1-2 lignes). */
  accroche: string;
  statut: StatutScrutin;
  phase?: PhaseScrutin;
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
  accroche: string;
  statut: StatutScrutin;
  theme: ThemeScrutin;
  tempsLectureSec: number;
  /** Nombre de scrutins rattachés (affiché sur la carte). */
  nombreScrutins: number;
  miseAJour?: MiseAJourDossier;
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
 * Écran d'accueil complet, servi en UNE réponse (miroir backend).
 * Construit côté serveur pour un affichage atomique — pas de remplissage
 * progressif des rangées. « Aujourd'hui » / « Hier » vides hors jours de
 * séance (rangée masquée, §2.5).
 */
export interface Accueil {
  aLaUne: DossierListItem | null;
  aujourdhui: DossierListItem[];
  hier: DossierListItem[];
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
