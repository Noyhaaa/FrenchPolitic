import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';
import { NiveauConfiance } from '@/types';

interface Props {
  confiance: NiveauConfiance;
  reluParHumain: boolean;
  onSignaler?: () => void;
}

const confianceLabel: Record<NiveauConfiance, string> = {
  haute: 'confiance élevée',
  moyenne: 'confiance moyenne',
  faible: 'confiance faible',
};

/**
 * Transparence sur l'IA (§7 point 6) : mention explicite que le résumé est
 * généré à partir des sources officielles + relu, et bouton « signaler ».
 */
export function AiNotice({ confiance, reluParHumain, onSignaler }: Props) {
  return (
    <View style={styles.wrap}>
      <Text style={typography.meta}>
        Résumé généré automatiquement à partir des sources officielles
        {reluParHumain ? ', relu par un humain' : ''} · {confianceLabel[confiance]}.
      </Text>
      <Pressable
        onPress={onSignaler}
        accessibilityRole="button"
        accessibilityLabel="Signaler une erreur dans ce résumé"
        hitSlop={8}
      >
        <Text style={styles.signaler}>Signaler une erreur</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
  },
  signaler: {
    ...typography.label,
    color: colors.brand,
  },
});
