import { TextStyle } from 'react-native';
import { colors } from './colors';

/**
 * Échelle typographique « grand public » : phrases courtes, lisibilité
 * prioritaire (cf. §8 « Langue simple » du MVP).
 */
export const typography: Record<string, TextStyle> = {
  hero: {
    fontSize: 26,
    lineHeight: 32,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  title: {
    fontSize: 20,
    lineHeight: 26,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  cardTitle: {
    fontSize: 17,
    lineHeight: 23,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  sectionTitle: {
    fontSize: 16,
    lineHeight: 22,
    fontWeight: '700',
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
    fontSize: 12,
    lineHeight: 16,
    fontWeight: '500',
    color: colors.textTertiary,
  },
  badge: {
    fontSize: 12,
    lineHeight: 16,
    fontWeight: '700',
  },
  overline: {
    fontSize: 11,
    lineHeight: 14,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    color: colors.textTertiary,
  },
};
