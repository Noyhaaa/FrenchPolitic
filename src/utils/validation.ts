/**
 * Règles de saisie du compte — source unique pour l'écran qui les affiche et
 * pour l'écran hôte qui décide si l'on peut avancer.
 *
 * Elles doublent celles du backend (`app/schemas/utilisateur.py`), qui reste
 * l'autorité : ici on évite un aller-retour réseau pour dire à quelqu'un que
 * son adresse manque un « @ », rien de plus.
 */

/** Miroir de `MOT_DE_PASSE_MIN` côté backend. */
export const MOT_DE_PASSE_MIN = 8;

const RE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function emailValide(email: string): boolean {
  return RE_EMAIL.test(email.trim());
}

export function nomValide(valeur: string): boolean {
  return valeur.trim().length >= 2;
}

export function motDePasseValide(motDePasse: string): boolean {
  return motDePasse.length >= MOT_DE_PASSE_MIN;
}

/**
 * Force du mot de passe, de 1 à 4. Purement indicative : seul le minimum de
 * longueur conditionne l'inscription — on informe, on n'impose pas une
 * composition que l'API n'exige pas.
 */
export type ForceMotDePasse = 1 | 2 | 3 | 4;

export function forceMotDePasse(motDePasse: string): ForceMotDePasse {
  const majuscule = /[A-ZÀ-Þ]/.test(motDePasse);
  const chiffre = /[0-9]/.test(motDePasse);
  const symbole = /[^a-zA-ZÀ-ÿ0-9]/.test(motDePasse);
  if (motDePasse.length >= 12 && majuscule && chiffre && symbole) return 4;
  if (motDePasse.length >= 10 && majuscule && chiffre) return 3;
  if (motDePasseValide(motDePasse)) return 2;
  return 1;
}

export const LIBELLE_FORCE: Record<ForceMotDePasse, string> = {
  1: 'Trop court',
  2: 'Correct',
  3: 'Fort',
  4: 'Très fort',
};
