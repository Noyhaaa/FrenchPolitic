import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, radius, spacing, typography } from '@/theme';
import { DeputeRow, EmptyView, OfflineBanner } from '@/components';
import { useDeputes } from '@/hooks';
import type { DeputeListItem } from '@/types';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

function Chip({
  actif,
  label,
  couleur,
  onPress,
}: {
  actif: boolean;
  label: string;
  couleur?: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.chip, actif && styles.chipActif]}
      accessibilityRole="button"
      accessibilityState={{ selected: actif }}
      accessibilityLabel={`Filtrer : ${label}`}
    >
      {couleur ? (
        <View
          style={[styles.chipPastille, { backgroundColor: couleur }]}
          importantForAccessibility="no"
        />
      ) : null}
      <Text style={[styles.chipTexte, actif && styles.chipTexteActif]}>
        {label}
      </Text>
    </Pressable>
  );
}

/**
 * Annuaire des députés : recherche par nom et filtre par groupe. Même gabarit
 * pour tous les groupes, dans l'ordre renvoyé par l'API (§7.4 : aucun groupe
 * n'est mis en avant).
 */
export function DeputesScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const [query, setQuery] = useState('');
  const [groupeId, setGroupeId] = useState<string | undefined>();
  const { deputes, groupes, loading, offline, error } = useDeputes(
    query,
    groupeId,
  );

  const onPressDepute = useCallback(
    (depute: DeputeListItem) =>
      navigation.navigate('DeputeDetail', { deputeId: depute.id }),
    [navigation],
  );

  const filtre = query.trim();

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={typography.title}>Assemblée nationale</Text>
        {/* Effectif réel de la liste servie — jamais un chiffre en dur (§2.5). */}
        <Text style={typography.meta}>
          {deputes.length} député{deputes.length > 1 ? 's' : ''}
          {filtre || groupeId ? ' (filtrés)' : ''}
        </Text>

        <View style={styles.searchBox}>
          <Text style={styles.searchIcon} importantForAccessibility="no">
            🔍
          </Text>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Chercher un député…"
            placeholderTextColor={colors.textTertiary}
            style={styles.input}
            returnKeyType="search"
            autoCorrect={false}
            clearButtonMode="while-editing"
            accessibilityLabel="Rechercher un député"
          />
          {loading ? (
            <ActivityIndicator size="small" color={colors.textTertiary} />
          ) : null}
        </View>

        {groupes.length > 0 ? (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chips}
          >
            <Chip
              actif={!groupeId}
              label="Tous"
              onPress={() => setGroupeId(undefined)}
            />
            {groupes.map((g) => (
              <Chip
                key={g.id}
                actif={groupeId === g.id}
                label={g.abrev !== '?' ? g.abrev : g.nom}
                couleur={g.couleur}
                onPress={() =>
                  setGroupeId((actuel) => (actuel === g.id ? undefined : g.id))
                }
              />
            ))}
          </ScrollView>
        ) : null}
      </View>

      {offline ? <OfflineBanner /> : null}

      <FlatList
        data={deputes}
        keyExtractor={(item) => item.id}
        contentContainerStyle={[
          styles.list,
          { paddingBottom: insets.bottom + spacing.xl },
        ]}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        renderItem={({ item }) => (
          <DeputeRow depute={item} onPress={onPressDepute} />
        )}
        ItemSeparatorComponent={() => <View style={styles.sep} />}
        ListEmptyComponent={
          loading ? null : error ? (
            <EmptyView
              title="Annuaire indisponible"
              subtitle="Impossible de joindre le serveur. Réessayez."
            />
          ) : (
            <EmptyView
              title="Aucun député"
              subtitle="Essayez un autre nom ou un autre groupe."
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
    gap: spacing.sm,
  },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    marginTop: spacing.sm,
  },
  searchIcon: {
    fontSize: 16,
  },
  input: {
    flex: 1,
    paddingVertical: spacing.md,
    ...typography.body,
  },
  chips: {
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    paddingVertical: 6,
    paddingHorizontal: 13,
  },
  chipActif: {
    backgroundColor: colors.textPrimary,
  },
  chipPastille: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  chipTexte: {
    ...typography.label,
    color: colors.textSecondary,
  },
  chipTexteActif: {
    color: colors.textOnLight,
  },
  list: {
    paddingHorizontal: spacing.lg,
    flexGrow: 1,
  },
  sep: {
    height: 1,
    backgroundColor: colors.border,
  },
});
