import Constants from 'expo-constants';
import { Platform } from 'react-native';

/**
 * URL de base de l'API Décrypté.
 *
 * En dev, l'app tourne sur simulateur ou appareil physique : « localhost » n'y
 * pointe pas vers la machine qui héberge le backend. On dérive donc l'IP de la
 * machine de dev depuis la config Expo (hostUri = l'hôte du bundler Metro), ce
 * qui marche à la fois sur simulateur iOS, émulateur Android et téléphone réel.
 *
 * Surchargeable via la variable d'env `EXPO_PUBLIC_API_URL`.
 */
const DEV_API_PORT = 8000;

function resolveBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  if (fromEnv) return fromEnv.replace(/\/+$/, '');

  const hostUri: string =
    Constants.expoConfig?.hostUri ??
    Constants.expoGoConfig?.debuggerHost ??
    '';
  const host = hostUri.split(':')[0];
  if (host) return `http://${host}:${DEV_API_PORT}`;

  // Derniers recours.
  if (Platform.OS === 'android') return `http://10.0.2.2:${DEV_API_PORT}`;
  return `http://localhost:${DEV_API_PORT}`;
}

export const API_BASE_URL = resolveBaseUrl();

/** Délai au-delà duquel une requête est abandonnée (ms). */
export const API_TIMEOUT_MS = 10_000;
