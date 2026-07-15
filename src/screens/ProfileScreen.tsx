import { PlaceholderScreen } from './PlaceholderScreen';

/**
 * Profil — aucune donnée personnelle nécessaire en V1 (pas de compte, §8 RGPD).
 * Cet écran hébergera à terme les préférences, mentions légales et licence.
 */
export function ProfileScreen() {
  return (
    <PlaceholderScreen
      emoji="👤"
      title="Profil"
      description="Aucun compte n'est requis pour utiliser Décrypté. On retrouvera ici les mentions légales, la licence des données et les réglages."
      jalon="Sans compte en V1"
    />
  );
}
