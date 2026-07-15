import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';

/** En-tête de marque : logo « AN » + nom de l'app « Décrypté ». */
export function BrandHeader({ right }: { right?: React.ReactNode }) {
  return (
    <View style={styles.wrap}>
      <View style={styles.left}>
        <View style={styles.logo}>
          <Text style={styles.logoText}>AN</Text>
        </View>
        <Text style={typography.title}>Décrypté</Text>
      </View>
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
  left: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  logo: {
    width: 34,
    height: 34,
    borderRadius: radius.sm,
    backgroundColor: colors.brand,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoText: {
    color: colors.textOnAccent,
    fontWeight: '800',
    fontSize: 14,
    letterSpacing: 0.5,
  },
});
