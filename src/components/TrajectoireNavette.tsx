import { Fragment } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import { StatutScrutin } from '@/types';
import {
  formatDateLong,
  statutLabel,
  type PhaseNavette,
} from '@/utils/format';

interface Props {
  phases: PhaseNavette[];
}

/** Icône + couleur par statut — jamais la couleur seule (RGAA §8) : le libellé
 * texte (« Adopté »…) accompagne toujours l'icône. */
const STATUT_UI: Record<StatutScrutin, { icon: string; color: string }> = {
  adopte: { icon: '✓', color: colors.adopte },
  rejete: { icon: '✕', color: colors.rejete },
  en_cours: { icon: '◷', color: colors.enCours },
};

/**
 * Frise de la trajectoire du texte **à l'Assemblée** (fiche dossier) : les
 * phases de navette documentées par les libellés officiels des votes
 * (« Première lecture », « Commission mixte paritaire », « Lecture
 * définitive »…), dans l'ordre chronologique, avec le statut du vote sur
 * l'ensemble de chaque phase quand il existe (§2.5 : sans vote d'ensemble,
 * la phase s'affiche sans statut — on n'infère rien). Les étapes hors AN
 * (Sénat) ne sont pas dans nos données, donc pas dans la frise.
 */
export function TrajectoireNavette({ phases }: Props) {
  if (phases.length === 0) return null;
  return (
    <View style={styles.card}>
      <Text style={[typography.overline, styles.titre]}>
        Trajectoire à l'Assemblée
      </Text>
      <View style={styles.steps}>
        {phases.map((p, i) => {
          const ui = p.statut ? STATUT_UI[p.statut] : null;
          return (
            <Fragment key={p.label}>
              {i > 0 ? (
                <Text style={styles.fleche} importantForAccessibility="no">
                  →
                </Text>
              ) : null}
              <View
                style={styles.step}
                accessibilityRole="text"
                accessibilityLabel={
                  p.statut
                    ? `${p.label} : ${statutLabel(p.statut)}, ${formatDateLong(p.date)}.`
                    : `${p.label}, ${formatDateLong(p.date)}.`
                }
              >
                <Text style={styles.stepLabel}>{p.label}</Text>
                {ui && p.statut ? (
                  <Text style={[styles.stepStatut, { color: ui.color }]}>
                    {ui.icon} {statutLabel(p.statut)}
                  </Text>
                ) : (
                  <Text style={styles.stepDate}>{formatDateLong(p.date)}</Text>
                )}
              </View>
            </Fragment>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
  },
  titre: {
    marginBottom: spacing.md,
  },
  steps: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: spacing.sm,
  },
  step: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    gap: 2,
  },
  stepLabel: {
    ...typography.label,
  },
  stepStatut: {
    ...typography.meta,
    fontWeight: '700',
  },
  stepDate: {
    ...typography.meta,
    color: colors.textTertiary,
  },
  fleche: {
    color: colors.textTertiary,
    fontSize: 16,
    fontWeight: '600',
  },
});
