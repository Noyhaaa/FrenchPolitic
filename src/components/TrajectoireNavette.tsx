import { Fragment } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import { PhaseScrutin, StatutScrutin } from '@/types';
import { formatDateLong, libelleChambre, statutLabel } from '@/utils/format';

interface Props {
  phases: PhaseScrutin[];
}

/** Icône + couleur par statut — jamais la couleur seule (RGAA §8) : le libellé
 * texte (« Adopté »…) accompagne toujours l'icône. */
const STATUT_UI: Record<StatutScrutin, { icon: string; color: string }> = {
  adopte: { icon: '✓', color: colors.adopte },
  rejete: { icon: '✕', color: colors.rejete },
  en_cours: { icon: '◷', color: colors.enCours },
};

/**
 * Frise de la trajectoire du texte **au Parlement** (fiche dossier) : les
 * étapes de la navette dans l'ordre chronologique — lectures à l'Assemblée ET
 * au Sénat, commission mixte paritaire, Conseil constitutionnel, promulgation.
 *
 * Elle est **calculée côté backend** (`Dossier.trajectoire`) depuis les actes
 * législatifs officiels du dossier : l'app ne peut pas la déduire des scrutins,
 * qui ne documentent que ce que chaque chambre a voté. Le statut d'une étape
 * n'est affiché que si la source le dit (§2.5 : une étape en cours s'affiche
 * avec sa seule date, on n'infère rien), et la chambre est écrite en toutes
 * lettres — jamais portée par la seule couleur (RGAA §8).
 */
export function TrajectoireNavette({ phases }: Props) {
  if (phases.length === 0) return null;
  return (
    <View style={styles.card}>
      <Text style={[typography.overline, styles.titre]}>
        Trajectoire au Parlement
      </Text>
      <View style={styles.steps}>
        {phases.map((p, i) => {
          const ui = p.statut ? STATUT_UI[p.statut] : null;
          const chambre = p.chambre ? libelleChambre(p.chambre) : null;
          const date = p.date ? formatDateLong(p.date) : null;
          // Une étape peut n'avoir ni statut ni date (rare) : on n'affiche
          // alors que son libellé officiel plutôt qu'une ligne vide.
          const detail = ui && p.statut ? statutLabel(p.statut) : date;
          return (
            <Fragment key={`${p.label}-${p.chambre ?? 'commune'}`}>
              {i > 0 ? (
                <Text style={styles.fleche} importantForAccessibility="no">
                  →
                </Text>
              ) : null}
              <View
                style={styles.step}
                accessibilityRole="text"
                accessibilityLabel={[
                  chambre ? `${chambre} :` : null,
                  p.label,
                  p.statut ? `: ${statutLabel(p.statut)}` : null,
                  date ? `, ${date}` : null,
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                {chambre ? (
                  <Text style={styles.stepChambre}>{chambre}</Text>
                ) : null}
                <Text style={styles.stepLabel}>{p.label}</Text>
                {ui && p.statut ? (
                  <Text style={[styles.stepStatut, { color: ui.color }]}>
                    {ui.icon} {statutLabel(p.statut)}
                  </Text>
                ) : detail ? (
                  <Text style={styles.stepDate}>{detail}</Text>
                ) : null}
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
  stepChambre: {
    ...typography.meta,
    color: colors.textTertiary,
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
