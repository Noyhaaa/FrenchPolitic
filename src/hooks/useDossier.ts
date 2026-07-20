import { useCallback, useEffect, useState } from 'react';
import { cache, fetchDossier } from '@/api';
import { ApiError } from '@/api/client';
import { Dossier } from '@/types';

interface State {
  data: Dossier | null;
  loading: boolean;
  /** Rafraîchissement (pull-to-refresh) : les données restent affichées. */
  refreshing: boolean;
  offline: boolean;
  error: 'network' | 'server' | 'notfound' | null;
}

/** Charge une fiche dossier par id, avec repli cache hors-ligne (§3.2, §8). */
export function useDossier(id: string) {
  const [state, setState] = useState<State>({
    data: null,
    loading: true,
    refreshing: false,
    offline: false,
    error: null,
  });

  const load = useCallback(
    async (mode: 'initial' | 'refresh' = 'initial') => {
      setState((s) => ({
        ...s,
        loading: mode === 'initial',
        refreshing: mode === 'refresh',
        error: null,
      }));
      try {
        const dossier = await fetchDossier(id);
        void cache.setDetail(dossier);
        setState({
          data: dossier,
          loading: false,
          refreshing: false,
          offline: false,
          error: null,
        });
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setState({
            data: null,
            loading: false,
            refreshing: false,
            offline: false,
            error: 'notfound',
          });
          return;
        }
        const cached = await cache.getDetail(id);
        const isNetwork = err instanceof ApiError && err.isNetwork;
        setState({
          data: cached ?? null,
          loading: false,
          refreshing: false,
          offline: cached != null,
          error: cached ? null : isNetwork ? 'network' : 'server',
        });
      }
    },
    [id],
  );

  useEffect(() => {
    load('initial');
  }, [load]);

  return { ...state, retry: () => load('initial'), refresh: () => load('refresh') };
}
