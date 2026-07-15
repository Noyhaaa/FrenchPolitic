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

/** GET typé avec timeout, annulation et erreurs normalisées. */
export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number>,
  signal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  // Relie une éventuelle annulation externe (ex. debounce) à ce contrôleur.
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener('abort', () => controller.abort());
  }

  try {
    const res = await fetch(buildUrl(path, params), {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new ApiError(res.status, `Erreur ${res.status} sur ${path}`);
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
