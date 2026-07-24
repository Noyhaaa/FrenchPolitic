import { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Defs, Path, RadialGradient, Stop } from 'react-native-svg';
import { colors, mono, serifDisplay, spacing } from '@/theme';

/**
 * Splash / écran de lancement « Décrypté » — le chat-constellation.
 *
 * Reprise fidèle de la maquette 12a : des étoiles pervenche s'allument une à une
 * et des traits lumineux se tracent pour dessiner un chat roulé en boule qui dort,
 * puis la constellation se retrace en boucle. Respiration lente, scintillement,
 * poussière d'étoiles, « Zzz », halo — dans la charte sombre de l'app.
 *
 * Porté sur l'API `Animated` intégrée de React Native (pas de reanimated).
 * Les props SVG animées (`strokeDashoffset`, `r`, `opacity` d'un `Circle`)
 * exigent `useNativeDriver:false` ; les transforms/opacité de `View`/`Text`
 * (respiration, « Zzz ») tournent en `useNativeDriver:true`.
 *
 * Animation décorative en boucle (pas de progression réelle) : on monte/démonte
 * le composant selon l'état `ready` du lancement (cf. App.tsx).
 */

const CYCLE = 6000; // durée d'un cycle complet (ms)

const AnimatedPath = Animated.createAnimatedComponent(Path);
const AnimatedCircle = Animated.createAnimatedComponent(Circle);

/** Segments tracés (silhouette du chat). len ≈ longueur du tracé. */
const LIGNES: { d: string; len: number; delay: number; color: string; w: number }[] = [
  {
    d: 'M46 138 L44 108 L54 72 L62 44 L78 66 L86 62 L94 64 L104 42 L114 70 L150 72 L186 92 L198 120 L190 144 L150 150 L100 150 Z',
    len: 480,
    delay: 0,
    color: colors.splashLigne,
    w: 1.6,
  },
  {
    d: 'M198 120 L214 138 L206 156 L176 158 L150 150',
    len: 110,
    delay: 500,
    color: colors.splashLigne,
    w: 1.6,
  },
  { d: 'M58 108 q 9 7 18 0', len: 26, delay: 1200, color: colors.splashLigneSoft, w: 1.6 }, // œil clos
  { d: 'M50 120 L58 124', len: 10, delay: 1400, color: colors.splashLigneSoft, w: 1.6 }, // museau
];

/** Étoiles aux sommets. r = rayon, b = brillante (blanche). */
const ETOILES: { x: number; y: number; r: number; delay: number; b?: boolean }[] = [
  { x: 46, y: 138, r: 2.4, delay: 0 },
  { x: 44, y: 108, r: 2.4, delay: 100 },
  { x: 54, y: 72, r: 2.4, delay: 200 },
  { x: 62, y: 44, r: 3.4, delay: 300, b: true },
  { x: 78, y: 66, r: 2.2, delay: 400 },
  { x: 86, y: 62, r: 2, delay: 500 },
  { x: 94, y: 64, r: 2.2, delay: 600 },
  { x: 104, y: 42, r: 3.4, delay: 700, b: true },
  { x: 114, y: 70, r: 2.2, delay: 800 },
  { x: 150, y: 72, r: 2.6, delay: 950 },
  { x: 186, y: 92, r: 3.4, delay: 1100, b: true },
  { x: 198, y: 120, r: 3.4, delay: 1250, b: true },
  { x: 190, y: 144, r: 2.4, delay: 1400 },
  { x: 150, y: 150, r: 2.4, delay: 1550 },
  { x: 100, y: 150, r: 2.4, delay: 1700 },
  { x: 214, y: 138, r: 2.4, delay: 1850 },
  { x: 206, y: 156, r: 2.2, delay: 2000 },
  { x: 176, y: 158, r: 2.2, delay: 2150 },
];

