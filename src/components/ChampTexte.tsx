import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import type { KeyboardTypeOptions, TextInputProps } from 'react-native';

import { colors, mono, radius, spacing, typography } from '@/theme';
import { IconLigne, type NomIcone } from './IconLigne';

/**
 * Champ de saisie du parcours d'inscription et de la connexion.
 *
 * Reprend le gabarit du champ de recherche déjà en place (`DeputesScreen`,
 * `ExplorerScreen`) : même hauteur, même rayon, icône à gauche. S'y ajoutent
 * les états d'un formulaire — focus, saisie conforme, saisie à corriger.
 *
 * L'état n'est **jamais porté par la seule couleur** (RGAA, §8) : une saisie
 * conforme affiche un ✓ dessiné, une saisie à corriger affiche un « ! » **et**
 * la phrase qui dit quoi corriger.
 */

interface Props {
  label: string;
  icone: NomIcone;
  valeur: string;
  onChangeText: (v: string) => void;
  placeholder: string;
  /** `undefined` = pas encore jugé (champ vide) : ni vert ni rouge. */
  valide?: boolean;
  /** Ce qu'il faut corriger — affiché seulement quand `valide === false`. */
  aide?: string;
  secret?: boolean;
  /** Bascule « afficher le mot de passe » (posée par l'appelant). */
  onBasculerSecret?: () => void;
  keyboardType?: KeyboardTypeOptions;
  autoCapitalize?: TextInputProps['autoCapitalize'];
  textContentType?: TextInputProps['textContentType'];
  returnKeyType?: TextInputProps['returnKeyType'];
  onSubmitEditing?: () => void;
}

export function ChampTexte({
  label,
  icone,
  valeur,
  onChangeText,
  placeholder,
  valide,
  aide,
  secret = false,
  onBasculerSecret,
  keyboardType,
  autoCapitalize = 'none',
  textContentType,
  returnKeyType = 'next',
  onSubmitEditing,
}: Props) {
  const [focus, setFocus] = useState(false);
  const rempli = valeur.length > 0;
  const conforme = rempli && valide === true;
  const aCorriger = rempli && valide === false;

  const bordure = aCorriger
    ? colors.invalide
    : conforme
      ? colors.valide
      : focus
        ? colors.champBordureFocus
        : colors.champBordure;

  return (
    <View style={styles.bloc}>
      <Text style={[styles.label, focus && styles.labelFocus]}>{label}</Text>
      <View
        style={[
          styles.cadre,
          { borderColor: bordure },
          focus && { backgroundColor: colors.champFondFocus },
        ]}
      >
        <IconLigne
          name={icone}
          color={focus ? colors.textSecondary : colors.textTertiary}
          size={17}
          strokeWidth={1.7}
        />
        <TextInput
          value={valeur}
          onChangeText={onChangeText}
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          placeholder={placeholder}
          placeholderTextColor={colors.textTertiary}
          secureTextEntry={secret}
          keyboardType={keyboardType}
          autoCapitalize={autoCapitalize}
          autoCorrect={false}
          textContentType={textContentType}
          returnKeyType={returnKeyType}
          onSubmitEditing={onSubmitEditing}
          accessibilityLabel={label}
          style={styles.saisie}
        />
        {onBasculerSecret ? (
          <Pressable
            onPress={onBasculerSecret}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityLabel={
              secret ? 'Afficher le mot de passe' : 'Masquer le mot de passe'
            }
          >
            <IconLigne
              name={secret ? 'oeil' : 'oeilBarre'}
              color={colors.textTertiary}
              size={17}
              strokeWidth={1.7}
            />
          </Pressable>
        ) : conforme ? (
          <IconLigne name="check" color={colors.valide} size={16} strokeWidth={2.2} />
        ) : aCorriger ? (
          <View style={styles.alerte}>
            <Text style={styles.alerteTexte}>!</Text>
          </View>
        ) : null}
      </View>
      {aCorriger && aide ? <Text style={styles.aide}>{aide}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  bloc: { flex: 1, gap: spacing.xs + 2 },
  label: {
    fontFamily: mono,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.3,
    textTransform: 'uppercase',
    color: colors.textTertiary,
  },
  labelFocus: { color: colors.textSecondary },
  cadre: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md - 2,
    backgroundColor: colors.champFond,
    borderWidth: 1.5,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.lg - 1,
    height: 52,
  },
  saisie: { flex: 1, ...typography.body, paddingVertical: 0 },
  alerte: {
    width: 17,
    height: 17,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(232,105,94,0.22)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  alerteTexte: { ...typography.badge, fontSize: 10, color: colors.invalide },
  aide: { ...typography.meta, color: colors.invalide, marginLeft: spacing.xs },
});
