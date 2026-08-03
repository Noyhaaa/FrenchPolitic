import { StyleSheet, Text, View } from 'react-native';
import { colors, mono, radius, spacing, typography } from '@/theme';
import { RecapMensuel } from '@/types';
import { libelleMoisAnnee } from '@/utils/format';

interface Props {
  recap: RecapMensuel;
}

/**
 * Récapitulatif du dernier mois **actif** à l'Assemblée (le bloc « Summary »
 * du prototype) : votes tenus, adoptés / rejetés, textes concernés. Comptes
 * calculés côté backend (exacts, indépendants de la pagination du fil).
 * Purement descriptif — un décompte, aucun jugement (§7.8).
 */
export function RecapVotes({ recap }: Props) {
  const libelleMois = libelleMoisAnnee(recap.annee, recap.mois);

  const cells = [
    { icon: '✓', label: 'Adoptés', value: recap.adoptes, color: colors.adopte },
    { icon: '✕', label: 'Rejetés', value: recap.rejetes, color: colors.rejete },
    { icon: '§', label: 'Textes', value: recap.textes, color: colors.brand },
  ];

  return (
    <View
      style={styles.card}
      accessibilityRole="text"
      accessibilityLabel={`${libelleMois} : ${recap.votes} votes, ${recap.adoptes} adoptés, ${recap.rejetes} rejetés, sur ${recap.textes} textes.`}
    >
      <View style={styles.header}>
        <Text style={typography.overline}>{libelleMois}</Text>
        <Text style={typography.overline}>
          {recap.votes} vote{recap.votes > 1 ? 's' : ''}
        </Text>
      </View>
      <View style={styles.row}>
        {cells.map((cell, i) => (
          <View key={cell.label} style={[styles.cell, i > 0 && styles.cellBorder]}>
            <Text
              style={[styles.icon, { color: cell.color }]}
              importantForAccessibility="no"
            >
              {cell.icon}
            </Text>
            <Text style={[styles.count, { color: cell.color }]}>
              {cell.value}
            </Text>
            <Text style={styles.label}>{cell.label}</Text>
          </View>
        ))}
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
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.lg,
  },
  row: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  cell: {
    flex: 1,
    alignItems: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.lg,
  },
  cellBorder: {
    borderLeftWidth: 1,
    borderLeftColor: colors.border,
  },
  icon: {
    fontSize: 15,
    fontWeight: '800',
  },
  count: {
    fontSize: 26,
    lineHeight: 30,
    fontWeight: '800',
    fontFamily: mono,
  },
  label: {
    ...typography.meta,
    color: colors.textSecondary,
  },
});
