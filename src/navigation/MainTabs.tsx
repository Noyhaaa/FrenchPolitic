import { StyleSheet, Text, View } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';

import { colors, radius, typography } from '@/theme';
import {
  AssistantScreen,
  HomeScreen,
  ProfileScreen,
  SearchScreen,
} from '@/screens';
import type { MainTabsParamList } from './types';

const Tab = createBottomTabNavigator<MainTabsParamList>();

const icons: Record<keyof MainTabsParamList, string> = {
  Accueil: '🏛️',
  Recherche: '🔍',
  Assistant: '💬',
  Profil: '👤',
};

function TabIcon({ name, focused }: { name: keyof MainTabsParamList; focused: boolean }) {
  return (
    <View style={styles.iconWrap}>
      <Text style={[styles.icon, { opacity: focused ? 1 : 0.35 }]}>
        {icons[name]}
      </Text>
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
      <Tab.Screen name="Recherche" component={SearchScreen} />
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
  icon: {
    fontSize: 20,
  },
  dot: {
    width: 4,
    height: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
  },
});
