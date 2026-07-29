import { Circle, Path, Svg } from 'react-native-svg';

import type { ThemeScrutin } from '@/types';

/**
 * Icônes à trait fin des écrans « Explorer » et « Glossaire ».
 * Même grammaire que `TabBarIcon` : monochrome, la couleur vient de `color`,
 * trait arrondi. Aucun emoji — le dessin porte le sens, le libellé le confirme.
 */

const COMMUN = {
  fill: 'none' as const,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

export type NomIcone =
  | 'loupe'
  | 'chevronDroite'
  | 'chevronGauche'
  | 'fleche'
  | 'dossiers'
  | 'votes'
  | 'elus'
  | 'assistant'
  | 'glossaire'
  | 'etoile'
  | 'horloge';

interface Props {
  name: NomIcone;
  color: string;
  size?: number;
  strokeWidth?: number;
}

export function IconLigne({ name, color, size = 20, strokeWidth = 1.8 }: Props) {
  const p = { stroke: color, strokeWidth, ...COMMUN };
  const s = { width: size, height: size, viewBox: '0 0 24 24' };

  switch (name) {
    case 'loupe':
      return (
        <Svg {...s}>
          <Circle {...p} cx="11" cy="11" r="7" />
          <Path {...p} d="M20 20 L16.4 16.4" />
        </Svg>
      );
    case 'chevronDroite':
      return (
        <Svg {...s}>
          <Path {...p} d="M9 6 l6 6 -6 6" />
        </Svg>
      );
    case 'chevronGauche':
      return (
        <Svg {...s}>
          <Path {...p} d="M14 6 l-6 6 6 6" />
        </Svg>
      );
    case 'fleche':
      return (
        <Svg {...s}>
          <Path {...p} d="M5 12 h13" />
          <Path {...p} d="M13 6 l6 6 -6 6" />
        </Svg>
      );
    case 'dossiers':
      return (
        <Svg {...s}>
          <Path {...p} d="M5 4 h9 l5 5 v11 H5 z" />
          <Path {...p} d="M14 4 v5 h5" />
        </Svg>
      );
    case 'votes':
      return (
        <Svg {...s}>
          <Path {...p} d="M5 20 V12 M12 20 V5 M19 20 v-5" />
        </Svg>
      );
    case 'elus':
      return (
        <Svg {...s}>
          <Circle {...p} cx="12" cy="9" r="3.4" />
          <Path {...p} d="M5.5 20 a6.5 6.5 0 0 1 13 0" />
        </Svg>
      );
    case 'assistant':
      return (
        <Svg {...s}>
          <Path
            {...p}
            d="M6 5 h12 a2 2 0 0 1 2 2 v6 a2 2 0 0 1 -2 2 h-6 l-4 3 v-3 h-2 a2 2 0 0 1 -2 -2 V7 a2 2 0 0 1 2 -2 z"
          />
          <Path {...p} d="M12 7.6 l1 2.6 l2.6 1 l-2.6 1 l-1 2.6 l-1 -2.6 l-2.6 -1 l2.6 -1 z" />
        </Svg>
      );
    case 'glossaire':
      return (
        <Svg {...s}>
          <Path
            {...p}
            d="M12 6 C10 4.6 7 4.4 5 4.6 v13 c2 -0.2 5 0 7 1.4 c2 -1.4 5 -1.6 7 -1.4 v-13 c-2 -0.2 -5 0 -7 1.4 z"
          />
          <Path {...p} d="M12 6 v13" />
        </Svg>
      );
    case 'etoile':
      return (
        <Svg {...s}>
          <Path
            {...p}
            d="M12 4.5 l2.3 4.8 l5.2 0.7 l-3.8 3.7 l0.9 5.3 l-4.6 -2.5 l-4.6 2.5 l0.9 -5.3 l-3.8 -3.7 l5.2 -0.7 z"
          />
        </Svg>
      );
    case 'horloge':
    default:
      return (
        <Svg {...s}>
          <Circle {...p} cx="12" cy="12" r="9" />
          <Path {...p} d="M12 7 v5 l3 2" />
        </Svg>
      );
  }
}

/**
 * Icône de catégorie (thème). Trait fin, même famille visuelle : c'est ce qui
 * remplace l'emoji de `themeEmoji` sur l'écran Explorer.
 */
export function ThemeIcone({
  theme,
  color,
  size = 21,
  strokeWidth = 1.8,
}: {
  theme: ThemeScrutin;
  color: string;
  size?: number;
  strokeWidth?: number;
}) {
  const p = { stroke: color, strokeWidth, ...COMMUN };
  const s = { width: size, height: size, viewBox: '0 0 24 24' };

  switch (theme) {
    case 'Santé':
      return (
        <Svg {...s}>
          <Path
            {...p}
            d="M12 20 s-7 -4.6 -7 -9.2 A3.9 3.9 0 0 1 12 8 a3.9 3.9 0 0 1 7 2.8 C19 15.4 12 20 12 20 z"
          />
        </Svg>
      );
    case 'Logement':
      return (
        <Svg {...s}>
          <Path {...p} d="M4 11 l8 -6 8 6 v9 H4 z" />
          <Path {...p} d="M10 20 v-5 h4 v5" />
        </Svg>
      );
    case 'Énergie':
      return (
        <Svg {...s}>
          <Path {...p} d="M13 3 L5 13 h5 l-1 8 8 -11 h-5 l1 -7 z" />
        </Svg>
      );
    case 'Justice':
      return (
        <Svg {...s}>
          <Path {...p} d="M12 4 v15 M6 20 h12" />
          <Path
            {...p}
            d="M4.5 8 L12 6 l7.5 2 M4.5 8 L2 13 a3 3 0 0 0 5 0 z M19.5 8 L17 13 a3 3 0 0 0 5 0 z"
          />
        </Svg>
      );
    case 'Éducation':
      return (
        <Svg {...s}>
          <Path {...p} d="M12 5 l9 4 -9 4 -9 -4 z" />
          <Path {...p} d="M6 11 v4 c0 1.2 2.7 2.6 6 2.6 s6 -1.4 6 -2.6 v-4" />
        </Svg>
      );
    case 'Environnement':
      return (
        <Svg {...s}>
          <Path {...p} d="M5 19 C5 11 11 5 19 5 c0 8 -6 14 -14 14 z" />
          <Path {...p} d="M5 19 c3 -3.2 6.5 -5.3 10 -6.4" />
        </Svg>
      );
    case 'Travail':
      return (
        <Svg {...s}>
          <Path {...p} d="M4 8 h16 v11 H4 z" />
          <Path {...p} d="M9 8 V6 a1.5 1.5 0 0 1 1.5 -1.5 h3 A1.5 1.5 0 0 1 15 6 v2" />
          <Path {...p} d="M4 13 h16" />
        </Svg>
      );
    case 'Fiscalité':
    case 'Économie':
      return (
        <Svg {...s}>
          <Path {...p} d="M4 19 h16" />
          <Path {...p} d="M7 19 V11 M12 19 V6 M17 19 v-5" />
        </Svg>
      );
    case 'Transports':
      return (
        <Svg {...s}>
          <Path {...p} d="M5 16 V8 a2 2 0 0 1 2 -2 h10 a2 2 0 0 1 2 2 v8" />
          <Path {...p} d="M3 16 h18" />
          <Circle {...p} cx="8" cy="19" r="1.6" />
          <Circle {...p} cx="16" cy="19" r="1.6" />
        </Svg>
      );
    case 'Agriculture':
      return (
        <Svg {...s}>
          <Path {...p} d="M12 20 V9" />
          <Path {...p} d="M12 9 C9 9 7 7 7 4 c3 0 5 2 5 5 z M12 9 c3 0 5 -2 5 -5 -3 0 -5 2 -5 5 z" />
          <Path {...p} d="M5 20 h14" />
        </Svg>
      );
    case 'Sécurité':
    case 'International & Défense':
      return (
        <Svg {...s}>
          <Path {...p} d="M12 4 l7 3 v5 c0 4 -3 6.6 -7 8 -4 -1.4 -7 -4 -7 -8 V7 z" />
        </Svg>
      );
    case 'Immigration':
      return (
        <Svg {...s}>
          <Circle {...p} cx="12" cy="12" r="8" />
          <Path {...p} d="M4 12 h16 M12 4 c2.6 2.4 2.6 13.2 0 16 -2.6 -2.8 -2.6 -13.6 0 -16 z" />
        </Svg>
      );
    case 'Institutions':
    case 'Vie parlementaire':
      return (
        <Svg {...s}>
          <Path {...p} d="M4 18 A8 8 0 0 1 20 18" />
          <Path {...p} d="M7.5 18 A4.5 4.5 0 0 1 16.5 18" />
          <Path {...p} d="M2.5 18 H21.5" />
          <Path {...p} d="M12 13.5 V18" />
        </Svg>
      );
    case 'Culture':
    case 'Sport':
    default:
      return (
        <Svg {...s}>
          <Path {...p} d="M5 4 h9 l5 5 v11 H5 z" />
          <Path {...p} d="M14 4 v5 h5" />
        </Svg>
      );
  }
}
