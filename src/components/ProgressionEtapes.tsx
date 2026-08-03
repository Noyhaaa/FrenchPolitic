import { StyleSheet, View } from 'react-native';

import { colors, radius, spacing } from '@/theme';

/**
 * Où en est-on dans le parcours d'accueil : un point par étape, allongé sur
 * l'étape courante.
 *
 * Décoratif pour un lecteur d'écran — la progression y est annoncée par le
 * `accessibilityLabel` du conteneur (« Étape 2 sur 5 »), pas par cinq points
 * qu'il faudrait parcourir un à un.
 */

interface Props {
  total: number;
  courante: number; // index 0-based
}

export function ProgressionEtapes({ total, courante }: Props) {
  return (
    <View
      style={styles.rangee}
      accessibilityRole="progressbar"
      accessibilityLabel={`Étape ${courante + 1} sur ${total}`}
    >
      {Array.from({ length: total }).map((_, i) => (
        <View
          key={i}
          style={[
            styles.point,
            i === courante && styles.pointCourant,
            i < courante && styles.pointFait,
          ]}
          importantForAccessibility="no"
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  rangee: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  point: {
    width: 7,
    height: 7,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
  },
  pointCourant: { width: 28, backgroundColor: colors.brand },
  pointFait: { backgroundColor: 'rgba(139,156,244,0.35)' },
});

/** Barre de remplissage simple (« 2 / 3 minimum » de l'étape des thèmes). */
export function BarreProgression({ part }: { part: number }) {
  const largeur = `${Math.max(0, Math.min(1, part)) * 100}%` as const;
  return (
    <View style={styles2.piste} importantForAccessibility="no">
      <View style={[styles2.remplissage, { width: largeur }]} />
    </View>
  );
}

const styles2 = StyleSheet.create({
  piste: {
    height: 5,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceMuted,
    overflow: 'hidden',
    marginTop: spacing.md,
  },
  remplissage: { height: '100%', borderRadius: radius.pill, backgroundColor: colors.brand },
});
