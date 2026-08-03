import {
  Amendement,
  Chambre,
  ObjetVote,
  PositionVote,
  ScrutinResume,
  StatutScrutin,
  TypeMotion,
  TypeVote,
} from '@/types';
import { MOTIONS } from '@/constants/motions';

/** Libellé texte du statut (jamais la couleur seule — RGAA §8). */
export function statutLabel(statut: StatutScrutin): string {
  switch (statut) {
    case 'adopte':
      return 'Adopté';
    case 'rejete':
      return 'Rejeté';
    case 'en_cours':
      return 'En discussion';
  }
}

/**
 * Le badge d'un dossier : son libellé et le statut qui lui donne sa couleur.
 *
 * `statut` est le sort du **dernier vote** du dossier. Trois cas, dans cet
 * ordre :
 *
 * 1. **loi promulguée** → « Promulguée ». « Adopté » est exact mais laisse
 *    croire que le texte est encore en chemin, alors que la source dit qu'il
 *    est arrivé au bout. (`etat` n'est servi que sur la fiche : dans le fil,
 *    `DossierListItem` ne le porte pas, et le badge reste celui du vote.)
 * 2. **le dernier vote est une MOTION** → « Motion adoptée » / « Motion
 *    rejetée ». Une motion inverse la lecture de son résultat : une motion de
 *    rejet préalable adoptée **rejette** le texte. Mesuré : 8 dossiers
 *    annonçaient « Adopté » sur un texte que la motion venait de rejeter, dont
 *    un dont c'était le seul vote — et la frise de la même fiche disait
 *    « 1ère lecture · Rejeté » deux centimètres plus bas. On **nomme le vote**
 *    plutôt que d'affirmer un sort du texte que ce seul vote ne décide pas :
 *    un rejet en 1re lecture n'empêche pas la navette de continuer (§7.4).
 * 3. sinon le statut, tel quel.
 *
 * Un seul endroit décide, pour les quatre surfaces qui affichent ce badge
 * (carte du fil, tuile, hero, tête de fiche) — sinon elles divergeraient.
 */
export function badgeDossier(dossier: {
  statut: StatutScrutin;
  statutMotion?: TypeMotion;
  phase?: { label?: string; statut?: StatutScrutin } | null;
  etat?: { etat?: string } | null;
}): { statut: StatutScrutin; label: string } {
  if (dossier.etat?.etat === 'promulgue') {
    return { statut: 'adopte', label: 'Promulguée' };
  }
  if (dossier.statutMotion) {
    return {
      statut: dossier.statut,
      label: dossier.statut === 'adopte' ? 'Motion adoptée' : 'Motion rejetée',
    };
  }
  const statut = dossier.phase?.statut ?? dossier.statut;
  return { statut, label: dossier.phase?.label ?? statutLabel(statut) };
}

export function positionLabel(position: PositionVote): string {
  switch (position) {
    case 'pour':
      return 'Pour';
    case 'contre':
      return 'Contre';
    case 'abstention':
      return 'Abstention';
    case 'non_votant':
      return 'Non-votant';
  }
}

/** Date relative simple et lisible (« Aujourd'hui », « Hier », « 6 juil. »). */
export function formatDateRelative(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const startOf = (x: Date) =>
    new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.round((startOf(now) - startOf(d)) / 86_400_000);

  if (diffDays <= 0) return "Aujourd'hui";
  if (diffDays === 1) return 'Hier';
  if (diffDays < 7) return `Il y a ${diffDays} jours`;

  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}

/** « 8 juil. 2026 » (sous-titre de la fiche). */
export function formatDateLong(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

/** « ~30 s de lecture ». */
export function formatTempsLecture(sec: number): string {
  if (sec < 60) return `~${sec} s de lecture`;
  const min = Math.round(sec / 60);
  return `~${min} min de lecture`;
}

/**
 * « 312 pour · 220 contre » (micro-résultat des cartes, §3.1).
 *
 * ⚠️ **Motion de censure** : l'article 49 de la Constitution ne fait recenser
 * que les voix FAVORABLES, donc `contre` y vaut 0 par construction. « 267 pour
 * · 0 contre » se lirait comme une unanimité alors que les opposants ne sont
 * pas comptés — on montre les voix recueillies face au seuil, seul rapport qui
 * décide (§7.4). Sans seuil connu, on s'en tient aux voix (§2.5).
 */
export function formatMicroResultat(
  pour: number,
  contre: number,
  typeVote?: TypeVote,
  suffragesRequis?: number,
): string {
  if (typeVote === 'motion_censure') {
    return suffragesRequis
      ? `${pour} voix pour · ${suffragesRequis} requises`
      : `${pour} voix pour`;
  }
  return `${pour} pour · ${contre} contre`;
}

/** Minuscules sans accents (miroir de `fold` côté backend), apostrophe droite. */
export function plier(texte: string): string {
  return texte
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/’/g, "'")
    .toLowerCase();
}

