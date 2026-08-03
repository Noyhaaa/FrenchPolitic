import {
  DarkTheme,
  NavigationContainer,
  type Theme,
} from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { colors } from '@/theme';
import {
  ConnexionScreen,
  DeputeDetailScreen,
  DossierDetailScreen,
  DossiersScreen,
  GlossaireScreen,
  GlossaireTermeScreen,
  OnboardingScreen,
  ScrutinDetailScreen,
} from '@/screens';
import { MainTabs } from './MainTabs';
import type { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();

const navTheme: Theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.surface,
    text: colors.textPrimary,
    border: colors.border,
    primary: colors.brand,
  },
};

/**
 * @param onboardingVu Le parcours d'accueil a déjà été vu (ou passé) : on entre
 *   alors directement dans l'app. Lu du stockage avant le montage (cf. App.tsx),
 *   de sorte que rien ne clignote — le splash couvre l'attente.
 */
export function RootNavigator({ onboardingVu }: { onboardingVu: boolean }) {
  return (
    <NavigationContainer theme={navTheme}>
      <Stack.Navigator
        screenOptions={{ headerShown: false }}
        initialRouteName={onboardingVu ? 'MainTabs' : 'Onboarding'}
      >
        <Stack.Screen name="MainTabs" component={MainTabs} />
        <Stack.Screen
          name="Onboarding"
          component={OnboardingScreen}
          // Pas d'animation d'entrée : c'est le premier écran de l'app, il
          // prend la suite du splash qui s'efface.
          options={{ animation: 'none' }}
        />
        <Stack.Screen
          name="Connexion"
          component={ConnexionScreen}
          options={{ presentation: 'card', animation: 'slide_from_bottom' }}
        />
        <Stack.Screen
          name="DossierDetail"
          component={DossierDetailScreen}
          options={{ presentation: 'card', animation: 'slide_from_right' }}
        />
        <Stack.Screen
          name="ScrutinDetail"
          component={ScrutinDetailScreen}
          options={{ presentation: 'card', animation: 'slide_from_right' }}
        />
        <Stack.Screen
          name="DeputeDetail"
          component={DeputeDetailScreen}
          options={{ presentation: 'card', animation: 'slide_from_right' }}
        />
        <Stack.Screen
          name="Dossiers"
          component={DossiersScreen}
          options={{ presentation: 'card', animation: 'slide_from_right' }}
        />
        <Stack.Screen
          name="Glossaire"
          component={GlossaireScreen}
          options={{ presentation: 'card', animation: 'slide_from_right' }}
        />
        <Stack.Screen
          name="GlossaireTerme"
          component={GlossaireTermeScreen}
          options={{ presentation: 'card', animation: 'slide_from_right' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
