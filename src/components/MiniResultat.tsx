import { StyleSheet, Text, View } from 'react-native';
import { colors, mono, spacing } from '@/theme';
import { ResultatGlobal, TypeVote } from '@/types';
import { ResultBar, segmentsMotionCensure } from './ResultBar';

interface Props {
  resultat: ResultatGlobal;
  height?: number;
  /**
   * Forme du scrutin. Seule `motion_censure` change quelque chose ici — et de
   * façon décisive : voir plus bas.
   */
  typeVote?: TypeVote;
  /** Voix nécessaires, utilisé uniquement pour une motion de censure. */
  suffragesRequis?: number;
}

/**
 * Barre compacte « pour / contre » d'un vote, pour les cartes du fil.
 * Purement factuelle : reflète les décomptes officiels du scrutin (voix pour vs
 * contre), jamais une opinion. Le détail complet (abstentions, groupes, noms)
 * vit sur la fiche vote. La proportion n'est **jamais** portée par la couleur
 * seule — le décompte chiffré et les libellés « pour »/« contre » l'accompagnent
 * (§7 point 2, RGAA §8).
 *
 * ⚠️ **Motion de censure** : l'article 49 de la Constitution ne fait recenser
 * que les voix FAVORABLES, si bien que `contre` y vaut 0 par construction. La
 * barre pour/contre s'afficherait alors pleine et à 100 % — une unanimité qui
 * n'a jamais eu lieu, sur le vote le plus regardé de tous. On mesure donc les
 * voix recueillies **contre le seuil**, qui est le seul rapport décisif.
 */
export function MiniResultat({
  resultat,
  height = 6,
  typeVote,
  suffragesRequis,
}: Props) {
  const { pour, contre } = resultat;

  if (typeVote === 'motion_censure' && suffragesRequis) {
    const pct = Math.round((Math.min(pour, suffragesRequis) / suffragesRequis) * 100);
    return (
      <View
        style={styles.wrap}
        accessibilityRole="text"
        accessibilityLabel={`Motion de censure : ${pour} voix pour, ${suffragesRequis} requises.`}
      >
        <ResultBar
          height={height}
          segments={segmentsMotionCensure(pour, suffragesRequis)}
        />
        <View style={styles.legend}>
          <Text style={[styles.pct, { color: colors.pour }]}>
            {pct}% <Text style={styles.count}>· {pour} voix pour</Text>
          </Text>
          <Text style={styles.count}>{suffragesRequis} requises</Text>
        </View>
      </View>
    );
  }

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