/**
 * Libellé compact d'un scrutin : le **type** du vote en clair, plus une
 * mention de contexte (lecture…) quand le libellé officiel la contient.
 * L'objet officiel complet reste la référence (affiché sur la fiche vote).
 */
export interface LibelleScrutin {
  /** Ce qu'est le vote : « Vote sur l'ensemble », « Motion de censure »… */
  titre: string;
  /** Mention extraite du libellé officiel (« Première lecture »…). */
  complement?: string;
}

/** Mentions de contexte reconnues dans les objets officiels. */
const MENTIONS_SCRUTIN: ReadonlyArray<[RegExp, string]> = [
  [/premiere lecture/, 'Première lecture'],
  [/deuxieme lecture/, 'Deuxième lecture'],
  [/troisieme lecture/, 'Troisième lecture'],
  [/nouvelle lecture/, 'Nouvelle lecture'],
  [/lecture definitive/, 'Lecture définitive'],
  [/commission mixte paritaire/, 'Commission mixte paritaire'],
  [/premiere partie/, 'Première partie'],
  [/seconde partie/, 'Seconde partie'],
];

/**
 * Type d'un vote à partir de son objet officiel, pour que l'utilisateur
 * comprenne en un coup d'œil **ce sur quoi** porte le vote (§3.2, §8 langue
 * simple). Reformule uniquement des tournures officielles connues ; tout objet
 * non reconnu est restitué tel quel — on n'invente rien (§2.5).
 */