/** Poussière d'étoiles autour (scintille seulement). */
const POUSSIERE = [
  { x: 24, y: 60, r: 1.2, dur: 3400, delay: 200 },
  { x: 224, y: 60, r: 1.4, dur: 2800, delay: 800 },
  { x: 120, y: 24, r: 1.2, dur: 3600, delay: 1100 },
  { x: 34, y: 150, r: 1.2, dur: 3000, delay: 1600 },
  { x: 216, y: 100, r: 1.2, dur: 3200, delay: 500 },
];

function Ligne({ d, len, delay, color, w }: (typeof LIGNES)[number]) {
  const p = useRef(new Animated.Value(0)).current; // 0 caché → 1 tracé
  useEffect(() => {
    const anim = Animated.sequence([
      Animated.delay(delay),
      Animated.loop(
        Animated.sequence([
          Animated.timing(p, {
            toValue: 1,
            duration: CYCLE * 0.34,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }), // tracé
          Animated.timing(p, { toValue: 1, duration: CYCLE * 0.58, useNativeDriver: false }), // maintien
          Animated.timing(p, { toValue: 0, duration: 1, useNativeDriver: false }), // reset instantané → retrace
          Animated.timing(p, { toValue: 0, duration: CYCLE * 0.08, useNativeDriver: false }),
        ]),
      ),
    ]);
    anim.start();
    return () => anim.stop();
  }, [delay, p]);
  const strokeDashoffset = p.interpolate({ inputRange: [0, 1], outputRange: [len, 0] });
  return (
    <AnimatedPath
      d={d}
      stroke={color}
      strokeWidth={w}
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
      strokeDasharray={len}
      strokeDashoffset={strokeDashoffset}
    />
  );
}

