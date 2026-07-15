import { useCallback, useEffect, useState } from 'react';
import { cache, fetchDossier } from '@/api';
import { ApiError } from '@/api/client';
import { Dossier } from '@/types';

interface State {
  data: Dossier | null;
  loading: boolean;
  offline: boolean;
  error: 'network' | 'server' | 'notfound' | null;
}

/** Charge une fiche dossier par id, avec repli cache hors-ligne (§3.2, §8). */
export function useDossier(id: string) {
  const [state, setState] = useState<State>({
    data: null,
    loading: true,
    offline: false,
    error: null,
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const dossier = await fetchDossier(id);
      void cache.setDetail(dossier);
      setState({ data: dossier, loading: false, offline: false, error: null });
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setState({ data: null, loading: false, offline: false, error: 'notfound' });
        return;
      }
      const cached = await cache.getDetail(id);
      const isNetwork = err instanceof ApiError && err.isNetwork;
      setState({
        data: cached ?? null,
        loading: false,
        offline: cached != null,
        error: cached ? null : isNetwork ? 'network' : 'server',
      });
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, retry: load };
}
