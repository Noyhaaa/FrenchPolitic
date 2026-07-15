import { useEffect, useRef, useState } from 'react';
import { searchDossiers } from '@/api';
import { DossierListItem } from '@/types';

interface State {
  results: DossierListItem[];
  loading: boolean;
  error: boolean;
}

const DEBOUNCE_MS = 300;

/**
 * Recherche avec debounce (§3.3). Annule la requête précédente à chaque frappe
 * pour éviter les résultats obsolètes.
 */
export function useDossierSearch(query: string) {
  const [state, setState] = useState<State>({
    results: [],
    loading: false,
    error: false,
  });
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const handle = setTimeout(async () => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      setState((s) => ({ ...s, loading: true, error: false }));
      try {
        const results = await searchDossiers(query, controller.signal);
        if (!controller.signal.aborted) {
          setState({ results, loading: false, error: false });
        }
      } catch {
        if (!controller.signal.aborted) {
          setState({ results: [], loading: false, error: true });
        }
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(handle);
  }, [query]);

  return state;
}
