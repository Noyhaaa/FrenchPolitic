import { StyleSheet, Text, View } from 'react-native';
import { colors, serif, spacing } from '@/theme';

/** En-tête de marque : wordmark serif « Décrypté » (style prototype). */
export function BrandHeader({ right }: { right?: React.ReactNode }) {
  return (
    <View style={styles.wrap}>
      <Text style={styles.wordmark}>Décrypté</Text>
      {right}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  wordmark: {
    fontSize: 21,
    fontWeight: '900',
    fontFamily: serif,
    letterSpacing: -0.4,
    color: colors.textPrimary,
  },
});
