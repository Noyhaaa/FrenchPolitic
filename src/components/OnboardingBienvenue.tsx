import { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Defs, Path, RadialGradient, Stop } from 'react-native-svg';

import { colors, mono, radius, serifDisplay, spacing, typography } from '@/theme';

/**
 * Étape 1 — la porte d'entrée.
 *
 * Reprend la constellation « chat qui dort » du splash (`DecrypteSplash`,
 * maquette 12a), en version **compacte et statique** : ici elle est un logo
 * dans une carte, pas une animation d'attente qui se retrace en boucle.
 *
 * ⚠️ La maquette annonçait « les votes EN DIRECT ». Les données viennent d'une
 * ingestion par lots de l'open data : rien n'est en direct, et l'écrire serait
 * promettre ce que l'app ne fait pas (§2.5). On décrit ce qu'elle fait.
 */

/** Silhouette du chat — mêmes tracés que le splash, à l'échelle de la carte. */
const SILHOUETTE = [
  'M46 138 L44 108 L54 72 L62 44 L78 66 L86 62 L94 64 L104 42 L114 70 L150 72 L186 92 L198 120 L190 144 L150 150 L100 150 Z',
  'M198 120 L214 138 L206 156 L176 158 L150 150',
];

const ETOILES: { x: number; y: number; r: number; b?: boolean }[] = [
  { x: 46, y: 138, r: 2.4 },
  { x: 44, y: 108, r: 2.4 },
  { x: 54, y: 72, r: 2.4 },
  { x: 62, y: 44, r: 3.4, b: true },
  { x: 78, y: 66, r: 2.2 },
  { x: 94, y: 64, r: 2.2 },
  { x: 104, y: 42, r: 3.4, b: true },
  { x: 114, y: 70, r: 2.2 },
  { x: 150, y: 72, r: 2.6 },
  { x: 186, y: 92, r: 3.4, b: true },
  { x: 198, y: 120, r: 3.4, b: true },
  { x: 190, y: 144, r: 2.4 },
  { x: 150, y: 150, r: 2.4 },
  { x: 100, y: 150, r: 2.4 },
  { x: 214, y: 138, r: 2.4 },
  { x: 206, y: 156, r: 2.2 },
  { x: 176, y: 158, r: 2.2 },
];

/** Ce que l'app fait — trois faits, pas trois promesses. */
const REPERES = [
  'Chaque vote de l’Assemblée et du Sénat, texte par texte',
  'Le détail par groupe, et le nom des votants quand la source le publie',
  'Chaque affirmation reliée à son document officiel',
];

export function OnboardingBienvenue() {
  // Respiration lente, comme le splash : le seul mouvement de l'écran.
  const souffle = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(souffle, {
          toValue: 1,
          duration: 4400,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(souffle, {
          toValue: 0,
          duration: 4400,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ]),
    );
    anim.start();
    return () => anim.stop();
  }, [souffle]);
  const scale = souffle.interpolate({ inputRange: [0, 1], outputRange: [1, 1.02] });
  const translateY = souffle.interpolate({ inputRange: [0, 1], outputRange: [0, -4] });

  return (
    <View style={styles.centre}>
      <Animated.View style={[styles.carte, { transform: [{ scale }, { translateY }] }]}>
        <Svg width={168} height={124} viewBox="0 0 240 176">
          <Defs>
            <RadialGradient id="halo-bienvenue" cx="50%" cy="50%" r="50%">
              <Stop offset="0%" stopColor={colors.brand} stopOpacity={0.28} />
              <Stop offset="70%" stopColor={colors.brand} stopOpacity={0} />
            </RadialGradient>
          </Defs>
          <Circle cx={120} cy={100} r={110} fill="url(#halo-bienvenue)" />
          {SILHOUETTE.map((d, i) => (
            <Path
              key={i}
              d={d}
              stroke={colors.splashLigne}
              strokeWidth={1.6}
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
              opacity={0.75}
            />
          ))}
          <Path
            d="M58 108 q 9 7 18 0"
            stroke={colors.splashLigneSoft}
            strokeWidth={1.6}
            strokeLinecap="round"
            fill="none"
          />
          {ETOILES.map((e, i) => (
            <Circle
              key={`e${i}`}
              cx={e.x}
              cy={e.y}
              r={e.r}
              fill={e.b ? colors.splashEtoileVive : colors.splashEtoile}
            />
          ))}
        </Svg>
      </Animated.View>

      <Text style={styles.marque}>Décrypté</Text>
      <Text style={styles.tagline}>La démocratie dans votre poche</Text>
      <Text style={styles.chapeau}>
        Comprendre en 30 secondes sur quoi les députés et les sénateurs ont voté, et ce
        que dit le texte.
      </Text>

      <View style={styles.reperes}>
        {REPERES.map((repere) => (
          <View key={repere} style={styles.repere}>
            <View style={styles.puce} importantForAccessibility="no" />
            <Text style={styles.repereTexte}>{repere}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  centre: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xxl,
  },
  carte: {
    width: 200,
    height: 148,
    borderRadius: radius.xxl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: 'rgba(139,156,244,0.20)',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  marque: {
    marginTop: spacing.xxl + spacing.xs,
    fontFamily: serifDisplay,
    fontSize: 38,
    lineHeight: 44,
    letterSpacing: -0.6,
    color: colors.textPrimary,
  },
  tagline: {
    marginTop: spacing.sm,
    fontFamily: mono,
    fontSize: 10.5,
    fontWeight: '700',
    letterSpacing: 1.7,
    textTransform: 'uppercase',
    color: colors.brand,
    textAlign: 'center',
  },
  chapeau: {
    ...typography.bodySecondary,
    marginTop: spacing.lg,
    textAlign: 'center',
    maxWidth: 290,
  },
  reperes: { marginTop: spacing.xxl, gap: spacing.md, alignSelf: 'stretch' },
  repere: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.md },
  puce: {
    width: 5,
    height: 5,
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
    marginTop: 7,
  },
  repereTexte: { ...typography.bodySecondary, flex: 1, fontSize: 13.5 },
});
