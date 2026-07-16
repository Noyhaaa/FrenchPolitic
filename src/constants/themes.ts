import { ThemeScrutin } from '@/types';

/** Emoji d'illustration par thème (partagé carte + avatar). */
export const themeEmoji: Record<ThemeScrutin, string> = {
  Logement: '🏠',
  Santé: '🏥',
  Fiscalité: '💶',
  Énergie: '⚡',
  Éducation: '🏫',
  Environnement: '🌱',
  Justice: '⚖️',
  Travail: '🧰',
  Autre: '🏛️',
};

/** Fond pastel propre à chaque thème (petites pastilles / avatars). */
export const themeTint: Record<ThemeScrutin, string> = {
  Logement: '#E7EBF4',
  Santé: '#E2EFE4',
  Fiscalité: '#EFE7DA',
  Énergie: '#F8F0D3',
  Éducation: '#F4E4DE',
  Environnement: '#E2EFE4',
  Justice: '#EAE6F2',
  Travail: '#EFE7DA',
  Autre: '#EDE9E0',
};

/**
 * Teinte profonde par thème pour les grandes tuiles du fil (hero, cartes-vignette).
 * On n'a pas d'images par dossier (on n'invente rien, §2.5) : la tuile est un
 * dégradé de couleur + emoji du thème, en remplacement de la photo des maquettes.
 */
export const themeTintDark: Record<ThemeScrutin, string> = {
  Logement: '#1E2A44',
  Santé: '#123026',
  Fiscalité: '#33291A',
  Énergie: '#3A3113',
  Éducation: '#3A2320',
  Environnement: '#153020',
  Justice: '#2A2340',
  Travail: '#2E2A18',
  Autre: '#24262C',
};
