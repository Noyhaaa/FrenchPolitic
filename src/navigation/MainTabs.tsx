import { StyleSheet, View } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';

import { colors, radius, typography } from '@/theme';
import { TabBarIcon } from '@/components';
import {
  AssistantScreen,
  DeputesScreen,
  ExplorerScreen,
  HomeScreen,
  ProfileScreen,
} from '@/screens';
import type { MainTabsParamList } from './types';

const Tab = createBottomTabNavigator<MainTabsParamList>();

function TabIcon({ name, focused }: { name: keyof MainTabsParamList; focused: boolean }) {
  return (
    <View style={styles.iconWrap}>
      <TabBarIcon
        name={name}
        color={focused ? colors.textPrimary : colors.textTertiary}
        size={24}
      />
      {/* Point d'accent sous l'onglet actif (prototype). */}
      <View style={[styles.dot, { opacity: focused ? 1 : 0 }]} />
    </View>
  );
}

export function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.textPrimary,
        tabBarInactiveTintColor: colors.textTertiary,
        tabBarStyle: styles.tabBar,
        tabBarLabelStyle: styles.label,
        tabBarIcon: ({ focused }) => (
          <TabIcon name={route.name} focused={focused} />
        ),
      })}
    >
      <Tab.Screen name="Accueil" component={HomeScreen} />
      {/* L'onglet garde son nom de route (`Recherche`) — il porte l'icône et
          le libellé de la barre —, mais l'écran est « Explorer » : la recherche
          n'est plus une page vide en attente d'un mot. */}
      <Tab.Screen name="Recherche" component={ExplorerScreen} />
      <Tab.Screen
        name="Deputes"
        component={DeputesScreen}
        options={{ title: 'Parlementaires' }}
      />
      <Tab.Screen name="Assistant" component={AssistantScreen} />
      <Tab.Screen name="Profil" component={ProfileScreen} />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: colors.background,
    borderTopColor: colors.borderStrong,
  },
  label: {
    ...typography.meta,
    fontFamily: undefined,
    fontWeight: '600',
  },
  iconWrap: {
    alignItems: 'center',
    gap: 3,
  },
  dot: {
    width: 4,
    height: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
  },
});
