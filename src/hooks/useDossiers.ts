import { useCallback, useEffect, useState } from 'react';
import { cache } from '@/api';
import { ApiError } from '@/api/client';
import { fetchDossiers, PAGE_SIZE } from '@/api/dossiers';
import { DossierListItem } from '@/types';

interface State {
  data: DossierListItem[] | null;
  loading: boolean;
  refreshing: boolean;
  /** true quand un chargement de page suivante est en cours. */
  loadingMore: boolean;
  /** true tant qu'il reste des dossiers plus anciens à charger. */
  hasMore: boolean;
  /** true quand les données affichées viennent du cache (backend injoignable). */
  offline: boolean;
  error: 'network' | 'server' | null;
}

const initial: State = {
  data: null,
  loading: true,
  refreshing: false,
  loadingMore: false,
  hasMore: true,
  offline: false,
  error: null,
};

/**
 * Charge le fil des dossiers depuis l'API, paginé (défilement infini), avec
 * repli sur le cache hors-ligne. `refresh` = pull-to-refresh, `loadMore` =
 * page suivante (§3.1).
 */
export function useDossiers() {
  const [state, setState] = useState<State>(initial);

  const load = useCallback(async (mode: 'initial' | 'refresh') => {
    setState((s) => ({
      ...s,
      loading: mode === 'initial',
      refreshing: mode === 'refresh',
    }));
    try {
      const items = await fetchDossiers({ offset: 0 });
      void cache.setFeed(items); // on ne met en cache que la 1re page
      setState({
        ...initial,
        data: items,
        loading: false,
        hasMore: items.length === PAGE_SIZE,
      });
    } catch (err) {
      const cached = await cache.getFeed();
      const isNetwork = err instanceof ApiError && err.isNetwork;
      setState({
        ...initial,
        data: cached ?? null,
        loading: false,
        hasMore: false,
        offline: cached != null,
        error: cached ? null : isNetwork ? 'network' : 'server',
      });
    }
  }, []);

  const loadMore = useCallback(() => {
    setState((s) => {
      if (s.loadingMore || !s.hasMore || !s.data || s.offline) return s;
      const offset = s.data.length;
      // Chargement asynchrone déclenché hors du setState.
      void (async () => {
        try {
          const page = await fetchDossiers({ offset });
          setState((cur) => ({
            ...cur,
            data: [...(cur.data ?? []), ...page],
            loadingMore: false,
            hasMore: page.length === PAGE_SIZE,
          }));
        } catch {
          // Échec silencieux : on garde ce qui est déjà chargé.
          setState((cur) => ({ ...cur, loadingMore: false }));
        }
      })();
      return { ...s, loadingMore: true };
    });
  }, []);

  useEffect(() => {
    load('initial');
  }, [load]);

  return {
    ...state,
    refresh: () => load('refresh'),
    retry: () => load('initial'),
    loadMore,
  };
}
