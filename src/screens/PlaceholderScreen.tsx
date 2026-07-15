import { StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, radius, spacing, typography } from '@/theme';

interface Props {
  emoji: string;
  title: string;
  description: string;
  /** Étiquette de jalon (ex. « Prévu en V2 »). */
  jalon?: string;
}

/** Écran « à venir » pour les fonctions hors périmètre V1 (§2.3 / §2.4). */
export function PlaceholderScreen({ emoji, title, description, jalon }: Props) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.content}>
        <Text style={styles.emoji}>{emoji}</Text>
        <Text style={[typography.title, styles.title]}>{title}</Text>
        <Text style={[typography.bodySecondary, styles.desc]}>{description}</Text>
        {jalon ? (
          <View style={styles.badge}>
            <Text style={[typography.badge, { color: colors.brand }]}>{jalon}</Text>
          </View>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xxl,
    gap: spacing.md,
  },
  emoji: {
    fontSize: 44,
  },
  title: {
    textAlign: 'center',
  },
  desc: {
    textAlign: 'center',
  },
  badge: {
    marginTop: spacing.sm,
    backgroundColor: colors.brandSoft,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
  },
});
