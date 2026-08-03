import { API_BASE_URL, API_TIMEOUT_MS } from './config';

/** Erreur normalisée : `status` à 0 = problème réseau/hors-ligne. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }

  get isNetwork(): boolean {
    return this.status === 0;
  }
}

function buildUrl(path: string, params?: Record<string, string | number>): string {
  let url = `${API_BASE_URL}${path}`;
  if (params) {
    const qs = Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== '')
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
      .join('&');
    if (qs) url += `?${qs}`;
  }
  return url;
}

/**
 * Requête typée avec timeout, annulation et erreurs normalisées.
 *
 * Toutes les méthodes passent par ici : une seule gestion du timeout, une seule
 * normalisation d'erreur. Le `message` porte le **détail renvoyé par l'API**
 * quand il y en a un (« Un compte existe déjà avec cette adresse e-mail. ») —
 * c'est ce que les écrans de compte affichent, plutôt qu'un code HTTP.
 */
async function requete<T>(
  methode: 'GET' | 'POST' | 'PUT',
  path: string,
  options: {
    params?: Record<string, string | number>;
    corps?: unknown;
    jeton?: string | null;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  const { params, corps, jeton, signal } = options;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  // Relie une éventuelle annulation externe (ex. debounce) à ce contrôleur.
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener('abort', () => controller.abort());
  }

  const headers: Record<string, string> = { Accept: 'application/json' };
  if (corps !== undefined) headers['Content-Type'] = 'application/json';
  if (jeton) headers.Authorization = `Bearer ${jeton}`;

  try {
    const res = await fetch(buildUrl(path, params), {
      method: methode,
      headers,
      body: corps === undefined ? undefined : JSON.stringify(corps),
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new ApiError(res.status, await messageErreur(res, path));
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    // AbortError ou échec réseau → status 0.
    const message =
      (err as Error)?.name === 'AbortError'
        ? 'Requête annulée ou expirée'
        : 'Réseau indisponible';
    throw new ApiError(0, message);
  } finally {
    clearTimeout(timeout);
  }
}

/** Détail lisible renvoyé par l'API, sinon le code HTTP. */
async function messageErreur(res: Response, path: string): Promise<string> {
  try {
    const corps = (await res.json()) as { detail?: unknown };
    if (typeof corps?.detail === 'string' && corps.detail) return corps.detail;
  } catch {
    // Corps absent ou non-JSON : on retombe sur le message générique.
  }
  return `Erreur ${res.status} sur ${path}`;
}

/** GET typé avec timeout, annulation et erreurs normalisées. */
export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number>,
  signal?: AbortSignal,
): Promise<T> {
  return requete<T>('GET', path, { params, signal });
}

/** GET typé porteur d'un jeton de session (routes `/moi`). */
export async function apiGetAuth<T>(path: string, jeton: string): Promise<T> {
  return requete<T>('GET', path, { jeton });
}

/** POST typé (inscription, connexion). */
export async function apiPost<T>(
  path: string,
  corps: unknown,
  jeton?: string | null,
): Promise<T> {
  return requete<T>('POST', path, { corps, jeton });
}

/** PUT typé (préférences du compte). */
export async function apiPut<T>(
  path: string,
  corps: unknown,
  jeton?: string | null,
): Promise<T> {
  return requete<T>('PUT', path, { corps, jeton });
}
