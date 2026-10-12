import type { ModaliteVote, StatutScrutin } from '@/types';

/**
 * Ce que l'app dit d'une décision prise SANS scrutin public (§5.2).
 *
 * Pour ces votes, la source ne donne que le résultat : ni décompte des voix, ni
 * position des groupes, ni liste des votants. Le lecteur doit comprendre
 * pourquoi ce détail manque — et que ce n'est pas une lacune de l'app — plutôt
 * que de chercher une barre de résultat qui n'existe pas. Ce fichier écrit ces
 * phrases **une seule fois**, pour toutes les surfaces : cartes du fil, liste
 * des votes d'un dossier, fiche vote, ligne d'amendement.
 *
 * Comme `constants/motions.ts`, ce n'est pas un glossaire : `glossaireId`
 * renvoie à la définition complète (`constants/glossaire.ts`, règle 7). Chaque
 * phrase énonce une règle de procédure, sans adjectif (§4.3).
 */
export interface Modalite {
  /** Titre du vote (fiche vote, liste des votes d'un dossier). */
  libelle: string;
  /** Mention courte, à la place d'une barre de résultat (cartes, listes). */
  mention: string;
  /** Pourquoi il n'y a ni décompte ni noms (fiche vote, vote décisif). */
  explication: (statut: StatutScrutin) => string;
  /** Terme de `constants/glossaire.ts` portant la définition complète. */
  glossaireId: string;
}

export const MODALITES: Record<ModaliteVote, Modalite> = {
  // Art. 64 du Règlement de l'Assemblée, art. 53 du Règlement du Sénat : la
  // main levée est la règle, le scrutin public l'exception demandée.
  main_levee: {
    libelle: 'Vote à main levée',
    mention: 'À main levée · pas de décompte des voix',
    explication: () =>
      'Ce vote s’est fait à main levée, sans scrutin public : le président de séance constate le résultat. Il n’existe ni décompte des voix, ni position des groupes, ni liste des votants.',
    glossaireId: 'vote-a-main-levee',
  },
  // Art. 49, alinéa 3, de la Constitution.
  article_49_3: {
    libelle: 'Sans vote : article 49.3',
    mention: 'Sans vote · article 49.3',
    explication: (statut) =>
      statut === 'rejete'
        ? 'Aucun vote n’a eu lieu sur ce texte : le Gouvernement a engagé sa responsabilité (article 49, alinéa 3, de la Constitution) et une motion de censure a été adoptée. Le texte est considéré comme rejeté.'
        : 'Aucun vote n’a eu lieu sur ce texte : le Gouvernement a engagé sa responsabilité (article 49, alinéa 3, de la Constitution) et aucune motion de censure n’a été adoptée. Le texte est considéré comme adopté.',
    glossaireId: 'article-49-3',
  },
  // Art. 151-7 du Règlement de l'Assemblée nationale.
  article_151_7: {
    libelle: 'Sans vote en séance : article 151-7',
    mention: 'Sans vote en séance · art. 151-7',
    explication: () =>
      'Cette résolution n’a pas été votée en séance : adoptée en commission, elle est devenue définitive sans que son examen en séance soit demandé (article 151-7 du Règlement de l’Assemblée nationale). Il n’existe donc ni décompte des voix ni liste des votants.',
    glossaireId: 'resolution-europeenne',
  },
};

export function modalite(type?: ModaliteVote): Modalite | undefined {
  return type ? MODALITES[type] : undefined;
}
