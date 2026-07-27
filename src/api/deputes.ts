import {
  Chambre,
  DeputeDetail,
  DeputeListItem,
  GroupeListItem,
  VoteDepute,
} from '@/types';
import { apiGet } from './client';

/** Taille d'une page d'historique de votes (« charger les plus anciens »). */
export const PAGE_VOTES = 30;

/**
 * Annuaire des parlementaires (§5.2) : recherche par nom, filtres par groupe
 * et par chambre. Sans `chambre`, l'API sert les deux assemblées.
 */
export function fetchDeputes(
  params: { q?: string; groupeId?: string; chambre?: Chambre } = {},
  signal?: AbortSignal,
): Promise<DeputeListItem[]> {
  return apiGet<DeputeListItem[]>(
    '/deputes',
    {
      q: params.q ?? '',
      groupe: params.groupeId ?? '',
      chambre: params.chambre ?? '',
    },
    signal,
  );
}

/** Fiche d'un député : profil, portrait de vote, première page d'historique. */
export function fetchDepute(
  id: string,
  signal?: AbortSignal,
): Promise<DeputeDetail> {
  return apiGet<DeputeDetail>(
    `/deputes/${encodeURIComponent(id)}`,
    { limit: PAGE_VOTES },
    signal,
  );
}

/** Page suivante de l'historique (votes plus anciens). */
export function fetchVotesDepute(
  id: string,
  offset: number,
  signal?: AbortSignal,
): Promise<VoteDepute[]> {
  return apiGet<VoteDepute[]>(
    `/deputes/${encodeURIComponent(id)}/votes`,
    { offset, limit: PAGE_VOTES },
    signal,
  );
}

/** Groupes politiques (chips de filtre de l'annuaire). */
export function fetchGroupes(signal?: AbortSignal): Promise<GroupeListItem[]> {
  return apiGet<GroupeListItem[]>('/groupes', undefined, signal);
}
