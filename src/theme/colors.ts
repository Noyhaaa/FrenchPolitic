/**
 * Palette de l'application « Décrypté ».
 * Inspirée des maquettes : fond crème chaud, cartes claires, accents sobres.
 * On garde une identité neutre (charte de neutralité §7 du MVP).
 */
export const colors = {
  // Fonds
  background: '#EDE7DC', // crème chaud (fil / écrans)
  surface: '#FBF8F3', // cartes
  surfaceAlt: '#F3EEE4', // blocs internes / pastilles neutres
  surfaceMuted: '#E7E0D3',

  // Texte
  textPrimary: '#1F2421',
  textSecondary: '#6B6459',
  textTertiary: '#98917F',
  textOnAccent: '#FFFFFF',

  // Marque
  brand: '#2E6FB5', // bleu « AN »
  brandSoft: '#DCE8F5',

  // Bordures / séparateurs
  border: '#E2D9C8',
  borderStrong: '#D2C7B2',

  // Statuts de scrutin (jamais la couleur seule — toujours un libellé, cf. RGAA §8)
  adopte: '#2F8F4E',
  adopteSoft: '#DCF0E1',
  rejete: '#C0392B',
  rejeteSoft: '#F6DED9',
  enCours: '#C58A1A',
  enCoursSoft: '#F6E9C9',

  // Résultats de vote (maquette : contre = terracotta, pas rouge vif)
  pour: '#2F8F4E',
  contre: '#C4703C',
  abstention: '#B7A98D',
  nonVotant: '#CDC3AE',

  // Intitulés de sous-blocs (CONTEXTE, OBJECTIF… — ocre discret)
  miniLabel: '#A98C45',

  // Accents divers
  accentWarm: '#D98A3D', // pastille « 3 jours »
  accentWarmSoft: '#F6E4CF',
} as const;

export type Colors = typeof colors;
