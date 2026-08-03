import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Animated,
  Easing,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ApiError } from '@/api';
import {
  BoutonPrincipal,
  OnboardingAlertes,
  OnboardingBienvenue,
  OnboardingCompte,
  OnboardingDepartement,
  OnboardingThemes,
  ProgressionEtapes,
  SAISIE_COMPTE_VIDE,
  THEMES_MINIMUM,
  compteAmorce,
  compteComplet,
  type SaisieCompte,
} from '@/components';
import { useProfil } from '@/session/ProfilContext';
import { colors, spacing, typography } from '@/theme';
import type { Preferences, ThemeScrutin } from '@/types';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/**
 * Parcours d'accueil (maquette `onboarding-v3`), porté sur la charte Décrypté.
 *
 * Cinq étapes : présentation, compte, thèmes, département, alertes. Trois
 * principes s'y appliquent, tous hérités des règles produit :
 *
 *  - **Rien n'est obligatoire.** « Passer » est disponible à chaque étape et
 *    entre directement dans l'app. Le compte lui-même est facultatif : sans
 *    lui, les préférences restent sur l'appareil et tout fonctionne.
 *  - **Rien n'est promis.** Pas de « en direct », pas d'alerte annoncée
 *    (§2.5) — les libellés décrivent ce que l'app fait réellement.
 *  - **Aucune préférence ne filtre.** Les thèmes choisis remontent des rangées
 *    de l'accueil ; ils n'en cachent aucune.
 *
 * L'accent est la pervenche de la marque, jamais le rouge de la maquette :
 * `colors.rejete` (#FF3040) veut dire « rejeté » dans toute l'app.
 */

const ETAPES = 5;
const DUREE_TRANSITION = 190;

