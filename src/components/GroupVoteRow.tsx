import { StyleSheet, Text, View } from 'react-native';
import { colors, spacing, typography } from '@/theme';
import { PositionGroupe } from '@/types';
import { positionLabel } from '@/utils/format';
import { ResultBar } from './ResultBar';

interface Props {
  groupe: PositionGroupe;
}

/**
 * Une ligne par groupe (§3.2 point 5) : pastille couleur + nom à gauche,
 * barre pour/contre/abstention à droite (maquette).
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
      <View style={styles.nameWrap}>
        <View style={[styles.dot, { backgroundColor: groupe.couleur }]} />
        <Text style={styles.name} numberOfLines={2}>
          {groupe.groupeNom}
        </Text>
      </View>
      <View style={styles.barWrap}>
        <ResultBar
          height={8}
          segments={[
            { value: pour, color: colors.pour },
            { value: contre, color: colors.contre },
            { value: abstention, color: colors.abstention },
          ]}
        />
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
  nameWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    width: 118,
  },
  name: {
    ...typography.meta,
    color: colors.textSecondary,
    flexShrink: 1,
  },
  dot: {
    width: 9,
    height: 9,
    borderRadius: 5,
  },
  barWrap: {
    flex: 1,
  },
});
