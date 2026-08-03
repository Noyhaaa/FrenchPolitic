import AsyncStorage from '@react-native-async-storage/async-storage';
import { Preferences } from '@/types';

/**
 * Ce que l'app retient de son lecteur, sur l'appareil.
 *
 * Distinct de `src/api/cache.ts`, qui garde des **données publiques** pour
 * l'usage hors-ligne : ici ce sont des **choix**. Même convention en revanche —
 * best-effort, toute erreur de stockage est ignorée silencieusement : un
 * stockage plein ne doit jamais empêcher de lire un vote.
 *
 * Les préférences vivent d'abord ici. Un compte n'est qu'un moyen de les
 * retrouver sur un autre appareil (§ `ProfilContext`).
 */
const KEY_ONBOARDING = 'pref:onboarding-vu';
const KEY_PREFERENCES = 'pref:preferences';
const KEY_JETON = 'auth:jeton';

/** Aucune préférence exprimée : l'accueil garde alors l'ordre de l'API. */
export const PREFERENCES_VIDES: Preferences = {
  themes: [],
  departement: null,
  alertes: false,
};

async function lireJson<T>(cle: string): Promise<T | null> {
  try {
    const brut = await AsyncStorage.getItem(cle);
    return brut ? (JSON.parse(brut) as T) : null;
  } catch {
    return null;
  }
}

async function ecrireJson(cle: string, valeur: unknown): Promise<void> {
  try {
    await AsyncStorage.setItem(cle, JSON.stringify(valeur));
  } catch {
    // stockage plein ou indisponible → on ignore
  }
}

async function effacer(cle: string): Promise<void> {
  try {
    await AsyncStorage.removeItem(cle);
  } catch {
    // idem
  }
}

export const stockage = {
  /**
   * Le parcours d'accueil a-t-il déjà été vu ? Posé aussi bien à la fin du
   * parcours qu'au « Passer » : dans les deux cas, l'utilisateur a répondu.
   */
  getOnboardingVu: async (): Promise<boolean> =>
    (await lireJson<boolean>(KEY_ONBOARDING)) === true,
  setOnboardingVu: (vu: boolean) => ecrireJson(KEY_ONBOARDING, vu),

  getPreferences: async (): Promise<Preferences> =>
    (await lireJson<Preferences>(KEY_PREFERENCES)) ?? PREFERENCES_VIDES,
  setPreferences: (p: Preferences) => ecrireJson(KEY_PREFERENCES, p),

  getJeton: () => lireJson<string>(KEY_JETON),
  setJeton: (jeton: string) => ecrireJson(KEY_JETON, jeton),
  oublierJeton: () => effacer(KEY_JETON),
};
