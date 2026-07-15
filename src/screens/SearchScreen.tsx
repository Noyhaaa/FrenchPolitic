import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, radius, spacing, typography } from '@/theme';
import { DossierCard, EmptyView } from '@/components';
import { useDossierSearch } from '@/hooks';
import { DossierListItem } from '@/types';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/**
 * Recherche simple (§3.3) : un champ, recherche plein texte via l'API sur le
 * titre reformulé + titre officiel + thème. Pas de filtres avancés en V1.
 */
export function SearchScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const [query, setQuery] = useState('');
  const { results, loading, error } = useDossierSearch(query);

  const onPressDossier = useCallback(
    (dossier: DossierListItem) =>
      navigation.navigate('DossierDetail', { dossierId: dossier.id }),
    [navigation],
  );

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={typography.title}>Recherche</Text>
        <View style={styles.searchBox}>
          <Text style={styles.searchIcon}>🔍</Text>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Un thème, un texte, un mot-clé…"
            placeholderTextColor={colors.textTertiary}
            style={styles.input}
            returnKeyType="search"
            autoCorrect={false}
            clearButtonMode="while-editing"
            accessibilityLabel="Rechercher un dossier"
          />
          {loading ? (
            <ActivityIndicator size="small" color={colors.textTertiary} />
          ) : null}
        </View>
      </View>

      <FlatList
        data={results}
        keyExtractor={(item) => item.id}
        contentContainerStyle={[
          styles.list,
          { paddingBottom: insets.bottom + spacing.xl },
        ]}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        renderItem={({ item }) => (
          <DossierCard dossier={item} onPress={onPressDossier} />
        )}
        ItemSeparatorComponent={() => <View style={{ height: spacing.md }} />}
        ListEmptyComponent={
          loading ? null : error ? (
            <EmptyView
              title="Recherche indisponible"
              subtitle="Impossible de joindre le serveur. Réessayez."
            />
          ) : query.trim() ? (
            <EmptyView
              title="Aucun résultat"
              subtitle="Essayez un autre mot-clé (ex. « logement », « énergie »)."
            />
          ) : (
            <EmptyView
              title="Recherchez un dossier"
              subtitle="Tapez un thème ou un mot-clé pour commencer."
            />
          )
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
    gap: spacing.md,
  },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
  },
  searchIcon: {
    fontSize: 16,
  },
  input: {
    flex: 1,
    paddingVertical: spacing.md,
    ...typography.body,
  },
  list: {
    paddingHorizontal: spacing.lg,
    flexGrow: 1,
  },
});
