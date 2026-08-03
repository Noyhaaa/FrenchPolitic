import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, radius, spacing, typography } from '@/theme';
import { IconLigne } from './IconLigne';
import { OnboardingDepartement } from './OnboardingDepartement';

/**
 * Choix du département depuis le profil — feuille posée par-dessus l'écran.
 *
 * On **réutilise l'étape du parcours d'accueil telle quelle** : le département
 * se choisit donc à l'identique aux deux endroits, et la liste reste dérivée de
 * l'annuaire réel (aucun département écrit en dur).
 *
 * ⚠️ **Un calque interne à l'écran, pas un `Modal`.** La contrainte est que le
 * `ScrollView` en `flex:1` de l'étape (et son `TextInput`) ne soit pas
 * **imbriqué** dans celui du profil — sinon il s'effondre ou capte le geste. Un
 * frère en `position:'absolute'` du `ScrollView` le règle sans faire intervenir
 * de vue hôte native, dont le cycle de vie est une source d'ennuis sur iOS
 * (touches avalées après fermeture).
 *
 * Corollaire assumé : la barre d'onglets reste visible au-dessus — d'où le
 * `paddingBottom` qui dégage la fin de liste.
 */

const HAUTEUR_BARRE_ONGLETS = 64;

interface Props {
  visible: boolean;
  selection: string | null;
  /** Re-toucher le département courant le retire (`null`). */
  onSelect: (departement: string | null) => void;
  onFermer: () => void;
}

export function SelecteurDepartement({ visible, selection, onSelect, onFermer }: Props) {
  const insets = useSafeAreaInsets();
  if (!visible) return null;

  return (
    <View style={StyleSheet.absoluteFill}>
      <Pressable
        style={[styles.voile, { height: insets.top + spacing.xxl }]}
        onPress={onFermer}
        accessibilityRole="button"
        accessibilityLabel="Fermer le choix du département"
      />
      <View
        style={[
          styles.feuille,
          { paddingBottom: insets.bottom + HAUTEUR_BARRE_ONGLETS },
        ]}
      >
        <Pressable
          onPress={onFermer}
          style={({ pressed }) => [styles.tete, pressed && styles.pressee]}
          accessibilityRole="button"
          accessibilityLabel="Fermer le choix du département"
        >
          <IconLigne
            name="chevronGauche"
            color={colors.textSecondary}
            size={18}
            strokeWidth={1.9}
          />
          <Text style={styles.fermer}>Fermer</Text>
        </Pressable>

        <OnboardingDepartement selection={selection} onSelect={onSelect} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  voile: { backgroundColor: colors.overlay },
  feuille: {
    flex: 1,
    backgroundColor: colors.background,
    borderTopLeftRadius: radius.xxl,
    borderTopRightRadius: radius.xxl,
    borderTopWidth: 1,
    borderColor: colors.borderStrong,
  },
  tete: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.lg,
  },
  pressee: { opacity: 0.85 },
  fermer: { ...typography.label, color: colors.textSecondary },
});
