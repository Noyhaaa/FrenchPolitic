import 'react-native-gesture-handler';
import { useEffect, useRef, useState } from 'react';
import { Animated, Easing, StyleSheet } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import {
  useFonts,
  Newsreader_400Regular,
  Newsreader_500Medium_Italic,
  Newsreader_600SemiBold,
  Newsreader_700Bold,
} from '@expo-google-fonts/newsreader';

import { RootNavigator } from '@/navigation/RootNavigator';
import { DecrypteSplash } from '@/components';
import { amorcerAccueil } from '@/hooks';
import { cache, fetchAccueil } from '@/api';
import { ProfilProvider, useProfil } from '@/session/ProfilContext';

// Durée minimale d'affichage du splash de lancement (ms) : l'animation
// « chat-constellation » doit avoir le temps de s'allumer, même quand tout
// arrive vite. Le splash reste tant que fonts non prêtes, délai non écoulé
// OU accueil non chargé — au plus long des trois.
const SPLASH_MIN_MS = 2400;

// Durée du fondu de sortie du splash (ms) : transition douce splash → accueil.
const SPLASH_FADE_MS = 550;

export default function App() {
  return (
    <ProfilProvider>
      <Lancement />
    </ProfilProvider>
  );
}

/**
 * Écran de lancement : le splash reste tant que les polices, l'accueil, le
 * délai minimal ET le profil local (parcours déjà vu ? session valide ?) ne
 * sont pas prêts. Lire le profil ici plutôt que dans le navigateur évite tout
 * clignotement entre l'app et le parcours d'accueil.
 */
function Lancement() {
  const { pret: profilPret, onboardingVu } = useProfil();

  // Newsreader (antiqua de presse) : chaque graisse est une famille distincte
  // en RN, on charge les 4 utilisées par `typography.ts` avant de rendre la nav.
  const [fontsLoaded] = useFonts({
    Newsreader_400Regular,
    Newsreader_500Medium_Italic,
    Newsreader_600SemiBold,
    Newsreader_700Bold,
  });

  const [minElapsed, setMinElapsed] = useState(false);
  useEffect(() => {
    const id = setTimeout(() => setMinElapsed(true), SPLASH_MIN_MS);
    return () => clearTimeout(id);
  }, []);

  // Préchargement de l'accueil : on garde le splash tant que le chargement de
  // fond n'a pas abouti (succès, cache hors-ligne ou échec). L'accueil obtenu
  // est « amorcé » pour que HomeScreen s'affiche sans re-spinner.
  const [donneesPretes, setDonneesPretes] = useState(false);
  useEffect(() => {
    let annule = false;
    (async () => {
      try {
        const accueil = await fetchAccueil();
        void cache.setAccueil(accueil);
        if (!annule) amorcerAccueil(accueil);
      } catch {
        // Backend injoignable : on laisse HomeScreen gérer le cache / l'erreur.
        // Le splash ne doit pas rester bloqué → on débloque quand même.
      } finally {
        if (!annule) setDonneesPretes(true);
      }
    })();
    return () => {
      annule = true;
    };
  }, []);

  const ready = fontsLoaded && minElapsed && donneesPretes && profilPret;

  // Fondu enchaîné : quand tout est prêt, l'accueil est monté dessous et le
  // splash (en surimpression) s'estompe, puis on le démonte. Pas de coupure
  // sèche entre le splash et la homepage.
  const splashOpacity = useRef(new Animated.Value(1)).current;
  const [splashMonte, setSplashMonte] = useState(true);
  useEffect(() => {
    if (!ready) return;
    const anim = Animated.timing(splashOpacity, {
      toValue: 0,
      duration: SPLASH_FADE_MS,
      easing: Easing.out(Easing.ease),
      useNativeDriver: true,
    });
    anim.start(({ finished }) => {
      if (finished) setSplashMonte(false);
    });
    return () => anim.stop();
  }, [ready, splashOpacity]);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <StatusBar style="light" />
        {/* L'accueil est monté dès que tout est prêt, sous le splash qui s'efface. */}
        {ready ? <RootNavigator onboardingVu={onboardingVu} /> : null}
        {splashMonte ? (
          <Animated.View
            style={[StyleSheet.absoluteFill, { opacity: splashOpacity }]}
            pointerEvents={ready ? 'none' : 'auto'}
          >
            <DecrypteSplash />
          </Animated.View>
        ) : null}
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
