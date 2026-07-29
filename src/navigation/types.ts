import type { NavigatorScreenParams } from '@react-navigation/native';

import type { ThemeScrutin } from '@/types';

export type MainTabsParamList = {
  Accueil: undefined;
  Recherche: undefined;
  Deputes: undefined;
  Assistant: undefined;
  Profil: undefined;
};

export type RootStackParamList = {
  MainTabs: NavigatorScreenParams<MainTabsParamList>;
  DossierDetail: { dossierId: string };
  ScrutinDetail: { scrutinId: string };
  DeputeDetail: { deputeId: string };
  // Résultats de recherche. Écran à part d'Explorer, qui fait découvrir : ici
  // on montre ce qu'on a trouvé, en chronologie. `query` vide + `theme` =
  // parcourir une catégorie ; les deux vides = parcourir tous les textes.
  Dossiers: { query: string; theme?: ThemeScrutin };
  // Glossaire : au niveau du stack racine, comme les fiches — on l'atteint
  // depuis l'onglet Explorer, mais aussi depuis l'aide en ligne d'une frise de
  // dossier ou d'un titre de vote (`DefinitionGlossaire`).
  Glossaire: undefined;
  GlossaireTerme: { termeId: string };
};

declare global {
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
