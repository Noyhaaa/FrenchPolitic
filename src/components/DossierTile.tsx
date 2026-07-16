import { Pressable, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { colors, radius, spacing, typography } from '@/theme';
import { DossierListItem } from '@/types';
import { themeEmoji, themeTintDark } from '@/constants/themes';
import { formatDateRelative } from '@/utils/format';
import { StatusBadge } from './StatusBadge';
import { MiniResultat } from './MiniResultat';

interface Props {
  dossier: DossierListItem;
  onPress: (dossier: DossierListItem) => void;
}

/** Largeur fixe des vignettes des carrousels (prototype : 200). */
export const TILE_WIDTH = 200;

/**
 * Vignette des carrousels horizontaux du fil (la « VoteCard » du prototype).
 * À défaut de photo (on n'invente pas d'illustration, §2.5), la vignette est
 * une tuile teintée par thème + emoji, fondue dans la carte par un dégradé.
 * Contenu factuel : statut, titre, résultat du dernier vote nominatif, date.
 */
export function DossierTile({ dossier, onPress }: Props) {
  return (
    <Pressable
      onPress={() => onPress(dossier)}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      accessibilityRole="button"
      accessibilityLabel={`${dossier.titreClair}. Thème ${dossier.theme}.`}
    >
      <View
        style={[
          styles.tile,
          { backgroundColor: themeTintDark[dossier.theme] ?? themeTintDark.Autre },
        ]}
      >
        <Text style={styles.emoji} importantForAccessibility="no">
          {themeEmoji[dossier.theme] ?? themeEmoji.Autre}
        </Text>
        {/* Fondu de la vignette vers la carte (prototype). */}
        <LinearGradient
          colors={['transparent', colors.surface]}
          style={styles.fade}
        />
        <View style={styles.badgeStatut}>
          <StatusBadge statut={dossier.statut} />
        </View>
        <View style={styles.badgeTheme} accessibilityElementsHidden>
          <Text style={styles.badgeThemeText}>{dossier.theme}</Text>
        </View>
      </View>

      <View style={styles.body}>
        <Text style={[typography.cardTitle, styles.title]} numberOfLines={2}>
          {dossier.titreClair}
        </Text>
        {dossier.resultatDernierScrutin ? (
          <MiniResultat resultat={dossier.resultatDernierScrutin} height={4} />
        ) : null}
        <View style={styles.footer}>
          <Text style={typography.meta}>Assemblée nat.</Text>
          <Text style={typography.meta}>{formatDateRelative(dossier.date)}</Text>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    width: TILE_WIDTH,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    overflow: 'hidden',
  },
  pressed: {
    opacity: 0.85,
    transform: [{ scale: 0.97 }],
  },
  tile: {
    height: 112,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emoji: {
    fontSize: 44,
    opacity: 0.85,
  },
  fade: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: 64,
  },
  badgeStatut: {
    position: 'absolute',
    top: spacing.sm,
    left: spacing.sm,
  },
  badgeTheme: {
    position: 'absolute',
    bottom: spacing.sm,
    right: spacing.sm,
    backgroundColor: colors.overlay,
    borderRadius: radius.sm,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
  },
  badgeThemeText: {
    ...typography.meta,
    color: colors.textSecondary,
    fontSize: 10,
  },
  body: {
    padding: spacing.md,
    gap: spacing.sm,
  },
  title: {
    fontSize: 14,
    lineHeight: 19,
    minHeight: 38,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
});
