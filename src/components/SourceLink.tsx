import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';
import { SourceOfficielle, TypeSource } from '@/types';

const icon: Record<TypeSource, string> = {
  texte: '📄',
  amendements: '✏️',
  debats: '💬',
  scrutin: '🗳️',
};

interface Props {
  source: SourceOfficielle;
}

/**
 * Lien vers une source officielle (§3.2 point 7).
 * Réversibilité : l'utilisateur atteint la source brute en 1 tap (§7 point 5).
 */
export function SourceLink({ source }: Props) {
  return (
    <Pressable
      onPress={() => Linking.openURL(source.url)}
      style={({ pressed }) => [styles.chip, pressed && styles.pressed]}
      accessibilityRole="link"
      accessibilityLabel={`Ouvrir la source : ${source.libelle}`}
    >
      <Text style={styles.icon}>{icon[source.type]}</Text>
      <Text style={[typography.label, styles.label]} numberOfLines={1}>
        {source.libelle}
      </Text>
      <Text style={styles.arrow}>↗</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
  },
  pressed: {
    opacity: 0.7,
  },
  icon: {
    fontSize: 14,
  },
  label: {
    color: colors.textPrimary,
  },
  arrow: {
    color: colors.brand,
    fontWeight: '700',
  },
});

// Simple grid wrapper for a list of sources.
export function SourceGrid({ sources }: { sources: SourceOfficielle[] }) {
  return (
    <View style={grid.wrap}>
      {sources.map((s) => (
        <View key={`${s.type}-${s.url}`} style={grid.item}>
          <SourceLink source={s} />
        </View>
      ))}
    </View>
  );
}

const grid = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  item: {
    // deux colonnes
    width: '48%',
    flexGrow: 1,
  },
});
