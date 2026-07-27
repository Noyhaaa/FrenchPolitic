import {
  Accueil,
  Dossier,
  DossierListItem,
  RecapMensuel,
  Scrutin,
  ThemeListItem,
} from '@/types';
import { apiGet } from './client';

/**
 * Écran d'accueil complet en UNE réponse (§3.1) : à la une, aujourd'hui,
 * hier, rangées par thème — l'affichage est atomique, pas de remplissage
 * progressif. (Le fil paginé `/dossiers` reste exposé par l'API.)
 */
export function fetchAccueil(signal?: AbortSignal): Promise<Accueil> {
  return apiGet<Accueil>('/accueil', undefined, signal);
}

/** Fiche détaillée d'un dossier (§3.2). */
export function fetchDossier(id: string, signal?: AbortSignal): Promise<Dossier> {
  return apiGet<Dossier>(`/dossiers/${encodeURIComponent(id)}`, undefined, signal);
}

/** Détail d'un vote : groupes + nominatif si disponible (§3.2, §5.2). */
export function fetchScrutin(id: string, signal?: AbortSignal): Promise<Scrutin> {
  return apiGet<Scrutin>(`/scrutins/${encodeURIComponent(id)}`, undefined, signal);
}

/** Activité du dernier mois actif (carte récap de l'accueil, §7.8). */
export function fetchRecap(signal?: AbortSignal): Promise<RecapMensuel | null> {
  return apiGet<RecapMensuel | null>('/recap', undefined, signal);
}

/**
 * Recherche multi-termes classée par pertinence (§3.3).
 *
 * Tous les mots sont exigés, pas forcément côte à côte ni dans le titre :
 * l'index du backend couvre aussi les réponses « pourquoi » / « ce que ça
 * change » et les publics concernés. `theme` seul (requête vide) parcourt le
 * thème.
 */
export function searchDossiers(
  query: string,
  theme?: string,
  signal?: AbortSignal,
): Promise<DossierListItem[]> {
  return apiGet<DossierListItem[]>(
    '/recherche',
    { q: query, theme: theme ?? '' },
    signal,
  );
}

/** Thèmes proposés en filtre de recherche (uniquement ceux qui ont des dossiers). */
export function fetchThemes(signal?: AbortSignal): Promise<ThemeListItem[]> {
  return apiGet<ThemeListItem[]>('/themes', undefined, signal);
}
