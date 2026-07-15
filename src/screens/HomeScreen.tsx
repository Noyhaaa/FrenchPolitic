import { useCallback } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, radius, spacing, typography } from '@/theme';
import {
  BrandHeader,
  DossierCard,
  EmptyView,
  ErrorView,
  LoadingView,
  OfflineBanner,
} from '@/components';
import { useDossiers } from '@/hooks';
import { DossierListItem } from '@/types';
import { formatTempsLecture } from '@/utils/format';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function HomeScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const {
    data,
    loading,
    refreshing,
    loadingMore,
    hasMore,
    offline,
    error,
    refresh,
    retry,
    loadMore,
  } = useDossiers();

  const onPressDossier = useCallback(
    (dossier: DossierListItem) =>
      navigation.navigate('DossierDetail', { dossierId: dossier.id }),
    [navigation],
  );

  const dossiers = data ?? [];
  const tempsTotalSec = dossiers.reduce((s, x) => s + x.tempsLectureSec, 0);

  const header = (
    <BrandHeader
      right={
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>👤</Text>
        </View>
      }
    />
  );

  // Erreur dure (pas de cache disponible) : on remplace la liste.
  if (!loading && error && dossiers.length === 0) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        {header}
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

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {header}
      {offline ? <OfflineBanner /> : null}
      {loading && dossiers.length === 0 ? (
        <LoadingView label="Chargement des dossiers…" />
      ) : (
        <FlatList
          data={dossiers}
          keyExtractor={(item) => item.id}
          contentContainerStyle={[
            styles.list,
            { paddingBottom: insets.bottom + spacing.xl },
          ]}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={refresh}
              tintColor={colors.brand}
            />
          }
          ListHeaderComponent={
            <View style={styles.hero}>
              <Text style={typography.hero}>Aujourd'hui à{'\n'}l'Assemblée</Text>
              <View style={styles.heroMeta}>
                <Text style={typography.bodySecondary}>
                  {dossiers.length} dossiers · {formatTempsLecture(tempsTotalSec)}
                </Text>
                <View style={styles.streak}>
                  <Text style={styles.streakText}>🔥 3 jours</Text>
                </View>
              </View>
            </View>
          }
          renderItem={({ item }) => (
            <DossierCard dossier={item} onPress={onPressDossier} />
          )}
          ItemSeparatorComponent={() => <View style={{ height: spacing.md }} />}
          onEndReached={loadMore}
          onEndReachedThreshold={0.4}
          ListFooterComponent={
            loadingMore ? (
              <ActivityIndicator
                color={colors.brand}
                style={{ paddingVertical: spacing.lg }}
              />
            ) : !hasMore && dossiers.length > 0 ? (
              <Text style={[typography.meta, styles.end]}>
                Vous êtes à jour.
              </Text>
            ) : null
          }
          ListEmptyComponent={
            <EmptyView
              title="Aucun dossier pour le moment."
              subtitle="Tirez vers le bas pour actualiser."
            />
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  list: {
    paddingHorizontal: spacing.lg,
  },
  hero: {
    paddingTop: spacing.sm,
    paddingBottom: spacing.lg,
    gap: spacing.md,
  },
  heroMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  streak: {
    backgroundColor: colors.accentWarmSoft,
    borderRadius: radius.pill,
    paddingVertical: 4,
    paddingHorizontal: spacing.md,
  },
  streakText: {
    ...typography.badge,
    color: colors.accentWarm,
  },
  avatar: {
    width: 34,
    height: 34,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  avatarText: {
    fontSize: 16,
  },
  end: {
    textAlign: 'center',
    paddingVertical: spacing.lg,
  },
});
