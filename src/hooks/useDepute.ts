import { useCallback, useEffect, useState } from 'react';
import { PAGE_VOTES, cache, fetchDepute, fetchVotesDepute } from '@/api';
import { ApiError } from '@/api/client';
import { DeputeDetail } from '@/types';

interface State {
  data: DeputeDetail | null;
  loading: boolean;
  /** Rafraîchissement (pull-to-refresh) : les données restent affichées. */
  refreshing: boolean;
  offline: boolean;
  error: 'network' | 'server' | 'notfound' | null;
  /** Chargement d'une page de votes plus anciens. */
  chargeantPlus: boolean;
  /** Faux tant que l'API peut encore renvoyer des votes plus anciens. */
  finHistorique: boolean;
}

/**
 * Fiche d'un député : profil, portrait de vote et historique paginé, avec
 * repli cache hors-ligne (§8). Une page plus courte que `PAGE_VOTES` signale
 * la fin de l'historique — on ne demande alors plus rien.
 */
export function useDepute(id: string) {
  const [state, setState] = useState<State>({
    data: null,
    loading: true,
    refreshing: false,
    offline: false,
    error: null,
    chargeantPlus: false,
    finHistorique: false,
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
        const depute = await fetchDepute(id);
        void cache.setDepute(depute);
        setState({
          data: depute,
          loading: false,
          refreshing: false,
          offline: false,
          error: null,
          chargeantPlus: false,
          finHistorique: depute.historique.length < PAGE_VOTES,
        });
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setState((s) => ({
            ...s,
            data: null,
            loading: false,
            refreshing: false,
            offline: false,
            error: 'notfound',
          }));
          return;
        }
        const cached = await cache.getDepute(id);
        const isNetwork = err instanceof ApiError && err.isNetwork;
        setState({
          data: cached ?? null,
          loading: false,
          refreshing: false,
          offline: cached != null,
          error: cached ? null : isNetwork ? 'network' : 'server',
          chargeantPlus: false,
          // Hors-ligne, on s'en tient à ce qui est en cache.
          finHistorique: true,
        });
      }
    },
    [id],
  );

  useEffect(() => {
    load('initial');
  }, [load]);

  /** Ajoute la page de votes suivante à l'historique déjà affiché. */
  const chargerPlus = useCallback(async () => {
    if (!state.data || state.chargeantPlus || state.finHistorique) return;
    const offset = state.data.historique.length;
    setState((s) => ({ ...s, chargeantPlus: true }));
    try {
      const page = await fetchVotesDepute(id, offset);
      setState((s) =>
        s.data
          ? {
              ...s,
              data: { ...s.data, historique: [...s.data.historique, ...page] },
              chargeantPlus: false,
              finHistorique: page.length < PAGE_VOTES,
            }
          : { ...s, chargeantPlus: false },
      );
    } catch {
      // Échec réseau : on garde l'historique déjà affiché et on laisse
      // l'utilisateur réessayer (§2.5 — rien n'est inventé ni masqué).
      setState((s) => ({ ...s, chargeantPlus: false }));
    }
  }, [id, state.data, state.chargeantPlus, state.finHistorique]);

  return {
    ...state,
    retry: () => load('initial'),
    refresh: () => load('refresh'),
    chargerPlus,
  };
}
