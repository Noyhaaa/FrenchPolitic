import { useCallback, useEffect, useState } from 'react';
import { cache, fetchRecap } from '@/api';
import { RecapMensuel } from '@/types';

interface State {
  data: RecapMensuel | null;
  loading: boolean;
}

/**
 * Charge la carte récap du dernier mois actif (§7.8), avec repli cache
 * hors-ligne. Contenu d'appoint : en cas d'échec sans cache, la carte est
 * simplement masquée (pas d'état d'erreur dédié).
 */
export function useRecap() {
  const [state, setState] = useState<State>({ data: null, loading: true });

  const load = useCallback(async () => {
    try {
      const recap = await fetchRecap();
      if (recap) void cache.setRecap(recap);
      setState({ data: recap, loading: false });
    } catch {
      const cached = await cache.getRecap();
      setState({ data: cached ?? null, loading: false });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, refresh: load };
}