export function OnboardingScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const { preferences, compte, enregistrerPreferences, terminerOnboarding, sInscrire } =
    useProfil();

  const [etape, setEtape] = useState(0);
  const [brouillon, setBrouillon] = useState<Preferences>(preferences);
  const [saisie, setSaisie] = useState<SaisieCompte>(SAISIE_COMPTE_VIDE);
  const [erreurCompte, setErreurCompte] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  // Transition entre étapes : fondu + léger glissement, comme la maquette.
  const opacite = useRef(new Animated.Value(1)).current;
  const glissement = useRef(new Animated.Value(0)).current;

  const allerA = useCallback(
    (suivante: number, sens: 1 | -1) => {
      Animated.parallel([
        Animated.timing(opacite, {
          toValue: 0,
          duration: DUREE_TRANSITION,
          easing: Easing.out(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(glissement, {
          toValue: sens * -24,
          duration: DUREE_TRANSITION,
          easing: Easing.out(Easing.ease),
          useNativeDriver: true,
        }),
      ]).start(({ finished }) => {
        if (!finished) return;
        setEtape(suivante);
        glissement.setValue(sens * 24);
        Animated.parallel([
          Animated.timing(opacite, {
            toValue: 1,
            duration: DUREE_TRANSITION,
            easing: Easing.out(Easing.ease),
            useNativeDriver: true,
          }),
          Animated.timing(glissement, {
            toValue: 0,
            duration: DUREE_TRANSITION,
            easing: Easing.out(Easing.ease),
            useNativeDriver: true,
          }),
        ]).start();
      });
    },
    [glissement, opacite],
  );

  // Le compte a pu être ouvert depuis l'écran de connexion (« J'ai déjà un
  // compte ») : ses préférences arrivent alors du serveur, on reprend le
  // brouillon dessus plutôt que d'écraser ce qui vient d'être retrouvé.
  useEffect(() => {
    if (compte) setBrouillon(compte.preferences);
  }, [compte]);

  const majPreferences = useCallback((maj: Partial<Preferences>) => {
    setBrouillon((p) => ({ ...p, ...maj }));
  }, []);

  const basculerTheme = useCallback((theme: ThemeScrutin) => {
    setBrouillon((p) => ({
      ...p,
      themes: p.themes.includes(theme)
        ? p.themes.filter((t) => t !== theme)
        : [...p.themes, theme],
    }));
  }, []);

  /** Sortie du parcours : on enregistre ce qui a été choisi, puis on entre. */
  const entrerDansLApp = useCallback(async () => {
    await enregistrerPreferences(brouillon);
    await terminerOnboarding();
    navigation.reset({ index: 0, routes: [{ name: 'MainTabs' }] });
  }, [brouillon, enregistrerPreferences, navigation, terminerOnboarding]);

  /**
   * Étape « compte » : on ne tente une inscription que si le formulaire a été
   * commencé. Laissé vide, il se passe — c'est le sens de « facultatif ».
   */
  const validerCompte = useCallback(async () => {
    if (compte || !compteAmorce(saisie)) {
      allerA(2, 1);
      return;
    }
    setEnvoi(true);
    setErreurCompte(null);
    try {
      await sInscrire(saisie, brouillon);
      allerA(2, 1);
    } catch (err) {
      setErreurCompte(
        err instanceof ApiError
          ? err.isNetwork
            ? 'Serveur injoignable. Vous pouvez continuer sans compte et le créer plus tard.'
            : err.message
          : 'La création du compte a échoué.',
      );
    } finally {
      setEnvoi(false);
    }
  }, [allerA, brouillon, compte, saisie, sInscrire]);

  const avancer = useCallback(() => {
    if (etape === 1) {
      void validerCompte();
      return;
    }
    if (etape < ETAPES - 1) allerA(etape + 1, 1);
    else void entrerDansLApp();
  }, [allerA, entrerDansLApp, etape, validerCompte]);

  const reculer = useCallback(() => {
    if (etape > 0) allerA(etape - 1, -1);
  }, [allerA, etape]);

  const assezDeThemes = brouillon.themes.length >= THEMES_MINIMUM;
  const compteUtilisable = !compteAmorce(saisie) || compteComplet(saisie);
  const peutAvancer = etape === 1 ? compteUtilisable && !envoi : etape === 2 ? assezDeThemes : true;

  const libelleAction = (() => {
    switch (etape) {
      case 0:
        return 'Commencer';
      case 1:
        if (compte) return 'Continuer';
        if (!compteAmorce(saisie)) return 'Continuer sans compte';
        return compteComplet(saisie) ? 'Créer mon compte' : 'Complétez vos informations';
      case 2:
        return assezDeThemes
          ? 'Continuer'
          : `Choisir encore ${THEMES_MINIMUM - brouillon.themes.length}`;
      case 3:
        return brouillon.departement ? 'Continuer' : 'Passer cette étape';
      default:
        return 'Entrer dans Décrypté';
    }
  })();

  return (
    <View style={[styles.ecran, { paddingTop: insets.top }]}>
      <View style={styles.entete}>
        <ProgressionEtapes total={ETAPES} courante={etape} />
        <Pressable
          onPress={() => void entrerDansLApp()}
          hitSlop={10}
          accessibilityRole="button"
          accessibilityLabel="Passer la présentation et entrer dans l’application"
        >
          <Text style={styles.passer}>Passer</Text>
        </Pressable>
      </View>

      <KeyboardAvoidingView
        style={styles.corps}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={insets.top + 40}
      >
        <Animated.View
          style={[
            styles.scene,
            { opacity: opacite, transform: [{ translateX: glissement }] },
          ]}
        >
          {etape === 0 ? <OnboardingBienvenue /> : null}
          {etape === 1 ? (
            <OnboardingCompte
              saisie={saisie}
              onChange={(champ, valeur) =>
                setSaisie((s) => ({ ...s, [champ]: valeur }))
              }
              erreur={erreurCompte}
              onOuvrirConnexion={() => navigation.navigate('Connexion')}
            />
          ) : null}
          {etape === 2 ? (
            <OnboardingThemes selection={brouillon.themes} onToggle={basculerTheme} />
          ) : null}
          {etape === 3 ? (
            <OnboardingDepartement
              selection={brouillon.departement}
              onSelect={(departement) => majPreferences({ departement })}
            />
          ) : null}
          {etape === 4 ? (
            <OnboardingAlertes
              preferences={brouillon}
              onToggleAlertes={() => majPreferences({ alertes: !brouillon.alertes })}
            />
          ) : null}
        </Animated.View>

        <View style={[styles.actions, { paddingBottom: insets.bottom + spacing.xl }]}>
          <BoutonPrincipal
            label={libelleAction}
            onPress={avancer}
            desactive={!peutAvancer}
            enCours={envoi}
          />
          {etape > 0 ? (
            <Pressable
              onPress={reculer}
              accessibilityRole="button"
              accessibilityLabel="Revenir à l’étape précédente"
              style={styles.retour}
            >
              <Text style={styles.retourTexte}>Retour</Text>
            </Pressable>
          ) : (
            <View style={styles.retour} />
          )}
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  ecran: { flex: 1, backgroundColor: colors.background },
  entete: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  passer: { ...typography.label, color: colors.textTertiary },
  corps: { flex: 1 },
  scene: { flex: 1 },
  actions: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    gap: spacing.xs,
  },
  retour: { paddingVertical: spacing.md, alignItems: 'center' },
  retourTexte: { ...typography.label, color: colors.textTertiary },
});
