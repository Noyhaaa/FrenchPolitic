import { useCallback, useEffect, useState } from 'react';
import { cache, fetchAccueil } from '@/api';
import { ApiError } from '@/api/client';
import { Accueil } from '@/types';

interface State {
  data: Accueil | null;
  loading: boolean;
  refreshing: boolean;
  /** true quand les données affichées viennent du cache (backend injoignable). */
  offline: boolean;
  error: 'network' | 'server' | null;
}

const initial: State = {
  data: null,
  loading: true,
  refreshing: false,
  offline: false,
  error: null,
};

/**
 * Charge l'écran d'accueil complet en une réponse (§3.1), avec repli sur le
 * cache hors-ligne. L'affichage est atomique : toutes les rangées arrivent
 * ensemble (pas de remplissage progressif).
 */
export function useAccueil() {
  const [state, setState] = useState<State>(initial);

  const load = useCallback(async (mode: 'initial' | 'refresh') => {
    setState((s) => ({
      ...s,
      loading: mode === 'initial',
      refreshing: mode === 'refresh',
    }));
    try {
      const accueil = await fetchAccueil();
      void cache.setAccueil(accueil);
      setState({ ...initial, data: accueil, loading: false });
    } catch (err) {
      const cached = await cache.getAccueil();
      const isNetwork = err instanceof ApiError && err.isNetwork;
      setState({
        ...initial,
        data: cached ?? null,
        loading: false,
        offline: cached != null,
        error: cached ? null : isNetwork ? 'network' : 'server',
      });
    }
  }, []);

  useEffect(() => {
    load('initial');
  }, [load]);

  return {
    ...state,
    refresh: () => load('refresh'),
    retry: () => load('initial'),
  };
}