function Etoile({ x, y, r, delay, b }: (typeof ETOILES)[number]) {
  const o = useRef(new Animated.Value(0)).current;
  const s = useRef(new Animated.Value(0.85)).current;
  useEffect(() => {
    // apparition puis scintillement continu
    const apparition = Animated.sequence([
      Animated.delay(delay),
      Animated.timing(o, { toValue: 1, duration: 500, useNativeDriver: false }),
    ]);
    const scintille = Animated.sequence([
      Animated.delay(delay),
      Animated.loop(
        Animated.sequence([
          Animated.timing(s, {
            toValue: 1.12,
            duration: 1500,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
          Animated.timing(s, {
            toValue: 0.85,
            duration: 1500,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
        ]),
      ),
    ]);
    apparition.start();
    scintille.start();
    return () => {
      apparition.stop();
      scintille.stop();
    };
  }, [delay, o, s]);
  const rAnim = s.interpolate({ inputRange: [0.85, 1.12], outputRange: [r * 0.85, r * 1.12] });
  return (
    <AnimatedCircle
      cx={x}
      cy={y}
      r={rAnim}
      opacity={o}
      fill={b ? colors.splashEtoileVive : colors.splashEtoile}
    />
  );
}

function Poussiere({ x, y, r, dur, delay }: (typeof POUSSIERE)[number]) {
  const s = useRef(new Animated.Value(0.82)).current;
  useEffect(() => {
    const anim = Animated.sequence([
      Animated.delay(delay),
      Animated.loop(
        Animated.sequence([
          Animated.timing(s, {
            toValue: 1.12,
            duration: dur,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
          Animated.timing(s, {
            toValue: 0.82,
            duration: dur,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
        ]),
      ),
    ]);
    anim.start();
    return () => anim.stop();
  }, [delay, dur, s]);
  const rAnim = s.interpolate({ inputRange: [0.82, 1.12], outputRange: [r * 0.82, r * 1.12] });
  const opacity = s.interpolate({ inputRange: [0.82, 1.12], outputRange: [0.5, 0.8] });
  return <AnimatedCircle cx={x} cy={y} r={rAnim} opacity={opacity} fill={colors.brand} />;
}

function Zzz() {
  return (
    <View style={styles.zzz} pointerEvents="none">
      <ZChar size={14} delay={0} left={0} top={16} />
      <ZChar size={18} delay={600} left={12} top={4} />
      <ZChar size={23} delay={1200} left={27} top={-6} upper />
    </View>
  );
}
function ZChar({
  size,
  delay,
  left,
  top,
  upper,
}: {
  size: number;
  delay: number;
  left: number;
  top: number;
  upper?: boolean;
}) {
  const t = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const anim = Animated.sequence([
      Animated.delay(delay),
      Animated.loop(Animated.timing(t, { toValue: 1, duration: 2800, useNativeDriver: true })),
    ]);
    anim.start();
    return () => anim.stop();
  }, [delay, t]);
  const opacity = t.interpolate({ inputRange: [0, 0.2, 0.55, 1], outputRange: [0, 1, 1, 0] });
  const translateX = t.interpolate({ inputRange: [0, 1], outputRange: [0, 13] });
  const translateY = t.interpolate({ inputRange: [0, 1], outputRange: [0, -32] });
  const scale = t.interpolate({ inputRange: [0, 1], outputRange: [0.5, 1.15] });
  return (
    <Animated.Text
      style={[
        styles.z,
        { fontSize: size, left, top, opacity, transform: [{ translateX }, { translateY }, { scale }] },
      ]}
    >
      {upper ? 'Z' : 'z'}
    </Animated.Text>
  );
}

export function DecrypteSplash({
  tagline = 'On veille, vous dormez tranquille',
}: {
  tagline?: string;
}) {
  // respiration lente de toute la constellation
  const breathe = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(breathe, {
          toValue: 1,
          duration: 4400,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(breathe, {
          toValue: 0,
          duration: 4400,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ]),
    );
    anim.start();
    return () => anim.stop();
  }, [breathe]);
  const translateY = breathe.interpolate({ inputRange: [0, 1], outputRange: [0, -3] });
  const scale = breathe.interpolate({ inputRange: [0, 1], outputRange: [1, 1.012] });

  return (
    <View style={styles.root}>
      <View style={styles.stage}>
        <View style={styles.halo} pointerEvents="none">
          <Svg width={300} height={260} viewBox="0 0 300 260">
            <Defs>
              <RadialGradient id="halo" cx="50%" cy="50%" r="50%">
                <Stop offset="0%" stopColor={colors.brand} stopOpacity={0.32} />
                <Stop offset="62%" stopColor={colors.brand} stopOpacity={0} />
              </RadialGradient>
            </Defs>
            <Circle cx={150} cy={130} r={130} fill="url(#halo)" />
          </Svg>
        </View>

        <Animated.View style={{ transform: [{ translateY }, { scale }] }}>
          <Svg width={270} height={200} viewBox="0 0 240 176">
            {LIGNES.map((l, i) => (
              <Ligne key={`l${i}`} {...l} />
            ))}
            {ETOILES.map((s, i) => (
              <Etoile key={`s${i}`} {...s} />
            ))}
            {POUSSIERE.map((s, i) => (
              <Poussiere key={`p${i}`} {...s} />
            ))}
          </Svg>
        </Animated.View>

        <Zzz />
      </View>

      <Text style={styles.word}>Décrypté</Text>
      <Text style={styles.tag}>{tagline.toUpperCase()}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center' },
  stage: { width: 270, height: 200, alignItems: 'center', justifyContent: 'center' },
  halo: { position: 'absolute', alignItems: 'center', justifyContent: 'center' },
  zzz: { position: 'absolute', right: 26, top: 0, width: 60, height: 60 },
  z: { position: 'absolute', color: colors.splashLigne, fontFamily: mono, fontWeight: '700' },
  word: {
    marginTop: spacing.xxl,
    fontFamily: serifDisplay,
    fontSize: 34,
    color: colors.textPrimary,
    letterSpacing: -0.4,
  },
  tag: {
    marginTop: spacing.md,
    fontFamily: mono,
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 2,
    color: colors.miniLabel,
  },
});
