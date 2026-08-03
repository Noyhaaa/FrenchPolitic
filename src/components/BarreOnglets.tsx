import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

/**
 * Barre d'onglets segmentée (pilule) — sections d'un même écran.
 *
 * La sélection se lit comme partout ailleurs dans l'app (fond clair, texte
 * sombre, cf. `Chip`) : introduire ici une troisième grammaire de sélection —
 * la maquette accentuait l'onglet actif en rouge — casserait la lecture, et ce
 * rouge-là veut dire « rejeté » dans toute l'app.
 *
 * L'état n'est jamais porté par la seule couleur : `accessibilityState`
 * l'annonce et le contraste s'inverse (RGAA §8).
 */

interface Props<T extends string> {
  onglets: readonly { cle: T; label: string }[];
  actif: T;
  onChange: (cle: T) => void;
  /** Ce que l'onglet sélectionne, pour un lecteur d'écran. */
  contexte?: string;
}

export function BarreOnglets<T extends string>({
  onglets,
  actif,
  onChange,
  contexte,
}: Props<T>) {
  return (
    <View style={styles.barre} accessibilityRole="tablist">
      {onglets.map((o) => {
        const selectionne = o.cle === actif;
        return (
          <Pressable
            key={o.cle}
            onPress={() => onChange(o.cle)}
            style={[styles.onglet, selectionne && styles.ongletActif]}
            accessibilityRole="tab"
            accessibilityState={{ selected: selectionne }}
            accessibilityLabel={contexte ? `${o.label} · ${contexte}` : o.label}
          >
            <Text style={[styles.texte, selectionne && styles.texteActif]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  barre: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: 4,
    gap: 4,
  },
  onglet: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.sm + 1,
    borderRadius: radius.md,
  },
  ongletActif: { backgroundColor: colors.textPrimary },
  texte: { ...typography.label, color: colors.textTertiary },
  texteActif: { color: colors.textOnLight },
});
