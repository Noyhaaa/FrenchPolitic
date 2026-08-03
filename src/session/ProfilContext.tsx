import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { ApiError, connecter, envoyerPreferences, fetchCompte, inscrire } from '@/api';
import { PREFERENCES_VIDES, stockage } from '@/storage/preferences';
import { Compte, Preferences } from '@/types';

/**
 * Session et préférences — le seul état applicatif partagé de l'app.
 *
 * Règle centrale : **les préférences vivent en local**. Le compte n'est qu'un
 * moyen de les retrouver ailleurs ; quand il y en a un, chaque changement est
 * en plus poussé vers l'API en best-effort. Un échec réseau ne bloque donc
 * jamais le parcours d'inscription ni la modification d'un thème — c'est la
 * même doctrine que le cache hors-ligne (§8).
 *
 * À la connexion, les préférences du serveur **remplacent** les locales : on
 * vient précisément de demander à retrouver son compte.
 */

interface ValeurProfil {
  /** Faux tant que le stockage n'a pas été relu : rien ne doit s'afficher avant. */
  pret: boolean;
  /** Le parcours d'accueil a déjà été vu (ou passé). */
  onboardingVu: boolean;
  preferences: Preferences;
  /** Le compte ouvert, ou `null` — l'app fonctionne dans les deux cas. */
  compte: Compte | null;
  enregistrerPreferences: (p: Preferences) => Promise<void>;
  terminerOnboarding: () => Promise<void>;
  revoirOnboarding: () => Promise<void>;
  sInscrire: (
    identite: { prenom: string; nom: string; email: string; motDePasse: string },
    preferences: Preferences,
  ) => Promise<void>;
  seConnecter: (email: string, motDePasse: string) => Promise<void>;
  seDeconnecter: () => Promise<void>;
}

const ProfilContext = createContext<ValeurProfil | null>(null);

export function ProfilProvider({ children }: { children: ReactNode }) {
  const [pret, setPret] = useState(false);
  const [onboardingVu, setOnboardingVu] = useState(false);
  const [preferences, setPreferences] = useState<Preferences>(PREFERENCES_VIDES);
  const [compte, setCompte] = useState<Compte | null>(null);
  const [jeton, setJeton] = useState<string | null>(null);

  // Relecture du stockage au lancement. Le jeton est vérifié auprès de l'API :
  // s'il a expiré, on le jette silencieusement et l'app repart sans compte —
  // les préférences locales, elles, restent (§2.5 : on ne perd pas un choix
  // déjà exprimé parce qu'une session a vieilli).
  useEffect(() => {
    let annule = false;
    (async () => {
      const [vu, prefsLocales, jetonStocke] = await Promise.all([
        stockage.getOnboardingVu(),
        stockage.getPreferences(),
        stockage.getJeton(),
      ]);
      if (annule) return;
      setOnboardingVu(vu);
      setPreferences(prefsLocales);

      if (jetonStocke) {
        try {
          const distant = await fetchCompte(jetonStocke);
          if (annule) return;
          setJeton(jetonStocke);
          setCompte(distant);
          setPreferences(distant.preferences);
          void stockage.setPreferences(distant.preferences);
        } catch (err) {
          // 401 → session périmée, on oublie le jeton. Réseau (status 0) → on
          // le garde : le compte est simplement hors d'atteinte pour l'instant.
          if (err instanceof ApiError && !err.isNetwork) {
            void stockage.oublierJeton();
          } else if (!annule) {
            setJeton(jetonStocke);
          }
        }
      }
      if (!annule) setPret(true);
    })();
    return () => {
      annule = true;
    };
  }, []);

  const enregistrerPreferences = useCallback(
    async (p: Preferences) => {
      setPreferences(p);
      await stockage.setPreferences(p);
      if (!jeton) return;
      try {
        const aJour = await envoyerPreferences(jeton, p);
        setCompte(aJour);
      } catch {
        // Best-effort : le choix est déjà enregistré sur l'appareil, il
        // repartira vers le serveur au prochain changement.
      }
    },
    [jeton],
  );

  const terminerOnboarding = useCallback(async () => {
    setOnboardingVu(true);
    await stockage.setOnboardingVu(true);
  }, []);

  const revoirOnboarding = useCallback(async () => {
    setOnboardingVu(false);
    await stockage.setOnboardingVu(false);
  }, []);

  const ouvrirSession = useCallback(
    async (session: { jeton: string; compte: Compte }) => {
      setJeton(session.jeton);
      setCompte(session.compte);
      setPreferences(session.compte.preferences);
      await Promise.all([
        stockage.setJeton(session.jeton),
        stockage.setPreferences(session.compte.preferences),
      ]);
    },
    [],
  );

  const sInscrire = useCallback<ValeurProfil['sInscrire']>(
    async (identite, prefs) => {
      const session = await inscrire({ ...identite, preferences: prefs });
      await ouvrirSession(session);
    },
    [ouvrirSession],
  );

  const seConnecter = useCallback<ValeurProfil['seConnecter']>(
    async (email, motDePasse) => {
      const session = await connecter(email, motDePasse);
      await ouvrirSession(session);
    },
    [ouvrirSession],
  );

  const seDeconnecter = useCallback(async () => {
    setJeton(null);
    setCompte(null);
    await stockage.oublierJeton();
    // Les préférences restent : elles décrivent ce que ce lecteur suit sur cet
    // appareil, pas la session. Se déconnecter ne doit pas vider son fil.
  }, []);

  const valeur = useMemo<ValeurProfil>(
    () => ({
      pret,
      onboardingVu,
      preferences,
      compte,
      enregistrerPreferences,
      terminerOnboarding,
      revoirOnboarding,
      sInscrire,
      seConnecter,
      seDeconnecter,
    }),
    [
      pret,
      onboardingVu,
      preferences,
      compte,
      enregistrerPreferences,
      terminerOnboarding,
      revoirOnboarding,
      sInscrire,
      seConnecter,
      seDeconnecter,
    ],
  );

  return <ProfilContext.Provider value={valeur}>{children}</ProfilContext.Provider>;
}

export function useProfil(): ValeurProfil {
  const valeur = useContext(ProfilContext);
  if (!valeur) {
    throw new Error('useProfil doit être utilisé dans un <ProfilProvider>.');
  }
  return valeur;
}
