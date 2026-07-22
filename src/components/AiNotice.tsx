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
 * Transparence sur l'IA (§7 point 6) : mention explicite que les réponses
 * générées (les 4 questions) le sont à partir des sources officielles + relu,
 * et bouton « signaler ».
 */
export function AiNotice({ confiance, reluParHumain, onSignaler }: Props) {
  return (
    <View style={styles.wrap}>
      <Text style={typography.meta}>
        Réponses générées automatiquement à partir des sources officielles
        {reluParHumain ? ', relues par un humain' : ''} · {confianceLabel[confiance]}.
      </Text>
      <Pressable
        onPress={onSignaler}
        accessibilityRole="button"
        accessibilityLabel="Signaler une erreur"
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
