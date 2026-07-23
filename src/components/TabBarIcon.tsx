import { Circle, Path, Svg } from 'react-native-svg';

import type { MainTabsParamList } from '@/navigation/types';

/**
 * Icônes de la barre d'onglets — dessinées pour « Décrypté ».
 * Trait fin arrondi, monochrome : la couleur vient de `color`, donc l'état
 * actif/inactif se pilote comme avant (`tabBarActiveTintColor`).
 *
 * Accueil  = hémicycle (l'Assemblée)   Recherche = loupe
 * Députés  = deux silhouettes (groupe) Assistant = bulle + étoile ✦ (IA)
 * Profil   = une silhouette
 */
type Nom = keyof MainTabsParamList;

const COMMUN = {
  fill: 'none' as const,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

interface Props {
  name: Nom;
  color: string;
  size?: number;
  /** ~2 pour un trait plus présent, ~1.6 pour plus fin. */
  strokeWidth?: number;
}

export function TabBarIcon({ name, color, size = 24, strokeWidth = 1.85 }: Props) {
  const p = { stroke: color, strokeWidth, ...COMMUN };

  switch (name) {
    case 'Accueil':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path {...p} d="M4 18 A8 8 0 0 1 20 18" />
          <Path {...p} d="M7.5 18 A4.5 4.5 0 0 1 16.5 18" />
          <Path {...p} d="M2.5 18 H21.5" />
          <Path {...p} d="M12 13.5 V18" />
        </Svg>
      );
    case 'Recherche':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle {...p} cx="10.5" cy="10.5" r="6.5" />
          <Path {...p} d="M15.6 15.6 L21 21" />
        </Svg>
      );
    case 'Deputes':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle {...p} cx="9" cy="8.5" r="3" />
          <Path {...p} d="M3.5 19 a5.5 5.5 0 0 1 11 0" />
          <Circle {...p} cx="16.8" cy="7.8" r="2.4" />
          <Path {...p} d="M15.2 18.2 a5.2 5.2 0 0 1 5.8 -1.6" />
        </Svg>
      );
    case 'Assistant':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path
            {...p}
            d="M6 5 h12 a2 2 0 0 1 2 2 v6 a2 2 0 0 1 -2 2 h-6 l-4 3 v-3 h-2 a2 2 0 0 1 -2 -2 V7 a2 2 0 0 1 2 -2 z"
          />
          <Path
            {...p}
            d="M12 7.6 l1 2.6 l2.6 1 l-2.6 1 l-1 2.6 l-1 -2.6 l-2.6 -1 l2.6 -1 z"
          />
        </Svg>
      );
    case 'Profil':
    default:
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle {...p} cx="12" cy="8.5" r="3.3" />
          <Path {...p} d="M5.5 19.5 a6.5 6.5 0 0 1 13 0" />
        </Svg>
      );
  }
}
