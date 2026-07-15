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

/** Fond pastel propre à chaque thème (repris de la maquette). */
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
