import { Children, Fragment, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import { IconLigne, type NomIcone } from './IconLigne';

/**
 * Carte de réglages et sa rangée — le gabarit de la maquette du profil : une
 * tuile d'icône teintée, un petit libellé, sa valeur, un chevron.
 *
 * Les deux vivent dans le même fichier : ils forment un seul système visuel
 * (même gouttière, séparateur aligné sur la colonne de texte).
 *
 * ⚠️ Le chevron n'apparaît **que** si la rangée fait quelque chose. Une
 * affordance qui ne mène nulle part est un mensonge d'interface (§2.5) — c'est
 * la même règle que la carte « À l'origine du texte », non pressable sans
 * `deputeId`.
 */

const TUILE = 34;

export function CarteRangees({ children }: { children: ReactNode }) {
  const rangees = Children.toArray(children).filter(Boolean);
  return (
    <View style={styles.carte}>
      {rangees.map((rangee, i) => (
        <Fragment key={i}>
          {i > 0 ? <View style={styles.separateur} /> : null}
          {rangee}
        </Fragment>
      ))}
    </View>
  );
}

interface RangeeProps {
  icone: NomIcone;
  /** Petit libellé au-dessus de la valeur (« E-mail », « Département »). */
  label: string;
  /** Valeur principale. `null` → « Non renseigné ». */
  valeur: string | null;
  /** Seconde ligne factuelle. */
  detail?: string;
  /** Absent → rangée non interactive, sans chevron. */
  onPress?: () => void;
  /** Ce que fait le tap, pour un lecteur d'écran. */
  action?: string;
  /** `neutre` pour une rangée sans accent de marque. */
  ton?: 'brand' | 'neutre';
}

export function RangeeReglage({
  icone,
  label,
  valeur,
  detail,
  onPress,
  action,
  ton = 'brand',
}: RangeeProps) {
  const neutre = ton === 'neutre';
  const renseignee = valeur !== null;

  const contenu = (
    <>
      <View style={[styles.tuile, neutre && styles.tuileNeutre]}>
        <IconLigne
          name={icone}
          color={neutre ? colors.textSecondary : colors.brand}
          size={17}
          strokeWidth={1.7}
        />
      </View>
      <View style={styles.textes}>
        <Text style={styles.label}>{label}</Text>
        <Text style={[styles.valeur, !renseignee && styles.valeurVide]} numberOfLines={1}>
          {valeur ?? 'Non renseigné'}
        </Text>
        {detail ? <Text style={styles.detail}>{detail}</Text> : null}
      </View>
      {onPress ? (
        <IconLigne name="chevronDroite" color={colors.textTertiary} size={16} strokeWidth={1.8} />
      ) : null}
    </>
  );

  if (!onPress) {
    return <View style={styles.rangee}>{contenu}</View>;
  }

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.rangee, pressed && styles.pressee]}
      accessibilityRole="button"
      accessibilityLabel={`${label} : ${valeur ?? 'non renseigné'}`}
      accessibilityHint={action}
    >
      {contenu}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  carte: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.xxl,
    overflow: 'hidden',
  },
  // Le trait démarre après la tuile, sur la colonne de texte.
  separateur: {
    height: 1,
    backgroundColor: colors.border,
    marginLeft: spacing.lg + TUILE + spacing.md,
  },
  rangee: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md + 2,
    paddingHorizontal: spacing.lg,
  },
  pressee: { opacity: 0.85 },
  tuile: {
    width: TUILE,
    height: TUILE,
    borderRadius: radius.md,
    backgroundColor: colors.brandSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tuileNeutre: { backgroundColor: colors.surfaceAlt },
  textes: { flex: 1, gap: 1 },
  label: { ...typography.meta, color: colors.miniLabel },
  valeur: { ...typography.label, fontSize: 14, color: colors.textPrimary },
  valeurVide: { color: colors.textTertiary },
  detail: { ...typography.meta },
});
