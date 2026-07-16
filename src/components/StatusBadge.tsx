import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';
import { StatutScrutin } from '@/types';
import { statutLabel } from '@/utils/format';

const config: Record<StatutScrutin, { bg: string; icon: string }> = {
  adopte: { bg: colors.adopte, icon: '✓' },
  rejete: { bg: colors.rejete, icon: '✕' },
  en_cours: { bg: colors.enCours, icon: '◷' },
};

interface Props {
  statut: StatutScrutin;
  /** Libellé personnalisé (ex. « Adopté en 1re lecture » sur la fiche). */
  label?: string;
}

/**
 * Badge de statut (style prototype : fond plein, texte mono en capitales).
 * L'information n'est jamais portée par la couleur seule : toujours un
 * glyphe + un libellé texte (RGAA, §8).
 */
export function StatusBadge({ statut, label }: Props) {
  const { bg, icon } = config[statut];
  const text = label ?? statutLabel(statut);
  return (
    <View
      style={[styles.badge, { backgroundColor: bg }]}
      accessibilityRole="text"
      accessibilityLabel={`Statut : ${text}`}
    >
      <Text style={styles.icon}>{icon}</Text>
      <Text style={[typography.badge, styles.label]}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingVertical: 3,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    gap: 4,
  },
  icon: {
    fontSize: 10,
    fontWeight: '800',
    color: colors.textOnAccent,
  },
  label: {
    color: colors.textOnAccent,
  },
});
