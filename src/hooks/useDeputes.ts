import { useEffect, useRef, useState } from 'react';
import { cache, fetchDeputes, fetchGroupes } from '@/api';
import { DeputeListItem, GroupeListItem } from '@/types';

interface State {
  deputes: DeputeListItem[];
  /** Groupes servant les chips de filtre (chargés une fois). */
  groupes: GroupeListItem[];
  loading: boolean;
  offline: boolean;
  error: boolean;
}

const DEBOUNCE_MS = 300;

/**
 * Annuaire des députés : recherche par nom (avec debounce) et filtre par
 * groupe, servis par l'API. Repli sur le cache hors-ligne pour la liste
 * complète (§8) — une recherche sans réseau n'invente rien, elle échoue.
 */
export function useDeputes(query: string, groupeId?: string) {
  const [state, setState] = useState<State>({
    deputes: [],
    groupes: [],
    loading: true,
    offline: false,
    error: false,
  });
  const controllerRef = useRef<AbortController | null>(null);

  // Les groupes ne dépendent ni de la recherche ni du filtre : un seul chargement.
  useEffect(() => {
    let vivant = true;
    (async () => {
      try {
        const groupes = await fetchGroupes();
        void cache.setGroupes(groupes);
        if (vivant) setState((s) => ({ ...s, groupes }));
      } catch {
        const cached = await cache.getGroupes();
        if (vivant && cached) setState((s) => ({ ...s, groupes: cached }));
      }
    })();
    return () => {
      vivant = false;
    };
  }, []);

  const filtre = query.trim();

  useEffect(() => {
    const handle = setTimeout(async () => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      setState((s) => ({ ...s, loading: true, error: false }));
      try {
        const deputes = await fetchDeputes(
          { q: filtre, groupeId },
          controller.signal,
        );
        // Seule la liste complète alimente le cache : c'est elle qui sert de
        // repli hors-ligne, pas un résultat de recherche partiel.
        if (!filtre && !groupeId) void cache.setDeputes(deputes);
        if (!controller.signal.aborted) {
          setState((s) => ({
            ...s,
            deputes,
            loading: false,
            offline: false,
            error: false,
          }));
        }
      } catch {
        if (controller.signal.aborted) return;
        const cached = !filtre && !groupeId ? await cache.getDeputes() : null;
        setState((s) => ({
          ...s,
          deputes: cached ?? [],
          loading: false,
          offline: cached != null,
          error: cached == null,
        }));
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(handle);
  }, [filtre, groupeId]);

  return state;
}
