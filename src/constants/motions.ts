import type { TypeMotion } from '@/types';

/**
 * Ce qu'emporte l'adoption — ou le rejet — d'une motion (§7.4).
 *
 * Une motion **inverse le sens de son propre résultat** : voter *pour* une
 * motion de rejet préalable, c'est demander la mort du texte, et l'*adopter*,
 * c'est le rejeter. Affichés sans mention, le verdict (« Adopté »), l'écart de
 * voix et la ligne de fracture (« Ont voté pour ») se lisent donc tous à
 * l'envers. Ce fichier écrit la phrase qui le dit, **une seule fois**, pour les
 * trois surfaces qui en ont besoin : la fiche vote, la liste des votes d'un
 * dossier et le fil d'un parlementaire.
 *
 * ⚠️ Ce n'est **pas** un glossaire — `constants/glossaire.ts` reste maître des
 * définitions (règle 7), et `glossaireId` y renvoie pour la fiche complète. Ici
 * on ne porte que l'aide en ligne, là où le résultat s'affiche.
 *
 * Chaque phrase est factuelle et sans adjectif (§4.3) : elle énonce une règle de
 * procédure, jamais un jugement sur le vote. Une motion inconnue (`typeMotion`
 * absent) n'affiche rien du tout — on ne devine pas une conséquence (§2.5).
 */
export interface Motion {
  /** Nom du vote, employé comme titre de fiche et comme tag du fil. */
  libelle: string;
  /** Ce que l'adoption emporte — affiché quand `statut === 'adopte'`. */
  siAdoptee: string;
  /** Ce que le rejet emporte — affiché quand `statut === 'rejete'`. */
  siRejetee: string;
  /** Ce que « pour » veut dire ici, au-dessus des positions de groupe. */
  sensPour: string;
  /** Terme de `constants/glossaire.ts` portant la définition complète. */
  glossaireId: string;
}

export const MOTIONS: Record<TypeMotion, Motion> = {
  // Art. 91 du Règlement de l'Assemblée nationale.
  rejet_prealable: {
    libelle: 'Motion de rejet préalable',
    siAdoptee:
      'Adoptée, cette motion rejette le texte sans examen de ses articles.',
    siRejetee: 'Rejetée, cette motion laisse l’examen du texte se poursuivre.',
    sensPour:
      'Sur cette motion, voter « pour », c’est demander le rejet du texte.',
    glossaireId: 'motion-de-rejet-prealable',
  },
  // Art. 44 du Règlement du Sénat — l'équivalent sénatorial du rejet préalable.
  question_prealable: {
    libelle: 'Question préalable',
    siAdoptee: 'Adoptée, cette motion entraîne le rejet du texte.',
    siRejetee: 'Rejetée, cette motion laisse l’examen du texte se poursuivre.',
    sensPour:
      'Sur cette motion, voter « pour », c’est demander le rejet du texte.',
    glossaireId: 'question-prealable',
  },
  // Art. 44 du Règlement du Sénat également — le texte est jugé contraire à la
  // Constitution ou à une règle de recevabilité.
  exception_irrecevabilite: {
    libelle: 'Exception d’irrecevabilité',
    siAdoptee: 'Adoptée, cette motion entraîne le rejet du texte.',
    siRejetee: 'Rejetée, cette motion laisse l’examen du texte se poursuivre.',
    sensPour:
      'Sur cette motion, voter « pour », c’est demander le rejet du texte.',
    glossaireId: 'exception-d-irrecevabilite',
  },
  renvoi_en_commission: {
    libelle: 'Renvoi en commission',
    siAdoptee:
      'Adoptée, cette motion renvoie le texte en commission et interrompt son examen en séance.',
    siRejetee: 'Rejetée, cette motion laisse l’examen se poursuivre en séance.',
    sensPour:
      'Sur cette motion, voter « pour », c’est demander le renvoi du texte en commission.',
    glossaireId: 'renvoi-en-commission',
  },
  // Art. 122 du Règlement de l'Assemblée nationale.
  referendaire: {
    libelle: 'Motion référendaire',
    siAdoptee:
      'Adoptée, cette motion suspend l’examen du texte, qu’elle propose de soumettre au référendum.',
    siRejetee: 'Rejetée, cette motion laisse l’examen du texte se poursuivre.',
    sensPour:
      'Sur cette motion, voter « pour », c’est demander que le texte soit soumis au référendum.',
    glossaireId: 'motion-referendaire',
  },
  ajournement: {
    libelle: 'Motion d’ajournement',
    siAdoptee: 'Adoptée, cette motion reporte l’examen du texte.',
    siRejetee: 'Rejetée, cette motion laisse l’examen du texte se poursuivre.',
    sensPour:
      'Sur cette motion, voter « pour », c’est demander que l’examen du texte soit reporté.',
    glossaireId: 'motion-ajournement',
  },
};

/** La motion, si le vote en est une — sinon `undefined` (aucune mention, §2.5). */
export function motion(type?: TypeMotion): Motion | undefined {
  return type ? MOTIONS[type] : undefined;
}

/**
 * Ce que le résultat d'une motion emporte, selon son sort. C'est la phrase
 * affichée sous le verdict de la fiche vote.
 */
export function consequenceMotion(
  type: TypeMotion | undefined,
  statut: 'adopte' | 'rejete' | 'en_cours',
): string | undefined {
  const m = motion(type);
  if (!m || statut === 'en_cours') return undefined;
  return statut === 'adopte' ? m.siAdoptee : m.siRejetee;
}
