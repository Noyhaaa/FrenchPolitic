import { useCallback } from 'react';
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, serif, spacing, typography } from '@/theme';
import {
  BrandHeader,
  DossierTile,
  EmptyView,
  ErrorView,
  HeroDossier,
  LoadingView,
  OfflineBanner,
  RecapVotes,
} from '@/components';
import { themeEmoji } from '@/constants/themes';
import { useAccueil, useRecap } from '@/hooks';
import { DossierListItem } from '@/types';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/** Hauteur de la barre de navigation superposée au hero (hors safe area). */
const NAV_HEIGHT = 52;

/** Rangée horizontale de vignettes (le « Row » du prototype, façon Netflix). */
function TuilesRow({
  titre,
  dossiers,
  onPress,
}: {
  titre: string;
  dossiers: DossierListItem[];
  onPress: (d: DossierListItem) => void;
}) {
  if (dossiers.length === 0) return null;
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text style={typography.sectionTitle}>{titre}</Text>
        <Text style={typography.meta}>
          {dossiers.length} dossier{dossiers.length > 1 ? 's' : ''}
        </Text>
      </View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.rail}
      >
        {dossiers.map((d) => (
          <DossierTile key={d.id} dossier={d} onPress={onPress} />
        ))}
      </ScrollView>
    </View>
  );
}

export function HomeScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const { data, loading, refreshing, offline, error, refresh, retry } =
    useAccueil();
  const { data: recap, refresh: refreshRecap } = useRecap();

  const onPressDossier = useCallback(
    (dossier: DossierListItem) =>
      navigation.navigate('DossierDetail', { dossierId: dossier.id }),
    [navigation],
  );

  const openSearch = useCallback(
    () => navigation.navigate('MainTabs', { screen: 'Recherche' }),
    [navigation],
  );

  // Barre superposée : wordmark + recherche, fondue dans le hero (prototype).
  const topNav = (
    <View
      style={[styles.topNav, { paddingTop: insets.top }]}
      pointerEvents="box-none"
    >
      <LinearGradient
        colors={[colors.background, 'transparent']}
        style={StyleSheet.absoluteFill}
        pointerEvents="none"
      />
      <View style={styles.topNavRow} pointerEvents="box-none">
        <Text style={styles.wordmark}>Décrypté</Text>
        <Pressable
          onPress={openSearch}
          hitSlop={10}
          accessibilityRole="button"
          accessibilityLabel="Rechercher un dossier"
        >
          <Text style={styles.searchIcon}>🔍</Text>
        </Pressable>
      </View>
    </View>
  );

  // Erreur dure (pas de cache disponible) : on remplace l'écran.
  if (!loading && error && !data) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <BrandHeader />
        <ErrorView
          message={
            error === 'network'
              ? "Impossible de joindre le serveur. Vérifiez votre connexion."
              : 'Une erreur est survenue. Réessayez dans un instant.'
          }
          onRetry={retry}
        />
      </View>
    );
  }

  if (loading && !data) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <BrandHeader />
        <LoadingView label="Chargement des dossiers…" />
      </View>
    );
  }

  const accueil = data;

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={{ paddingBottom: insets.bottom + spacing.xl }}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              void refreshRecap();
              refresh();
            }}
            tintColor={colors.brand}
          />
        }
      >
        {accueil?.aLaUne ? (
          <HeroDossier
            dossier={accueil.aLaUne}
            onPress={onPressDossier}
            topInset={insets.top + NAV_HEIGHT}
          />
        ) : null}
        {offline ? <OfflineBanner /> : null}

        {accueil && (accueil.aLaUne || accueil.sections.length > 0) ? (
          <View style={styles.sectionsBlock}>
            <TuilesRow
              titre="Aujourd'hui"
              dossiers={accueil.aujourdhui}
              onPress={onPressDossier}
            />
            <TuilesRow
              titre="Hier"
              dossiers={accueil.hier}
              onPress={onPressDossier}
            />

            {recap ? (
              <View style={styles.recapWrap}>
                <RecapVotes recap={recap} />
              </View>
            ) : null}

            {accueil.sections.map((section) => (
              <TuilesRow
                key={section.theme}
                titre={`${themeEmoji[section.theme] ?? themeEmoji.Autre}  ${
                  section.theme
                }`}
                dossiers={section.dossiers}
                onPress={onPressDossier}
              />
            ))}
          </View>
        ) : (
          <EmptyView
            title="Aucun dossier pour le moment."
            subtitle="Tirez vers le bas pour actualiser."
          />
        )}
      </ScrollView>
      {topNav}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  topNav: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
  },
  topNavRow: {
    height: NAV_HEIGHT,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
  },
  wordmark: {
    fontSize: 21,
    fontWeight: '900',
    fontFamily: serif,
    letterSpacing: -0.4,
    color: colors.textPrimary,
  },
  searchIcon: {
    fontSize: 17,
  },
  sectionsBlock: {
    gap: spacing.xxl,
    paddingTop: spacing.xxl,
    paddingBottom: spacing.xxl,
  },
  section: {
    gap: spacing.md,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
  },
  rail: {
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xs,
  },
  recapWrap: {
    paddingHorizontal: spacing.lg,
  },
});
