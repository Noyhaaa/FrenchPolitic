import { Amendement, StatutScrutin, PositionVote } from '@/types';

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
