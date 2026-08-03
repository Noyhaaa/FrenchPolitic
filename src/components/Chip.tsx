import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

/**
 * Pastille sélectionnable — filtres de l'annuaire, thèmes du parcours d'accueil.
 *
 * Une seule définition pour toute l'app : la sélection s'y lit toujours de la
 * même façon (fond clair + texte sombre), et l'état est porté par
 * `accessibilityState`, pas par la seule couleur (RGAA, §8).
 *
 * La `couleur` optionnelle est une **pastille** (couleur d'un groupe politique,
 * teinte d'un thème) posée à gauche du libellé ; elle ne remplace jamais le
 * libellé.
 */

interface Props {
  actif: boolean;
  label: string;
  onPress: () => void;
  /** Pastille de couleur (groupe, thème). */
  couleur?: string;
  /** Emoji décoratif à gauche (thèmes) — ignoré par les lecteurs d'écran. */
  emoji?: string;
  /** Ce que fait le tap, pour un lecteur d'écran (« Filtrer : … »). */
  action?: string;
  /** Chip plus généreux, pour une grille de choix plutôt qu'une barre de filtres. */
  large?: boolean;
  /** Décompte servi par l'API (dossiers d'un thème, élus d'un groupe). */
  compteur?: number;
}

export function Chip({
  actif,
  label,
  onPress,
  couleur,
  emoji,
  action = 'Filtrer',
  large = false,
  compteur,
}: Props) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.chip, large && styles.chipLarge, actif && styles.chipActif]}
      accessibilityRole="button"
      accessibilityState={{ selected: actif }}
      accessibilityLabel={
        compteur === undefined ? `${action} : ${label}` : `${action} : ${label}, ${compteur} dossiers`
      }
    >
      {couleur ? (
        <View
          style={[styles.pastille, { backgroundColor: couleur }]}
          importantForAccessibility="no"
        />
      ) : null}
      {emoji ? (
        <Text style={styles.emoji} importantForAccessibility="no">
          {emoji}
        </Text>
      ) : null}
      <Text style={[styles.texte, large && styles.texteLarge, actif && styles.texteActif]}>
        {label}
      </Text>
      {compteur === undefined ? null : (
        <Text style={[styles.compteur, actif && styles.compteurActif]} importantForAccessibility="no">
          {compteur}
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    paddingVertical: 6,
    paddingHorizontal: 13,
  },
  chipLarge: { paddingVertical: spacing.md - 2, paddingHorizontal: spacing.lg },
  chipActif: { backgroundColor: colors.textPrimary },
  pastille: { width: 8, height: 8, borderRadius: 4 },
  emoji: { fontSize: 14 },
  texte: { ...typography.label, color: colors.textSecondary },
  texteLarge: { fontSize: 14 },
  texteActif: { color: colors.textOnLight },
  compteur: { ...typography.meta, color: colors.textTertiary },
  compteurActif: { color: colors.textOnLight },
});
