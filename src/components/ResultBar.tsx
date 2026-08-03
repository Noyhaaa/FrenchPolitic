import { StyleSheet, View } from 'react-native';
import { colors } from '@/theme';

export interface Segment {
  value: number;
  color: string;
}

interface Props {
  segments: Segment[];
  height?: number;
}

/**
 * Barre proportionnelle multi-segments (résultat global, vote par groupe).
 * Purement factuelle — reflète les décomptes officiels (§7 point 2).
 */
export function ResultBar({ segments, height = 10 }: Props) {
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;
  return (
    <View style={[styles.track, { height, borderRadius: height / 2 }]}>
      {segments.map((s, i) => {
        const pct = (s.value / total) * 100;
        if (pct <= 0) return null;
        return (
          <View
            key={i}
            style={{ width: `${pct}%`, backgroundColor: s.color, height: '100%' }}
          />
        );
      })}
    </View>
  );
}

/**
 * Segments d'une **motion de censure**, mesurés contre le SEUIL de suffrages
 * requis — jamais pour/contre (§7.4).
 *
 * ⚠️ L'article 49 de la Constitution ne fait recenser que les voix
 * *favorables* : `contre` et `abstention` valent 0 **par construction**. Une
 * barre pour/contre s'afficherait donc toujours pleine, disant l'inverse du
 * résultat. Le seul rapport qui décide est « voix recueillies / voix requises »,
 * et la part manquante se peint en « non votant » plutôt qu'en « contre » :
 * personne n'a voté contre, la source ne le dit nulle part.
 *
 * Règle unique, partagée par les quatre endroits qui affichent une motion de
 * censure (fil, chronologie, fiche dossier, fiche vote) — elle était recopiée
 * dans chacun.
 */
export function segmentsMotionCensure(
  pour: number,
  suffragesRequis: number,
): Segment[] {
  return [
    { value: pour, color: colors.pour },
    { value: Math.max(0, suffragesRequis - pour), color: colors.nonVotant },
  ];
}

const styles = StyleSheet.create({
  track: {
    flexDirection: 'row',
    overflow: 'hidden',
    backgroundColor: colors.surfaceMuted,
    width: '100%',
    columnGap: 2, // fin liseré entre segments, comme le prototype
  },
});
