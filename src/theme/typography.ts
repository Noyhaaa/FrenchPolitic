import { Platform, TextStyle } from 'react-native';
import { colors } from './colors';

/** Famille serif d'affichage (titres éditoriaux — « Playfair » du prototype). */
export const serif = Platform.select({
  ios: 'Georgia',
  android: 'serif',
  default: 'serif',
});

/** Famille mono (métadonnées, décomptes, en-têtes de section du prototype). */
export const mono = Platform.select({
  ios: 'Menlo',
  android: 'monospace',
  default: 'monospace',
});

/**
 * Échelle typographique « grand public » : phrases courtes, lisibilité
 * prioritaire (cf. §8 « Langue simple » du MVP). Trois registres, comme le
 * prototype : serif pour les titres, sans-serif pour le corps, mono pour les
 * métadonnées (dates, décomptes, en-têtes de section).
 */
export const typography: Record<string, TextStyle> = {
  display: {
    fontSize: 28,
    lineHeight: 34,
    fontWeight: '800',
    fontFamily: serif,
    color: colors.textPrimary,
  },
  hero: {
    fontSize: 26,
    lineHeight: 32,
    fontWeight: '700',
    fontFamily: serif,
    color: colors.textPrimary,
  },
  title: {
    fontSize: 21,
    lineHeight: 27,
    fontWeight: '700',
    fontFamily: serif,
    color: colors.textPrimary,
  },
  cardTitle: {
    fontSize: 16,
    lineHeight: 21,
    fontWeight: '700',
    fontFamily: serif,
    color: colors.textPrimary,
  },
  sectionTitle: {
    fontSize: 16,
    lineHeight: 22,
    fontWeight: '700',
    letterSpacing: -0.2,
    color: colors.textPrimary,
  },
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
