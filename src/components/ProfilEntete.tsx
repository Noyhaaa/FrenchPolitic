import { StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

import { colors, radius, serifDisplay, spacing, typography } from '@/theme';
import { AnneauCouverture } from './AnneauCouverture';
import { IconLigne } from './IconLigne';
import { ProfilCiel } from './ProfilCiel';

/**
 * En-tête du profil — ciel, médaillon débordant, identité, anneau de couverture.
 *
 * ⚠️ Le compte est **facultatif** : rien de structurel ne change sans lui. Seuls
 * le médaillon (initiales ↔ pictogramme) et le titre changent, et l'anneau reste
 * identique — il décrit les préférences de cet appareil, pas une session.
 */

const HAUTEUR_CIEL = 210;
const MEDAILLON = 96;
const DEBORD = 36;

interface Props {
  insetTop: number;
  anime: boolean;
  /** Initiales du compte, `null` sans compte. */
  initiales: string | null;
  /** « Prénom Nom », ou « Vos réglages » sans compte. */
  titre: string;
  departement: string | null;
  sansCompte: boolean;
  couverture: { suivis: number; total: number };
  onAnneauPress: () => void;
}

function Medaillon({ initiales }: { initiales: string | null }) {
  if (!initiales) {
    // Pas de « ? » : ça se lirait comme une erreur de chargement.
    return (
      <View style={[styles.medaillon, styles.medaillonVide]} importantForAccessibility="no">
        <IconLigne name="personne" color={colors.textTertiary} size={36} strokeWidth={1.5} />
      </View>
    );
  }
  return (
    <LinearGradient
      colors={[colors.brand, colors.brandProfond]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.medaillon}
    >
      <Text style={styles.initiales} importantForAccessibility="no">
        {initiales}
      </Text>
    </LinearGradient>
  );
}

export function ProfilEntete({
  insetTop,
  anime,
  initiales,
  titre,
  departement,
  sansCompte,
  couverture,
  onAnneauPress,
}: Props) {
  return (
    // ⚠️ Pas d'`overflow:'hidden'` : le médaillon déborde du ciel.
    <View>
      <ProfilCiel hauteur={HAUTEUR_CIEL} insetTop={insetTop} anime={anime} />

      {/* Ancré au bas du ciel, dont il déborde de `DEBORD`. On positionne par le
          haut : `bottom` se rapporterait à l'en-tête entier, pas au ciel. */}
      <View
        style={[styles.ancreMedaillon, { top: insetTop + HAUTEUR_CIEL - MEDAILLON + DEBORD }]}
        pointerEvents="none"
      >
        <Medaillon initiales={initiales} />
      </View>

      <View style={styles.identite}>
        <View style={styles.textes}>
          <Text style={styles.nom}>{titre}</Text>
          {departement ? (
            <View style={styles.ligneDep}>
              <IconLigne name="epingle" color={colors.brand} size={14} strokeWidth={1.8} />
              <Text style={styles.dep}>{departement}</Text>
            </View>
          ) : null}
          {sansCompte ? (
            <View style={styles.pastille}>
              <Text style={styles.pastilleTexte}>Sans compte</Text>
            </View>
          ) : null}
        </View>

        <AnneauCouverture
          suivis={couverture.suivis}
          total={couverture.total}
          onPress={onAnneauPress}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  ancreMedaillon: { position: 'absolute', left: spacing.xl },
  medaillon: {
    width: MEDAILLON,
    height: MEDAILLON,
    borderRadius: radius.xxl,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    borderColor: colors.background,
  },
  medaillonVide: { backgroundColor: colors.surfaceAlt },
  initiales: {
    fontFamily: serifDisplay,
    fontSize: 30,
    color: colors.textOnAccent,
    letterSpacing: 0.5,
  },
  identite: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.lg,
    paddingHorizontal: spacing.xl,
    marginTop: DEBORD + spacing.md,
  },
  textes: { flex: 1, gap: spacing.xs + 2 },
  nom: {
    fontFamily: serifDisplay,
    fontSize: 27,
    lineHeight: 32,
    letterSpacing: -0.5,
    color: colors.textPrimary,
  },
  ligneDep: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs + 2 },
  dep: { ...typography.label, color: colors.textSecondary },
  pastille: {
    alignSelf: 'flex-start',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    paddingVertical: 3,
    paddingHorizontal: spacing.sm + 2,
    marginTop: spacing.xs,
  },
  pastilleTexte: { ...typography.badge, color: colors.textSecondary },
});
