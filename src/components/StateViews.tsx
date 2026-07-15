import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';

/** Indicateur de chargement centré. */
export function LoadingView({ label }: { label?: string }) {
  return (
    <View style={styles.center}>
      <ActivityIndicator color={colors.brand} />
      {label ? <Text style={[typography.bodySecondary, styles.gap]}>{label}</Text> : null}
    </View>
  );
}

interface ErrorProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

/** État d'erreur avec bouton « Réessayer ». */
export function ErrorView({ title = 'Oups', message, onRetry }: ErrorProps) {
  return (
    <View style={styles.center}>
      <Text style={styles.emoji}>📡</Text>
      <Text style={[typography.cardTitle, styles.gap]}>{title}</Text>
      <Text style={[typography.bodySecondary, styles.message]}>{message}</Text>
      {onRetry ? (
        <Pressable
          onPress={onRetry}
          style={({ pressed }) => [styles.retry, pressed && { opacity: 0.85 }]}
          accessibilityRole="button"
          accessibilityLabel="Réessayer"
        >
          <Text style={styles.retryText}>Réessayer</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

/** Message d'état vide (aucun contenu). */
export function EmptyView({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View style={styles.center}>
      <Text style={typography.body}>{title}</Text>
      {subtitle ? (
        <Text style={[typography.bodySecondary, styles.gap]}>{subtitle}</Text>
      ) : null}
    </View>
  );
}

/** Bandeau discret : contenu servi depuis le cache (hors-ligne). */
export function OfflineBanner() {
  return (
    <View style={styles.banner}>
      <Text style={styles.bannerText}>
        ⚠︎ Hors-ligne — contenu enregistré, peut-être daté.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xxl,
    gap: spacing.xs,
  },
  gap: {
    marginTop: spacing.xs,
  },
  emoji: {
    fontSize: 40,
  },
  message: {
    textAlign: 'center',
  },
  retry: {
    marginTop: spacing.lg,
    backgroundColor: colors.brand,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
  },
  retryText: {
    ...typography.label,
    color: colors.textOnAccent,
    fontSize: 15,
  },
  banner: {
    backgroundColor: colors.accentWarmSoft,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  bannerText: {
    ...typography.meta,
    color: colors.accentWarm,
    textAlign: 'center',
  },
});
