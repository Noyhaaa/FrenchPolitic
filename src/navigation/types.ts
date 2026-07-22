import type { NavigatorScreenParams } from '@react-navigation/native';

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
};

declare global {
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
