import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, mono, radius, serifDisplay, spacing, typography } from '@/theme';
import { themeEmoji } from '@/constants/themes';
import type { Preferences } from '@/types';
import { IconLigne } from './IconLigne';
import { Interrupteur } from './Interrupteur';

/**
 * Étape 5 — la préférence d'alerte, et le récapitulatif.
 *
 * ⚠️ **Aucune notification n'est envoyée aujourd'hui** : les alertes sont hors
 * périmètre V1 et rien dans l'app ni sur le serveur ne les produit. L'écran ne
 * demande donc **pas** la permission système et ne promet rien — il retient un
 * choix, et le dit (§2.5). Promettre « soyez alerté dès qu'un vote commence »
 * comme le faisait la maquette serait une promesse qu'on ne tient pas.
 */

interface Props {
  preferences: Preferences;
  onToggleAlertes: () => void;
}

export function OnboardingAlertes({ preferences, onToggleAlertes }: Props) {
  const { themes, departement, alertes } = preferences;

  return (
    <ScrollView
      contentContainerStyle={styles.contenu}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.icone}>
        <IconLigne name="cloche" color={colors.brand} size={30} strokeWidth={1.6} />
      </View>

      <Text style={styles.titre}>Être prévenu, plus tard</Text>
      <Text style={styles.chapeau}>
        Les alertes n’existent pas encore dans Décrypté. On retient votre choix dès
        maintenant : le jour où elles arriveront, elles suivront vos thèmes.
      </Text>

      <Interrupteur
        actif={alertes}
        onToggle={onToggleAlertes}
        titre={alertes ? 'Alertes souhaitées' : 'Alertes non souhaitées'}
        detail={
          alertes
            ? 'Ce choix est enregistré — rien ne vous sera envoyé d’ici là'
            : 'Modifiable à tout moment depuis votre profil'
        }
      />

      <View style={styles.recap}>
        <Text style={styles.recapTitre}>Ce que vous suivrez</Text>

        {themes.length > 0 ? (
          <View style={styles.pastilles}>
            {themes.map((t) => (
              <View key={t} style={styles.pastille}>
                <Text style={styles.pastilleEmoji} importantForAccessibility="no">
                  {themeEmoji[t] ?? themeEmoji.Autre}
                </Text>
                <Text style={styles.pastilleTexte}>{t}</Text>
              </View>
            ))}
          </View>
        ) : (
          <Text style={styles.recapVide}>
            Aucun thème choisi — l’accueil gardera l’ordre par défaut.
          </Text>
        )}

        {/* Ligne masquée si le département n'a pas été renseigné (§2.5). */}
        {departement ? (
          <View style={styles.ligneDep}>
            <IconLigne name="epingle" color={colors.textTertiary} size={15} strokeWidth={1.7} />
            <Text style={styles.depTexte}>{departement}</Text>
          </View>
        ) : null}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  contenu: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.xl,
    gap: spacing.lg,
  },
  icone: {
    width: 64,
    height: 64,
    borderRadius: radius.xl,
    backgroundColor: colors.brandSoft,
    borderWidth: 1,
    borderColor: 'rgba(139,156,244,0.22)',
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'center',
  },
  titre: {
    fontFamily: serifDisplay,
    fontSize: 28,
    lineHeight: 34,
    letterSpacing: -0.5,
    color: colors.textPrimary,
    textAlign: 'center',
  },
  chapeau: {
    ...typography.bodySecondary,
    textAlign: 'center',
    marginTop: -spacing.sm,
    marginBottom: spacing.xs,
  },
  recap: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.md,
  },
  recapTitre: {
    fontFamily: mono,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
    color: colors.miniLabel,
  },
  pastilles: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  pastille: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: colors.brandSoft,
    borderRadius: radius.pill,
    paddingVertical: 5,
    paddingHorizontal: spacing.md,
  },
  pastilleEmoji: { fontSize: 13 },
  pastilleTexte: { ...typography.label, fontSize: 12.5, color: colors.brand },
  recapVide: { ...typography.bodySecondary, color: colors.textTertiary },
  ligneDep: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  depTexte: { ...typography.bodySecondary, color: colors.textSecondary },
});
