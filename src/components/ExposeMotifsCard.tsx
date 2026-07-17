import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';
import type { ExposeMotifs } from '@/types';
import { SourceLink } from './SourceLink';

interface Props {
  expose: ExposeMotifs;
}

/** Au-delà de ce nombre de caractères, le bloc est replié par défaut. */
const SEUIL_REPLI = 320;

/**
 * Exposé des motifs du texte — le « pourquoi » **rédigé par l'auteur du dépôt**.
 *
 * ⚠️ Contenu NON neutre (§4.3) : présenté comme une **citation attribuée**
 * (pastille « Point de vue de l'auteur », texte en italique entre guillemets),
 * jamais confondu avec le résumé neutre. Un accent ambre + le libellé signalent
 * qu'il s'agit d'un point de vue, pas d'un fait. Source officielle en 1 tap
 * (réversibilité §7.5).
 */
export function ExposeMotifsCard({ expose }: Props) {
  const [deplie, setDeplie] = useState(false);
  const repliable = expose.texte.length > SEUIL_REPLI;

  return (
    <View style={styles.card}>
      <Text style={[typography.overline, styles.title]}>
        Ce que dit l'auteur du texte
      </Text>

      <View style={styles.pill}>
        <Text style={styles.pillText}>👤 Point de vue de l'auteur</Text>
      </View>

      <Text style={[typography.bodySecondary, styles.intro]}>
        Extrait de l'exposé des motifs, rédigé par l'auteur du texte lors de son
        dépôt. Ce n'est pas une analyse neutre.
      </Text>

      <Text
        style={[typography.body, styles.quote]}
        numberOfLines={repliable && !deplie ? 6 : undefined}
      >
        « {expose.texte} »
      </Text>

      {repliable ? (
        <Pressable
          onPress={() => setDeplie((v) => !v)}
          accessibilityRole="button"
          accessibilityLabel={
            deplie ? "Réduire l'exposé des motifs" : "Lire tout l'exposé des motifs"
          }
        >
          <Text style={styles.toggle}>
            {deplie ? 'Réduire ▲' : 'Lire la suite ▼'}
          </Text>
        </Pressable>
      ) : null}

      <View style={styles.source}>
        <SourceLink source={expose.source} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    // Accent ambre à gauche : marque visuellement un contenu « point de vue ».
    borderLeftWidth: 3,
    borderLeftColor: colors.accentWarm,
  },
  title: {
    marginBottom: spacing.md,
  },
  pill: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accentWarmSoft,
    borderRadius: radius.pill,
    paddingVertical: 4,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  pillText: {
    ...typography.badge,
    color: colors.accentWarm,
  },
  intro: {
    marginBottom: spacing.md,
  },
  quote: {
    fontStyle: 'italic',
  },
  toggle: {
    ...typography.meta,
    color: colors.brand,
    fontWeight: '600',
    paddingTop: spacing.md,
  },
  source: {
    marginTop: spacing.lg,
    alignSelf: 'flex-start',
  },
});
