import { StyleSheet, Text, View } from 'react-native';
import { spacing, typography } from '@/theme';

export interface LegendItem {
  label: string;
  color: string;
}

/** Légende des couleurs (accompagne toujours les barres — RGAA §8). */
export function Legend({ items }: { items: LegendItem[] }) {
  return (
    <View style={styles.wrap}>
      {items.map((it) => (
        <View key={it.label} style={styles.item}>
          <View style={[styles.dot, { backgroundColor: it.color }]} />
          <Text style={typography.meta}>{it.label}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  dot: {
    // petits carrés, comme la maquette
    width: 8,
    height: 8,
    borderRadius: 2,
  },
});