export function libelleScrutin(
  objet: string,
  typeMotion?: TypeMotion,
): LibelleScrutin {
  const t = plier(objet);
  const numero = (re: RegExp) => t.match(re)?.[1];

  // Le classement fait à l'ingestion PRIME sur l'heuristique de texte : il a lu
  // l'objet ENTIER, là où celui qu'on reçoit est tronqué à 120 caractères. Un
  // objet du Sénat s'ouvre sur le numéro et l'auteur de la motion et ne dit
  // qu'au 135e caractère ce qu'elle est — sans ce raccourci, ces 23 votes
  // resteraient affichés sous forme de chaîne coupée, sans nom ni définition.
  let titre: string | undefined = typeMotion
    ? MOTIONS[typeMotion].libelle
    : undefined;
  if (titre) {
    // rien à deviner : le titre est déjà connu
  } else if (t.includes('sous-amendement')) {
    const n = numero(/sous-amendements?[^,]*?n[°o]\s*(\d+)/);
    titre = n ? `Sous-amendement n° ${n}` : undefined;
  } else if (t.includes('amendement')) {
    const n = numero(/amendements?[^,]*?n[°o]\s*(\d+)/);
    titre = n ? `Amendement n° ${n}` : undefined;
  } else if (t.includes('motion de censure')) {
    titre = 'Motion de censure';
  } else if (t.includes('motion de rejet prealable')) {
    titre = 'Motion de rejet préalable';
  } else if (t.includes('motion referendaire')) {
    titre = 'Motion référendaire';
  } else if (t.includes("motion d'ajournement")) {
    titre = "Motion d'ajournement";
  } else if (t.includes("l'article unique")) {
    // Texte mono-article : ce vote est le vote sur le texte lui-même.
    titre = 'Article unique';
  } else if (/\barticle premier\b/.test(t)) {
    titre = 'Article 1er';
  } else if (numero(/\bl'article (\d+)/)) {
    titre = `Article ${numero(/\bl'article (\d+)/)}`;
  } else if (t.includes("l'ensemble")) {
    titre = "Vote sur l'ensemble";
  } else if (t.includes('credits de la mission')) {
    const mission = objet.match(/mission\s*«\s*([^»]+?)\s*»/)?.[1];
    titre = mission ? `Crédits de la mission « ${mission} »` : undefined;
  } else if (t.includes('declaration')) {
    titre = 'Déclaration du Gouvernement';
  }

  // Objet non reconnu → restitué tel quel, sans mention (déjà incluse dedans).
  if (!titre) return { titre: objet };

  const mentions = MENTIONS_SCRUTIN.filter(([re]) => re.test(t)).map(
    ([, label]) => label,
  );
  return { titre, complement: mentions.join(' · ') || undefined };
}

/**
 * Nature d'un texte de loi d'après son titre officiel (« Projet de loi… »),
 * pour situer le dossier d'un coup d'œil. Absent si le titre ne commence pas
 * par une nature connue (titres clairs du seed, par ex.) — on ne déduit pas.
 */
export function natureTexte(titre: string): string | undefined {
  const t = plier(titre);
  if (t.startsWith('projet de loi organique')) return 'Projet de loi organique';
  if (t.startsWith('projet de loi')) return 'Projet de loi';
  if (t.startsWith('proposition de loi organique'))
    return 'Proposition de loi organique';
  if (t.startsWith('proposition de loi')) return 'Proposition de loi';
  if (t.startsWith('proposition de resolution'))
    return 'Proposition de résolution';
  return undefined;
}

/**
 * Nom d'une chambre du Parlement, tel qu'on l'écrit à l'écran.
 *
 * Un dossier agrège désormais les votes des deux assemblées : chaque vote et
 * chaque étape de navette doit dire d'où elle vient, sinon « 214 pour » se lit
 * comme un vote de l'Assemblée alors que c'en est un du Sénat (§2.5).
 */
export function libelleChambre(chambre: Chambre): string {
  return chambre === 'senat' ? 'Sénat' : 'Assemblée nationale';
}

/** Variante courte, pour les vignettes et les lignes de liste. */
export function libelleChambreCourt(chambre: Chambre): string {
  return chambre === 'senat' ? 'Sénat' : 'Assemblée nat.';
}

/**
 * Le vote DÉCISIF d'un dossier : le vote sur l'ensemble du texte le plus
 * récent (la liste arrive triée du plus récent au plus ancien) — c'est lui qui
 * scelle l'adoption ou le rejet, contrairement aux votes d'articles ou aux
 * motions. Miroir de `_vote_decisif` côté backend. undefined si le texte n'a
 * pas (encore) été voté dans son ensemble — on ne désigne alors rien (§2.5).
 */
export function voteDecisif(scrutins: ScrutinResume[]): ScrutinResume | undefined {
  return scrutins.find((s) => plier(s.objet).includes('ensemble'));
}

/** Le vote porte-t-il sur un amendement (ou sous-amendement) ? Miroir de
 * `est_amendement` côté backend (heuristique sur l'objet officiel). */
export function estVoteAmendement(objet: string): boolean {
  return plier(objet).includes('amendement');
}

/** Le vote porte-t-il sur un sous-amendement ? Miroir de `est_sous_amendement`. */
export function estVoteSousAmendement(objet: string): boolean {
  return plier(objet).includes('sous-amendement');
}

/**
 * Partie descriptive de l'objet officiel, à afficher sous le titre compact.
 * Évite de répéter « l'amendement n° X de M. Y » (déjà porté par le titre et
 * le champ auteur) : on garde ce qui suit un tiret, sinon rien si l'objet
 * n'est que la formule d'usage. Tout reste un extrait du libellé officiel.
 */
export function detailObjetAmendement(a: Amendement): string {
  if (!a.numero) return ''; // le titre affiche déjà l'objet complet
  const sep = a.objet.search(/\s[—–]\s/);
  if (sep >= 0) return a.objet.slice(sep).replace(/^\s[—–]\s/, '');
  return /^\s*(l['’]|les?\s|la\s)?(sous-)?amendements?\b/i.test(a.objet)
    ? ''
    : a.objet;
}

/**
 * Repère compact de l'article visé pour une ligne d'amendement : « Article 2 »
 * → « Art. 2 ». Tout libellé qui n'est pas un article (« ÉTAT B »…) est
 * restitué tel quel, en casse d'origine — on n'invente pas de forme courte
 * pour ce qu'on ne reconnaît pas (§2.5).
 */
export function cibleCourte(cible: string): string {
  const t = cible.trim();
  return /^articles?\s+/i.test(t) ? t.replace(/^articles?\s+/i, 'Art. ') : t;
}

/** Une substitution de valeur repérée dans le dispositif officiel. */
export interface SubstitutionValeur {
  avant: string;
  apres: string;
}

/**
 * Termes de la formule officielle de substitution. C'est le texte lui-même qui
 * dit qu'on remplace une VALEUR (« substituer au taux : … ») : on ne s'appuie
 * pas sur l'allure du contenu. Une substitution de mots (« substituer aux
 * mots : … ») n'est pas une valeur et retombe sur l'affichage brut.
 */
const TERME_VALEUR =
  '(?:taux|nombres?|montants?|chiffres?|sommes?|dates?|années?)';

const RE_SUBSTITUTION = new RegExp(
  `substituer\\s+aux?\\s+${TERME_VALEUR}\\s*:?\\s*[«"]\\s*([^»"]+?)\\s*[»"]\\s*,?\\s*` +
    `(?:les?|la|aux?)\\s+(?:${TERME_VALEUR}|mots?)\\s*:?\\s*[«"]\\s*([^»"]+?)\\s*[»"]`,
  'i',
);

/**
 * Extrait l'« avant → après » d'un dispositif quand il applique la formule
 * officielle de substitution (« substituer au taux : « 20 % » le taux :
 * « 25 % » »). Les deux valeurs sont des **extraits verbatim** du texte
 * officiel : rien n'est reformulé, et on ne renvoie rien dès que la lecture
 * n'est pas certaine (§2.5) — pas de chiffre dans la valeur remplacée, ou
 * termes trop longs pour tenir la comparaison, qui s'affichent alors tels quels.
 */
export function substitutionValeur(
  dispositif: string,
): SubstitutionValeur | undefined {
  const m = RE_SUBSTITUTION.exec(dispositif.replace(/\s+/g, ' '));
  if (!m) return undefined;
  const [, avant, apres] = m;
  if (avant.length > 24 || apres.length > 24) return undefined;
  if (!/\d/.test(avant)) return undefined;
  return { avant, apres };
}

/** Marqueurs d'énumération du texte législatif : « I. – », « 1° », « a) ». */
const RE_POINT = /^\s*(?:[IVX]+\s*[.°]|\d+°|[a-z]\))\s*[–—-]?\s*/;

/**
 * Découpe un dispositif en ses instructions successives quand il en énumère
 * plusieurs (« I. – … », « II. – En conséquence, … », « 1° … »). Chaque point
 * est un **extrait verbatim**, marqueur retiré. Renvoie `[]` si le dispositif
 * n'énumère rien : il s'affiche alors d'un seul tenant.
 */
export function pointsDispositif(dispositif: string): string[] {
  const points = dispositif
    .split(/\n+/)
    .map((l) => l.trim())
    .filter(Boolean)
    .reduce<string[]>((acc, ligne) => {
      // Une ligne sans marqueur poursuit le point précédent (citations « … »).
      if (RE_POINT.test(ligne) || acc.length === 0) acc.push(ligne);
      else acc[acc.length - 1] += ` ${ligne}`;
      return acc;
    }, []);
  const marques = points.filter((p) => RE_POINT.test(p));
  if (marques.length < 2) return [];
  return points.map((p) => p.replace(RE_POINT, '').trim()).filter(Boolean);
}

/** Première lettre en capitale — `toLocaleDateString('fr-FR')` rend les mois en
 *  minuscules, alors qu'ils ouvrent un en-tête ou un libellé de période. */
export function capitale(texte: string): string {
  return texte.charAt(0).toUpperCase() + texte.slice(1);
}

/** « Juillet 2026 » — en-tête de mois du fil de votes d'un député. */
export function moisAnnee(iso: string): string {
  return capitale(
    new Date(iso).toLocaleDateString('fr-FR', {
      month: 'long',
      year: 'numeric',
    }),
  );
}

/**
 * « Juillet 2026 » à partir d'une année et d'un mois **1–12** (le récap mensuel
 * les sert ainsi, pas en ISO).
 *
 * Un mois hors bornes n'est pas « corrigé » silencieusement : `new Date` le
 * ferait déborder sur l'année suivante et afficherait un mois que la source ne
 * dit pas (§2.5). On rend alors le nombre brut, comme avant.
 */
export function libelleMoisAnnee(annee: number, mois: number): string {
  if (mois < 1 || mois > 12) return `${mois} ${annee}`;
  return capitale(
    new Date(annee, mois - 1, 1).toLocaleDateString('fr-FR', {
      month: 'long',
      year: 'numeric',
    }),
  );
}

/**
 * Ce qu'a fait le député sur ce scrutin, dit en clair. Purement descriptif :
 * on rapporte le sens du vote officiel, on ne le qualifie pas (§7.4).
 */
export function libellePositionVotee(position: PositionVote): string {
  switch (position) {
    case 'pour':
      return 'A voté pour';
    case 'contre':
      return 'A voté contre';
    case 'abstention':
      return "S'est abstenu";
    case 'non_votant':
      return "N'a pas pris part au vote";
  }
}

/** Nature de ce sur quoi portait le vote (repère du fil). */
export function libelleObjetVote(type: ObjetVote): string {
  switch (type) {
    case 'dossier':
      return 'Dossier';
    case 'amendement':
      return 'Amendement';
    case 'sous_amendement':
      return 'Sous-amend.';
  }
}
