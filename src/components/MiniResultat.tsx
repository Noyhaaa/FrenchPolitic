import { StyleSheet, Text, View } from 'react-native';
import { colors, mono, spacing } from '@/theme';
import { ResultatGlobal } from '@/types';
import { ResultBar } from './ResultBar';

interface Props {
  resultat: ResultatGlobal;
  height?: number;
}

/**
 * Barre compacte « pour / contre » d'un vote, pour les cartes du fil.
 * Purement factuelle : reflète les décomptes officiels du scrutin (voix pour vs
 * contre), jamais une opinion. Le détail complet (abstentions, groupes, noms)
 * vit sur la fiche vote. La proportion n'est **jamais** portée par la couleur
 * seule — le décompte chiffré et les libellés « pour »/« contre » l'accompagnent
 * (§7 point 2, RGAA §8).
 */
export function MiniResultat({ resultat, height = 6 }: Props) {
  const { pour, contre } = resultat;
  const total = pour + contre || 1;
  const pctPour = Math.round((pour / total) * 100);
  const pctContre = 100 - pctPour;

  return (
    <View
      style={styles.wrap}
      accessibilityRole="text"
      accessibilityLabel={`Résultat du vote : ${pour} pour, ${contre} contre.`}
    >
      <ResultBar
        height={height}
        segments={[
          { value: pour, color: colors.pour },
          { value: contre, color: colors.contre },
        ]}
      />
      <View style={styles.legend}>
        <Text style={[styles.pct, { color: colors.pour }]}>
          {pctPour}%{' '}
          <Text style={styles.count}>· {pour} pour</Text>
        </Text>
        <Text style={[styles.pct, { color: colors.contre }]}>
          <Text style={styles.count}>{contre} contre ·</Text> {pctContre}%
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: spacing.xs,
  },
  legend: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  pct: {
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '700',
    fontFamily: mono,
  },
  count: {
    fontSize: 10,
    fontWeight: '500',
    fontFamily: mono,
    color: colors.textTertiary,
  },
});
