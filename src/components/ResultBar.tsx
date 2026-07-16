import { StyleSheet, View } from 'react-native';
import { colors } from '@/theme';

export interface Segment {
  value: number;
  color: string;
}

interface Props {
  segments: Segment[];
  height?: number;
}

/**
 * Barre proportionnelle multi-segments (résultat global, vote par groupe).
 * Purement factuelle — reflète les décomptes officiels (§7 point 2).
 */
export function ResultBar({ segments, height = 10 }: Props) {
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;
  return (
    <View style={[styles.track, { height, borderRadius: height / 2 }]}>
      {segments.map((s, i) => {
        const pct = (s.value / total) * 100;
        if (pct <= 0) return null;
        return (
          <View
            key={i}
            style={{ width: `${pct}%`, backgroundColor: s.color, height: '100%' }}
          />
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    flexDirection: 'row',
    overflow: 'hidden',
    backgroundColor: colors.surfaceMuted,
    width: '100%',
    columnGap: 2, // fin liseré entre segments, comme le prototype
  },
});
