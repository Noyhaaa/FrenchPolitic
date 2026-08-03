import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

/**
 * Action principale d'un écran (parcours d'inscription, connexion).
 *
 * L'accent est la **pervenche de la marque**, jamais le rouge : dans cette app
 * `colors.rejete` (#FF3040) veut dire « rejeté », et un bouton rouge se lirait
 * comme un verdict de vote.
 *
 * Désactivé, le bouton reste **lisible et présent** (il n'est pas masqué) et
 * son libellé dit ce qui manque — « Choisir encore 2 » plutôt qu'un
 * « Continuer » grisé sans explication.
 */

interface Props {
  label: string;
  onPress: () => void;
  /** Grisé : l'action n'est pas encore possible. */
  desactive?: boolean;
  /** Action en cours (appel réseau) : le bouton ne se presse plus. */
  enCours?: boolean;
  /** Variante discrète, pour une action secondaire de même rang visuel. */
  variante?: 'plein' | 'contour';
}

export function BoutonPrincipal({
  label,
  onPress,
  desactive = false,
  enCours = false,
  variante = 'plein',
}: Props) {
  const inactif = desactive || enCours;
  const contour = variante === 'contour';

  return (
    <Pressable
      onPress={onPress}
      disabled={inactif}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: inactif, busy: enCours }}
      style={({ pressed }) => [
        styles.bouton,
        contour ? styles.contour : styles.plein,
        inactif && (contour ? styles.contourInactif : styles.pleinInactif),
        pressed && !inactif && styles.presse,
      ]}
    >
      {enCours ? (
        <View style={styles.chargement}>
          <ActivityIndicator size="small" color={colors.textOnAccent} />
          <Text style={[styles.label, styles.labelInactif]}>{label}</Text>
        </View>
      ) : (
        <Text
          style={[
            styles.label,
            contour && styles.labelContour,
            inactif && styles.labelInactif,
          ]}
        >
          {label}
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  bouton: {
    borderRadius: radius.lg,
    paddingVertical: spacing.lg - 1,
    paddingHorizontal: spacing.xl,
    alignItems: 'center',
    justifyContent: 'center',
  },
  plein: { backgroundColor: colors.brand },
  pleinInactif: { backgroundColor: colors.surfaceAlt },
  contour: { borderWidth: 1, borderColor: 'rgba(139,156,244,0.30)' },
  contourInactif: { borderColor: colors.border },
  presse: { opacity: 0.85, transform: [{ scale: 0.995 }] },
  chargement: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  label: { ...typography.label, fontSize: 15, color: colors.textOnAccent },
  labelContour: { color: colors.brand },
  labelInactif: { color: colors.textTertiary },
});
