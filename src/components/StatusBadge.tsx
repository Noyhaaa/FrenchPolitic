import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';
import { StatutScrutin } from '@/types';
import { statutLabel } from '@/utils/format';

const config: Record<StatutScrutin, { fg: string; bg: string; icon: string }> = {
  adopte: { fg: colors.adopte, bg: colors.adopteSoft, icon: '✅' },
  rejete: { fg: colors.rejete, bg: colors.rejeteSoft, icon: '❌' },
  en_cours: { fg: colors.enCours, bg: colors.enCoursSoft, icon: '🟡' },
};

interface Props {
  statut: StatutScrutin;
  /** Libellé personnalisé (ex. « Adopté en 1re lecture » sur la fiche). */
  label?: string;
}

/**
 * Badge de statut : couleur + icône + libellé texte.
 * L'information n'est jamais portée par la couleur seule (RGAA, §8).
 */
export function StatusBadge({ statut, label }: Props) {
  const { fg, bg, icon } = config[statut];
  const text = label ?? statutLabel(statut);
  return (
    <View
      style={[styles.badge, { backgroundColor: bg }]}
      accessibilityRole="text"
      accessibilityLabel={`Statut : ${text}`}
    >
      <Text style={styles.icon}>{icon}</Text>
      <Text style={[typography.badge, { color: fg }]}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingVertical: 5,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    gap: 6,
  },
  icon: {
    fontSize: 11,
  },
});
