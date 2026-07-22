import { useState } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';

import { colors, mono, radius } from '@/theme';

/** Initiales d'un nom (« Camille Laurent » → « CL »). Deux lettres au plus. */
function initiales(nom: string): string {
  return nom
    .split(/[\s-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((mot) => mot[0]?.toUpperCase() ?? '')
    .join('');
}

interface Props {
  nom: string;
  /** Photo officielle si l'open data la fournit — sinon les initiales (§2.5). */
  portraitUrl?: string;
  /** Couleur du groupe : pastille d'appartenance en bas à droite. */
  groupeCouleur?: string;
  taille?: number;
}

/**
 * Portrait d'un député. Sans photo officielle, on affiche ses initiales
 * plutôt qu'une silhouette générique. La pastille de groupe est cerclée du
 * fond de page pour se détacher ; elle ne porte jamais seule une information
 * (le nom du groupe est toujours écrit à côté, §8/RGAA).
 */
export function Avatar({ nom, portraitUrl, groupeCouleur, taille = 44 }: Props) {
  // Photo injoignable au moment de l'affichage (réseau, image retirée du site
  // de l'Assemblée) → on retombe sur les initiales plutôt que sur un trou.
  const [echecPhoto, setEchecPhoto] = useState(false);
  const photo = portraitUrl && !echecPhoto ? portraitUrl : undefined;
  const style = {
    width: taille,
    height: taille,
    borderRadius: taille / 2,
  };
  const pastille = Math.max(10, Math.round(taille * 0.28));

  return (
    <View style={[styles.wrap, style]} importantForAccessibility="no">
      {photo ? (
        <Image
          source={{ uri: photo }}
          style={[styles.photo, style]}
          onError={() => setEchecPhoto(true)}
          accessibilityIgnoresInvertColors
        />
      ) : (
        <Text style={[styles.initiales, { fontSize: Math.round(taille * 0.34) }]}>
          {initiales(nom)}
        </Text>
      )}
      {groupeCouleur ? (
        <View
          style={[
            styles.pastille,
            {
              width: pastille,
              height: pastille,
              borderRadius: pastille / 2,
              backgroundColor: groupeCouleur,
            },
          ]}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.pill,
  },
  photo: {
    position: 'absolute',
  },
  initiales: {
    // Pas de spread de `typography.meta` : sa hauteur de ligne fixe (15)
    // rognerait les initiales, dont la taille suit celle de l'avatar.
    fontFamily: mono,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  pastille: {
    position: 'absolute',
    right: -1,
    bottom: -1,
    borderWidth: 2,
    borderColor: colors.background,
  },
});
