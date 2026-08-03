import { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, StyleSheet, useWindowDimensions, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Svg, { Circle, Line } from 'react-native-svg';

import { colors } from '@/theme';

/**
 * Le ciel du profil — bandeau dégradé, champ d'étoiles qui scintille, fondu vers
 * le fond de l'app.
 *
 * Purement décoratif : rien n'y est une information, et le bloc entier est
 * retiré de l'ordre de lecture (RGAA §8).
 *
 * Reprend la grammaire constellation déjà posée par `DecrypteSplash` (mêmes
 * tokens d'étoile) plutôt que d'inventer un second ciel.
 *
 * ⚠️ **Le scintillement n'anime aucune prop SVG.** Les étoiles sont dessinées
 * une fois pour toutes, réparties en 4 **calques** superposés, et c'est
 * l'`opacity` de la `View` de chaque calque qui respire — donc en
 * `useNativeDriver: true`. Animer l'`opacity` de 32 `Circle` (ce que fait
 * `DecrypteSplash`, sur un écran de lancement bref) obligerait au driver JS :
 * chaque frame repasserait par JavaScript pour 32 mises à jour de props, le
 * thread JS saturerait et les taps comme la navigation se figeraient. Ici
 * l'écran vit dans un onglet qu'on ne démonte jamais : c'est rédhibitoire.
 *
 * `anime` coupe en plus les boucles hors focus et quand le système demande de
 * réduire les animations ; les calques gèlent à leur opacité courante.
 */

const HAUTEUR_REF = 210;
const GROUPES = 4;
const CREUX = 0.42; // opacité basse d'un calque
const PLEIN = 1;

/**
 * Table déterministe (jamais `Math.random` : le ciel doit être le même à chaque
 * rendu). Le pas de 137,5° est l'angle d'or — il répartit sans grille apparente.
 */
const ETOILES = Array.from({ length: 32 }, (_, i) => ({
  x: (i * 137.5) % 390,
  y: (i * 97.3) % HAUTEUR_REF,
  r: i % 5 === 0 ? 1.5 : i % 3 === 0 ? 1.1 : 0.7,
  // Opacité pleine de l'étoile ; le calque la fait ensuite respirer.
  eclat: Math.min((0.14 + (i % 7) * 0.06) * 2.4, 0.9),
  groupe: i % GROUPES,
  vive: i % 11 === 0,
}));

/** Quelques traits entre étoiles voisines — le rappel de la constellation. */
const TRAITS: [number, number][] = [
  [3, 14],
  [7, 18],
  [11, 22],
];

interface Props {
  /** Hauteur du ciel sous la zone sûre. */
  hauteur: number;
  /** Décalage de barre d'état à couvrir. */
  insetTop: number;
  /** Les étoiles scintillent. */
  anime: boolean;
}

export function ProfilCiel({ hauteur, insetTop, anime }: Props) {
  const { width } = useWindowDimensions();
  const total = hauteur + insetTop;

  // Un pilote par calque, déphasé d'un quart de cycle.
  const pilotes = useRef(
    Array.from({ length: GROUPES }, () => new Animated.Value(0.75)),
  ).current;

  const calques = useMemo(
    () => pilotes.map((_, g) => ETOILES.filter((e) => e.groupe === g)),
    [pilotes],
  );

  useEffect(() => {
    if (!anime) return;
    const boucles = pilotes.map((p, i) =>
      Animated.sequence([
        Animated.delay(i * 850),
        Animated.loop(
          Animated.sequence([
            Animated.timing(p, {
              toValue: PLEIN,
              duration: 1700,
              easing: Easing.inOut(Easing.ease),
              useNativeDriver: true,
            }),
            Animated.timing(p, {
              toValue: CREUX,
              duration: 1700,
              easing: Easing.inOut(Easing.ease),
              useNativeDriver: true,
            }),
          ]),
        ),
      ]),
    );
    boucles.forEach((b) => b.start());
    return () => boucles.forEach((b) => b.stop());
  }, [anime, pilotes]);

  return (
    <View
      style={{ height: total }}
      pointerEvents="none"
      importantForAccessibility="no-hide-descendants"
    >
      <LinearGradient
        colors={[colors.cielHaut, colors.cielMilieu, colors.cielBas]}
        locations={[0, 0.55, 1]}
        start={{ x: 0.15, y: 0 }}
        end={{ x: 0.85, y: 1 }}
        style={StyleSheet.absoluteFill}
      />

      {/* Traits de constellation — statiques. */}
      <View style={StyleSheet.absoluteFill}>
        <Svg
          width={width}
          height={total}
          viewBox={`0 0 390 ${HAUTEUR_REF}`}
          preserveAspectRatio="xMidYMid slice"
        >
          {TRAITS.map(([a, b], i) => (
            <Line
              key={`t${i}`}
              x1={ETOILES[a].x}
              y1={ETOILES[a].y}
              x2={ETOILES[b].x}
              y2={ETOILES[b].y}
              stroke={colors.splashLigneSoft}
              strokeWidth={0.7}
              opacity={0.1}
            />
          ))}
        </Svg>
      </View>

      {calques.map((etoiles, g) => (
        <Animated.View key={`c${g}`} style={[StyleSheet.absoluteFill, { opacity: pilotes[g] }]}>
          <Svg
            width={width}
            height={total}
            viewBox={`0 0 390 ${HAUTEUR_REF}`}
            preserveAspectRatio="xMidYMid slice"
          >
            {etoiles.map((e, i) => (
              <Circle
                key={`e${i}`}
                cx={e.x}
                cy={e.y}
                r={e.r}
                fill={e.vive ? colors.splashEtoileVive : colors.splashEtoile}
                opacity={e.eclat}
              />
            ))}
          </Svg>
        </Animated.View>
      ))}

      <LinearGradient
        colors={['transparent', colors.cielVoile, colors.background]}
        locations={[0, 0.62, 1]}
        style={StyleSheet.absoluteFill}
      />
    </View>
  );
}
