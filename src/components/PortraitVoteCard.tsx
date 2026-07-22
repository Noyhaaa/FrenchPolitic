import { StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import type { PortraitVote } from '@/types';
import { Legend } from './Legend';
import { ResultBar } from './ResultBar';

/** « 0.87 » → « 87 % ». */
function pourcentage(ratio: number): string {
  return `${Math.round(ratio * 100)} %`;
}

function Stat({ valeur, label }: { valeur: string; label: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.valeur}>{valeur}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

/**
 * Portrait de vote d'un député sur les 12 derniers mois : ce qu'il a voté et
 * son alignement sur son groupe, puis la ventilation de ses votes. Purement
 * descriptif (§7.4) — aucun classement, aucune appréciation, et pas de taux de
 * participation (l'open data ne recense que les votants physiques d'un scrutin :
 * un ratio de présence se lirait comme un score d'absentéisme non sourcé). Une
 * statistique non calculable est **masquée** plutôt que ramenée à zéro (§2.5).
 */
export function PortraitVoteCard({ portrait }: { portrait: PortraitVote }) {
  const stats = [
    portrait.cohesionGroupe !== undefined
      ? { valeur: pourcentage(portrait.cohesionGroupe), label: 'avec son groupe' }
      : null,
    { valeur: String(portrait.votes), label: portrait.votes > 1 ? 'votes' : 'vote' },
  ].filter((s): s is { valeur: string; label: string } => s !== null);

  const total = portrait.pour + portrait.contre + portrait.abstention;

  return (
    <View style={styles.carte}>
      <View style={styles.entete}>
        <Text style={typography.overline}>Portrait de vote</Text>
        <Text style={typography.meta}>12 derniers mois</Text>
      </View>

      <View style={styles.stats}>
        {stats.map((s, i) => (
          <View key={s.label} style={styles.colonne}>
            {i > 0 ? <View style={styles.filet} /> : null}
            <Stat valeur={s.valeur} label={s.label} />
          </View>
        ))}
      </View>

      {/* Ventilation de ses votes exprimés. Masquée s'il n'a exprimé aucun
          vote sur la période : une barre vide ne dirait rien (§2.5). */}
      {total > 0 ? (
        <View style={styles.ventilation}>
          <ResultBar
            segments={[
              { value: portrait.pour, color: colors.pour },
              { value: portrait.abstention, color: colors.abstention },
              { value: portrait.contre, color: colors.contre },
            ]}
          />
          <Legend
            items={[
              { label: `${portrait.pour} pour`, color: colors.pour },
              { label: `${portrait.abstention} abstention`, color: colors.abstention },
              { label: `${portrait.contre} contre`, color: colors.contre },
            ]}
          />
        </View>
      ) : (
        <Text style={styles.absent}>
          Aucun vote exprimé sur la période : information non disponible.
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  carte: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    gap: spacing.lg,
  },
  entete: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  stats: {
    flexDirection: 'row',
  },
  colonne: {
    flex: 1,
    flexDirection: 'row',
  },
  filet: {
    width: 1,
    backgroundColor: colors.border,
    marginRight: spacing.md,
  },
  stat: {
    flex: 1,
    gap: 2,
  },
  valeur: {
    ...typography.hero,
    fontSize: 24,
    lineHeight: 30,
  },
  statLabel: {
    ...typography.meta,
  },
  ventilation: {
    gap: spacing.md,
  },
  absent: {
    ...typography.bodySecondary,
  },
});
