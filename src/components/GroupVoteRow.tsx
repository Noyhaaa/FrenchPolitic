import { StyleSheet, Text, View } from 'react-native';
import { colors, mono, spacing, typography } from '@/theme';
import { PositionGroupe } from '@/types';
import { positionLabel } from '@/utils/format';
import { ResultBar } from './ResultBar';

interface Props {
  groupe: PositionGroupe;
}

/**
 * Une ligne par groupe (§3.2 point 5), au format « Party Breakdown » du
 * prototype : barre de couleur du groupe à gauche, nom, barre
 * pour/abstention/contre et décomptes mono colorés.
 * Symétrie stricte : même gabarit pour tous les groupes (§7 point 4).
 */
export function GroupVoteRow({ groupe }: Props) {
  const { pour, contre, abstention } = groupe;
  return (
    <View
      style={styles.row}
      accessibilityLabel={`${groupe.groupeNom} : position majoritaire ${positionLabel(
        groupe.positionMajoritaire
      )}. ${pour} pour, ${contre} contre, ${abstention} abstentions.`}
    >
      <View style={[styles.colorBar, { backgroundColor: groupe.couleur }]} />
      <View style={styles.info}>
        <Text style={styles.name} numberOfLines={1}>
          {groupe.groupeNom}
        </Text>
        <ResultBar
          height={5}
          segments={[
            { value: pour, color: colors.pour },
            { value: abstention, color: colors.abstention },
            { value: contre, color: colors.contre },
          ]}
        />
        <View style={styles.counts}>
          <Text style={[styles.count, { color: colors.pour }]}>
            {pour} POUR
          </Text>
          {abstention > 0 ? (
            <Text style={[styles.count, { color: colors.abstention }]}>
              {abstention} ABS
            </Text>
          ) : null}
          <Text style={[styles.count, { color: colors.contre }]}>
            {contre} CONTRE
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  colorBar: {
    width: 4,
    height: 40,
    borderRadius: 2,
  },
  info: {
    flex: 1,
    gap: spacing.xs,
  },
  name: {
    ...typography.label,
    color: colors.textPrimary,
  },
  counts: {
    flexDirection: 'row',
    gap: spacing.lg,
  },
  count: {
    fontSize: 10,
    fontWeight: '600',
    fontFamily: mono,
  },
});
