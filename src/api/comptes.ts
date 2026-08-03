import { Compte, Preferences, SessionOuverte } from '@/types';
import { apiGetAuth, apiPost, apiPut } from './client';

/**
 * Compte utilisateur — les seuls appels d'ÉCRITURE de l'app (§ backend
 * `app/api/routes/comptes.py`). Le compte est facultatif : aucune de ces
 * fonctions n'est nécessaire pour consulter dossiers, votes ou parlementaires.
 *
 * Les erreurs remontent en `ApiError` : `status` 409 (adresse déjà prise),
 * 401 (identifiants), 0 (réseau). Le `message` porte le texte renvoyé par
 * l'API, directement affichable.
 */

export interface DemandeInscription {
  prenom: string;
  nom: string;
  email: string;
  motDePasse: string;
  preferences: Preferences;
}

export function inscrire(demande: DemandeInscription): Promise<SessionOuverte> {
  return apiPost<SessionOuverte>('/inscription', demande);
}

export function connecter(email: string, motDePasse: string): Promise<SessionOuverte> {
  return apiPost<SessionOuverte>('/connexion', { email, motDePasse });
}

export function fetchCompte(jeton: string): Promise<Compte> {
  return apiGetAuth<Compte>('/moi', jeton);
}

export function envoyerPreferences(jeton: string, preferences: Preferences): Promise<Compte> {
  return apiPut<Compte>('/moi/preferences', preferences, jeton);
}
