/**
 * Palette de l'application « Décrypté » — thème sombre éditorial.
 * Reprise du prototype `Political Mobile App Design2` : fond #141414, cartes
 * #1E1E1E, séparateurs en blanc translucide, accents vert / rouge / ambre /
 * pervenche. On garde une identité neutre (charte de neutralité §7 du MVP) :
 * la couleur ne porte jamais seule une information (toujours icône + libellé, §8).
 */
export const colors = {
  // Fonds
  background: '#141414', // page
  surface: '#1E1E1E', // cartes
  surfaceAlt: '#2A2A2C', // chips inactifs / pastilles neutres
  surfaceMuted: 'rgba(255,255,255,0.06)', // pistes de barres, blocs internes

  // Texte
  textPrimary: '#FFFFFF',
  textSecondary: 'rgba(255,255,255,0.55)',
  textTertiary: 'rgba(255,255,255,0.34)',
  textOnAccent: '#FFFFFF',
  textOnLight: '#141414', // texte posé sur un fond clair (bouton blanc, chip actif)

  // Marque (pervenche du prototype : liens, actions, « Voir tout »)
  brand: '#8B9CF4',
  brandSoft: 'rgba(139,156,244,0.14)',

  // Bordures / séparateurs
  border: 'rgba(255,255,255,0.07)',
  borderStrong: 'rgba(255,255,255,0.16)',

  // Statuts de scrutin (jamais la couleur seule — toujours un libellé, cf. RGAA §8)
  adopte: '#22C55E',
  adopteSoft: 'rgba(34,197,94,0.12)',
  rejete: '#FF3040',
  rejeteSoft: 'rgba(255,48,64,0.12)',
  enCours: '#F59E0B',
  enCoursSoft: 'rgba(245,158,11,0.12)',

  // Résultats de vote (prototype : abstention = ambre)
  pour: '#22C55E',
  contre: '#FF3040',
  abstention: '#F59E0B',
  nonVotant: 'rgba(255,255,255,0.18)',

  // Intitulés de sous-blocs (CONTEXTE, OBJECTIF… — mono discret)
  miniLabel: 'rgba(255,255,255,0.40)',

  // Accents divers
  accentWarm: '#F59E0B',
  accentWarmSoft: 'rgba(245,158,11,0.12)',

  // Superposition sur les tuiles teintées (lisibilité du texte par-dessus)
  overlay: 'rgba(0,0,0,0.55)',
} as const;

export type Colors = typeof colors;
