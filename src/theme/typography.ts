import { Platform, TextStyle } from 'react-native';
import { colors } from './colors';

/**
 * Familles Newsreader — antiqua de presse pensée pour la lecture longue.
 * Chargées au démarrage via `@expo-google-fonts/newsreader` (voir App.tsx).
 *
 * ⚠️ En React Native, avec une police custom, on ne s'appuie PAS sur
 * `fontWeight` : chaque graisse est une **famille distincte**. On sélectionne
 * donc la bonne famille au lieu de jouer sur le poids.
 */
export const serifDisplay = 'Newsreader_700Bold'; // titres d'affichage
export const serifDisplaySemi = 'Newsreader_600SemiBold'; // titres secondaires
export const serifText = 'Newsreader_400Regular'; // paragraphes de lecture
export const serifItalic = 'Newsreader_500Medium_Italic'; // citations attribuées

/** Rétrocompat : l'ancien nom `serif` = graisse d'affichage. */
export const serif = serifDisplay;

/** Famille mono (métadonnées, décomptes, en-têtes de section). */
export const mono = Platform.select({
  ios: 'Menlo',
  android: 'monospace',
  default: 'monospace',
});

/**
 * Échelle typographique « grand public ». Nouveauté : deux styles de LECTURE
 * (`readingBody`, `readingQuote`) en serif de labeur, un peu plus grands et
 * aérés que le corps d'UI — c'est eux qui donnent envie de lire (§8).
 */
export const typography: Record<string, TextStyle> = {
  display: {
    fontSize: 28,
    lineHeight: 34,
    fontFamily: serifDisplay,
    color: colors.textPrimary,
  },
  hero: {
    fontSize: 26,
    lineHeight: 32,
    fontFamily: serifDisplay,
    color: colors.textPrimary,
  },
  title: {
    fontSize: 22,
    lineHeight: 28,
    fontFamily: serifDisplay,
    color: colors.textPrimary,
  },
  cardTitle: {
    fontSize: 16,
    lineHeight: 21,
    fontFamily: serifDisplaySemi,
    color: colors.textPrimary,
  },
  sectionTitle: {
    fontSize: 16,
    lineHeight: 22,
    fontWeight: '700',
    letterSpacing: -0.2,
    color: colors.textPrimary,
  },
  // Corps d'UI (labels, notes secondaires) — reste en sans système.
  body: {
    fontSize: 15,
    lineHeight: 22,
    fontWeight: '400',
    color: colors.textPrimary,
  },
  bodySecondary: {
    fontSize: 14,
    lineHeight: 20,
    fontWeight: '400',
    color: colors.textSecondary,
  },
  // --- LECTURE : serif de labeur (dispositif, résumé, réponses) ---
  readingBody: {
    fontSize: 16,
    lineHeight: 26,
    fontFamily: serifText,
    color: colors.textPrimary,
  },
  readingQuote: {
    fontSize: 16,
    lineHeight: 27,
    fontFamily: serifItalic,
    fontStyle: 'italic',
    color: colors.textSecondary,
  },
  label: {
    fontSize: 13,
    lineHeight: 18,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  meta: {
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '500',
    fontFamily: mono,
    color: colors.textTertiary,
  },
  badge: {
    fontSize: 10,
    lineHeight: 14,
    fontWeight: '700',
    fontFamily: mono,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  overline: {
    fontSize: 11,
    lineHeight: 14,
    fontWeight: '700',
    fontFamily: mono,
    letterSpacing: 1.4,
    textTransform: 'uppercase',
    color: colors.miniLabel,
  },
};
