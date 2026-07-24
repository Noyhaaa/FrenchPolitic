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
 * Accueil préchargé au lancement (App.tsx maintient le splash tant que ce
 * fetch n'est pas résolu). Le premier `useAccueil` le consomme pour s'afficher
 * immédiatement, sans re-déclencher un chargement ni faire clignoter un
 * spinner. À usage unique : une fois lu, on le vide.
 */
let accueilPrecharge: Accueil | null = null;

export function amorcerAccueil(data: Accueil) {
  accueilPrecharge = data;
}

function consommerAccueilPrecharge(): Accueil | null {
  const data = accueilPrecharge;
  accueilPrecharge = null;
  return data;
}

/**
 * Charge l'écran d'accueil complet en une réponse (§3.1), avec repli sur le
 * cache hors-ligne. L'affichage est atomique : toutes les rangées arrivent
 * ensemble (pas de remplissage progressif).
 */
export function useAccueil() {
  // Si le lancement a déjà chargé l'accueil, on part directement des données
  // (pas de spinner) ; sinon état initial « loading ».
  const [state, setState] = useState<State>(() => {
    const precharge = consommerAccueilPrecharge();
    return precharge ? { ...initial, data: precharge, loading: false } : initial;
  });

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
    // Déjà servi par le préchargement du lancement → pas de re-fetch.
    if (state.data) return;
    load('initial');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  return {
    ...state,
    refresh: () => load('refresh'),
    retry: () => load('initial'),
  };
}
