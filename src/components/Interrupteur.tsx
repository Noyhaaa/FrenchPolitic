import { useEffect, useRef } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

/**
 * Interrupteur d'un réglage (première occurrence de l'app : la préférence
 * d'alerte du parcours d'accueil).
 *
 * Écrit à la main plutôt que le `Switch` de React Native, dont la couleur et
 * la taille ne se règlent pas de la même façon sur iOS et Android — il ne
 * tiendrait pas la charte. Animé avec l'API `Animated` intégrée, comme le
 * splash (pas de reanimated dans le projet).
 *
 * L'état est **écrit** (« Activées » / « Désactivées ») : la position du curseur
 * ne le porte pas seule (RGAA, §8).
 */

const PISTE_LARGEUR = 50;
const CURSEUR = 20;
const MARGE = 4;

interface Props {
  actif: boolean;
  onToggle: () => void;
  titre: string;
  /** Précision factuelle sous le titre (ce que le réglage fait, ou pas). */
  detail?: string;
}

export function Interrupteur({ actif, onToggle, titre, detail }: Props) {
  const position = useRef(new Animated.Value(actif ? 1 : 0)).current;

  useEffect(() => {
    const anim = Animated.timing(position, {
      toValue: actif ? 1 : 0,
      duration: 180,
      useNativeDriver: true,
    });
    anim.start();
    return () => anim.stop();
  }, [actif, position]);

  const translateX = position.interpolate({
    inputRange: [0, 1],
    outputRange: [0, PISTE_LARGEUR - CURSEUR - MARGE * 2],
  });

  return (
    <Pressable
      onPress={onToggle}
      accessibilityRole="switch"
      accessibilityState={{ checked: actif }}
      accessibilityLabel={titre}
      style={({ pressed }) => [
        styles.ligne,
        actif && styles.ligneActive,
        pressed && styles.pressee,
      ]}
    >
      <View style={styles.textes}>
        <Text style={styles.titre}>{titre}</Text>
        {detail ? <Text style={styles.detail}>{detail}</Text> : null}
      </View>
      <View style={[styles.piste, actif && styles.pisteActive]}>
        <Animated.View style={[styles.curseur, { transform: [{ translateX }] }]} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  ligne: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingVertical: spacing.lg - 1,
    paddingHorizontal: spacing.lg,
  },
  ligneActive: { borderColor: 'rgba(139,156,244,0.35)', backgroundColor: colors.brandSoft },
  pressee: { opacity: 0.85 },
  textes: { flex: 1, gap: 2 },
  titre: { ...typography.label, fontSize: 14, color: colors.textPrimary },
  detail: { ...typography.meta, color: colors.textTertiary },
  piste: {
    width: PISTE_LARGEUR,
    height: CURSEUR + MARGE * 2,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    padding: MARGE,
    justifyContent: 'center',
  },
  pisteActive: { backgroundColor: colors.brand },
  curseur: {
    width: CURSEUR,
    height: CURSEUR,
    borderRadius: radius.pill,
    backgroundColor: colors.textPrimary,
  },
});
