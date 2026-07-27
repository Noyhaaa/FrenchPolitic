import { useEffect, useRef, useState } from 'react';
import { fetchDeputes, fetchThemes, searchDossiers } from '@/api';
import { DeputeListItem, DossierListItem, ThemeListItem } from '@/types';

/** Députés montrés en second rang : de quoi reconnaître, pas de quoi noyer. */
export const MAX_DEPUTES = 5;

interface State {
  dossiers: DossierListItem[];
  deputes: DeputeListItem[];
  loading: boolean;
  error: boolean;
}

const DEBOUNCE_MS = 300;

/**
 * Recherche unifiée textes + députés, avec debounce (§3.3).
 *
 * Les deux requêtes partent **en parallèle** et sont annulées ensemble à chaque
 * frappe : une réponse obsolète ne peut pas écraser la suivante. Un thème actif
 * ne s'applique qu'aux textes — il ne qualifie pas une personne —, la liste des
 * députés est donc vidée dans ce cas.
 */
export function useRecherche(query: string, theme?: string) {
  const [state, setState] = useState<State>({
    dossiers: [],
    deputes: [],
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
        const [dossiers, deputes] = await Promise.all([
          searchDossiers(query, theme, controller.signal),
          // Pas de recherche de personne sans terme, ni sous filtre de thème.
          query.trim() && !theme
            ? fetchDeputes({ q: query }, controller.signal)
            : Promise.resolve([] as DeputeListItem[]),
        ]);
        if (!controller.signal.aborted) {
          setState({
            dossiers,
            deputes: deputes.slice(0, MAX_DEPUTES),
            loading: false,
            error: false,
          });
        }
      } catch {
        if (!controller.signal.aborted) {
          setState({ dossiers: [], deputes: [], loading: false, error: true });
        }
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(handle);
  }, [query, theme]);

  return state;
}

/**
 * Thèmes proposés en filtre. Chargés une fois : ils ne dépendent ni de la
 * requête ni du filtre courant. Échec → liste vide, donc pas de chips (§2.5).
 */
export function useThemes(): ThemeListItem[] {
  const [themes, setThemes] = useState<ThemeListItem[]>([]);

  useEffect(() => {
    let vivant = true;
    (async () => {
      try {
        const resultat = await fetchThemes();
        if (vivant) setThemes(resultat);
      } catch {
        if (vivant) setThemes([]);
      }
    })();
    return () => {
      vivant = false;
    };
  }, []);

  return themes;
}
