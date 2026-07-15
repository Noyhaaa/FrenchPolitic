import { useCallback, useEffect, useState } from 'react';
import { cache, fetchScrutin } from '@/api';
import { ApiError } from '@/api/client';
import { Scrutin } from '@/types';

interface State {
  data: Scrutin | null;
  loading: boolean;
  offline: boolean;
  error: 'network' | 'server' | 'notfound' | null;
}

/** Charge le détail d'un vote par id, avec repli cache hors-ligne (§3.2, §8). */
export function useScrutin(id: string) {
  const [state, setState] = useState<State>({
    data: null,
    loading: true,
    offline: false,
    error: null,
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const scrutin = await fetchScrutin(id);
      void cache.setScrutin(scrutin);
      setState({ data: scrutin, loading: false, offline: false, error: null });
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setState({ data: null, loading: false, offline: false, error: 'notfound' });
        return;
      }
      const cached = await cache.getScrutin(id);
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
