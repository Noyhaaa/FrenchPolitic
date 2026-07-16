import AsyncStorage from '@react-native-async-storage/async-storage';
import { Accueil, Dossier, RecapMensuel, Scrutin } from '@/types';

/**
 * Cache local pour l'usage hors-ligne (§8 : l'app reste utilisable sur les
 * contenus déjà consultés). On stocke le dernier fil et chaque fiche ouverte.
 * Best-effort : toute erreur de stockage est ignorée silencieusement.
 */
const KEY_ACCUEIL = 'cache:accueil';
const KEY_RECAP = 'cache:recap';
const keyDetail = (id: string) => `cache:dossier:${id}`;
const keyScrutin = (id: string) => `cache:scrutin:${id}`;

async function readJson<T>(key: string): Promise<T | null> {
  try {
    const raw = await AsyncStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

async function writeJson(key: string, value: unknown): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
  } catch {
    // stockage plein ou indisponible → on ignore, le cache est optionnel
  }
}

export const cache = {
  getAccueil: () => readJson<Accueil>(KEY_ACCUEIL),
  setAccueil: (a: Accueil) => writeJson(KEY_ACCUEIL, a),
  getDetail: (id: string) => readJson<Dossier>(keyDetail(id)),
  setDetail: (d: Dossier) => writeJson(keyDetail(d.id), d),
  getScrutin: (id: string) => readJson<Scrutin>(keyScrutin(id)),
  setScrutin: (s: Scrutin) => writeJson(keyScrutin(s.id), s),
  getRecap: () => readJson<RecapMensuel>(KEY_RECAP),
  setRecap: (r: RecapMensuel) => writeJson(KEY_RECAP, r),
};
