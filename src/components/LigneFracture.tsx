import { StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import type { PositionGroupe, PositionVote } from '@/types';

interface Props {
  positionsGroupes: PositionGroupe[];
  /**
   * Par défaut, un vote unanime (un seul camp) ne montre pas de fracture —
   * il n'y en a pas. `true` affiche quand même le camp unique : utile quand la
   * ligne répond à « Qui était pour, qui était contre ? » (l'unanimité EST la
   * réponse, factuelle).
   */
  afficherUnanimite?: boolean;
}

/** Un camp du vote (une position + les groupes qui l'ont majoritairement prise). */
interface Camp {
  position: PositionVote;
  label: string;
  color: string;
  groupes: PositionGroupe[];
}

/**
 * Synthèse en un coup d'œil de **la ligne de fracture d'un vote** : quels groupes
 * ont majoritairement voté pour, contre, ou se sont abstenus (§3.2, §5.2).
 *
 * 100 % factuel et sourcé par le scrutin lui-même — c'est la position
 * majoritaire de chaque groupe, jamais un jugement (« qui a raison »). Symétrie
 * stricte : même gabarit pour chaque camp et chaque groupe (§7.4). Le camp est
 * porté par le **libellé texte** (« Ont voté pour »…), pas par la couleur seule
 * (§8, RGAA) ; la pastille reprend la couleur d'identité du groupe.
 */
export function LigneFracture({ positionsGroupes, afficherUnanimite }: Props) {
  const camps: Camp[] = [
    { position: 'pour', label: 'Ont voté pour', color: colors.pour, groupes: [] },
    { position: 'contre', label: 'Ont voté contre', color: colors.contre, groupes: [] },
    {
      position: 'abstention',
      label: 'Se sont abstenus',
      color: colors.abstention,
      groupes: [],
    },
    {
      position: 'non_votant',
      label: "N'ont pas pris part",
      color: colors.nonVotant,
      groupes: [],
    },
  ];
  const parPosition = new Map(camps.map((c) => [c.position, c]));
  for (const g of positionsGroupes) {
    parPosition.get(g.positionMajoritaire)?.groupes.push(g);
  }
  const campsRemplis = camps.filter((c) => c.groupes.length > 0);
  // Un seul camp = pas de fracture à montrer (unanimité des groupes présents),
  // sauf si l'appelant veut l'unanimité comme réponse factuelle.
  if (campsRemplis.length < (afficherUnanimite ? 1 : 2)) return null;

  return (
    <View style={styles.wrap}>
      {campsRemplis.map((camp) => (
        <View key={camp.position} style={styles.camp}>
          <Text style={[typography.overline, { color: camp.color }]}>
            {camp.label} ({camp.groupes.length})
          </Text>
          <View style={styles.chips}>
            {camp.groupes.map((g) => (
              <View key={g.groupeId} style={styles.chip}>
                <View style={[styles.dot, { backgroundColor: g.couleur }]} />
                <Text style={styles.chipText} numberOfLines={1}>
                  {g.groupeNom}
                </Text>
              </View>
            ))}
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: spacing.md,
  },
  camp: {
    gap: spacing.xs,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.pill,
    paddingVertical: 3,
    paddingHorizontal: spacing.sm,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  chipText: {
    ...typography.meta,
    color: colors.textPrimary,
  },
});
