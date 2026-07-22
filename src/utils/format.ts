import { Amendement, ScrutinResume, StatutScrutin, PositionVote } from '@/types';

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

/** « 312 pour · 220 contre » (micro-résultat des cartes, §3.1). */
export function formatMicroResultat(pour: number, contre: number): string {
  return `${pour} pour · ${contre} contre`;
}

/** Minuscules sans accents (miroir de `fold` côté backend), apostrophe droite. */
function plier(texte: string): string {
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
export function libelleScrutin(objet: string): LibelleScrutin {
  const t = plier(objet);
  const numero = (re: RegExp) => t.match(re)?.[1];

  let titre: string | undefined;
  if (t.includes('sous-amendement')) {
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

/** Phases de la navette reconnues dans les objets officiels des votes AN.
 * (Les « parties » du budget ne sont pas des phases de navette — exclues.) */
const PHASES_NAVETTE: ReadonlyArray<[RegExp, string]> = [
  [/premiere lecture/, 'Première lecture'],
  [/deuxieme lecture/, 'Deuxième lecture'],
  [/troisieme lecture/, 'Troisième lecture'],
  [/commission mixte paritaire/, 'Commission mixte paritaire'],
  [/nouvelle lecture/, 'Nouvelle lecture'],
  [/lecture definitive/, 'Lecture définitive'],
];

/** Une étape de la trajectoire du texte À L'ASSEMBLÉE (frise de la fiche). */
export interface PhaseNavette {
  label: string;
  /** Statut du vote sur l'ensemble de cette phase — absent si la phase n'a pas
   * (encore) de vote d'ensemble documenté (§2.5 : on n'infère pas). */
  statut?: StatutScrutin;
  /** Date du vote le plus récent de la phase (ISO). */
  date: string;
}

/**
 * Trajectoire du texte à l'Assemblée : les phases de navette que les libellés
 * officiels des votes documentent, dans l'ordre chronologique. 100 % factuel :
 * une phase n'apparaît que si un vote la mentionne, et son statut ne vient que
 * du vote sur l'ensemble de cette phase. Les étapes hors AN (Sénat) ne sont
 * pas couvertes par nos données — elles ne sont donc pas affichées (§2.5).
 * Vide si aucun vote ne porte de mention de phase.
 */
export function phasesNavette(scrutins: ScrutinResume[]): PhaseNavette[] {
  const parLabel = new Map<string, PhaseNavette & { ordre: number }>();
  // La liste arrive du plus récent au plus ancien → on remonte le fil.
  const chrono = [...scrutins].reverse();
  chrono.forEach((s, ordre) => {
    const t = plier(s.objet);
    for (const [re, label] of PHASES_NAVETTE) {
      if (!re.test(t)) continue;
      const estEnsemble = t.includes('ensemble');
      const connu = parLabel.get(label);
      if (!connu) {
        parLabel.set(label, {
          label,
          date: s.date,
          ordre,
          statut: estEnsemble ? s.statut : undefined,
        });
      } else {
        connu.date = s.date;
        if (estEnsemble) connu.statut = s.statut;
      }
    }
  });
  return [...parLabel.values()]
    .sort((a, b) => a.ordre - b.ordre)
    .map(({ ordre: _ordre, ...phase }) => phase);
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

/** Titre compact d'un amendement : « Amendement n° 80 » (ou l'objet complet
 * quand le numéro n'a pas pu être identifié — on n'invente pas, §2.5). */
export function titreAmendement(a: Amendement, sous = false): string {
  if (!a.numero) return a.objet;
  return `${sous ? 'Sous-amendement' : 'Amendement'} n° ${a.numero}`;
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
