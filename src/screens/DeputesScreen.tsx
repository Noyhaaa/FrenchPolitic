import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
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
import { Chip, DeputeRow, EmptyView, OfflineBanner } from '@/components';
import { useDeputes } from '@/hooks';
import type { Chambre, DeputeListItem } from '@/types';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/** Filtres de chambre, dans l'ordre constitutionnel des assemblées. */
const CHAMBRES: ReadonlyArray<{ valeur?: Chambre; label: string }> = [
  { valeur: undefined, label: 'Les deux' },
  { valeur: 'assemblee', label: 'Assemblée nationale' },
  { valeur: 'senat', label: 'Sénat' },
];

/**
 * Annuaire des parlementaires : recherche par nom, filtre par chambre puis par
 * groupe. Même gabarit pour tous les groupes, dans l'ordre renvoyé par l'API
 * (§7.4 : aucun groupe n'est mis en avant).
 */
export function DeputesScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const [query, setQuery] = useState('');
  const [chambre, setChambre] = useState<Chambre | undefined>();
  const [groupeId, setGroupeId] = useState<string | undefined>();
  const { deputes, groupes, loading, offline, error } = useDeputes(
    query,
    groupeId,
    chambre,
  );

  const onPressDepute = useCallback(
    (depute: DeputeListItem) =>
      navigation.navigate('DeputeDetail', { deputeId: depute.id }),
    [navigation],
  );

  // Les chips de groupe suivent la chambre choisie : proposer un groupe du
  // Sénat en filtrant l'Assemblée ne ramènerait rien (§2.5).
  const groupesVisibles = chambre
    ? groupes.filter((g) => g.chambre === chambre)
    : groupes;

  // Changer de chambre invalide un filtre de groupe qui n'y appartient pas.
  const choisirChambre = (valeur?: Chambre) => {
    setChambre(valeur);
    setGroupeId((actuel) => {
      if (!actuel || !valeur) return actuel;
      const groupe = groupes.find((g) => g.id === actuel);
      return groupe && groupe.chambre !== valeur ? undefined : actuel;
    });
  };

  const filtre = query.trim();

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={typography.title}>Parlementaires</Text>
        {/* Effectif réel de la liste servie — jamais un chiffre en dur (§2.5). */}
        <Text style={typography.meta}>
          {deputes.length} parlementaire{deputes.length > 1 ? 's' : ''}
          {filtre || groupeId || chambre ? ' (filtrés)' : ''}
        </Text>

        <View style={styles.searchBox}>
          <Text style={styles.searchIcon} importantForAccessibility="no">
            🔍
          </Text>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Chercher un député, un sénateur…"
            placeholderTextColor={colors.textTertiary}
            style={styles.input}
            returnKeyType="search"
            autoCorrect={false}
            clearButtonMode="while-editing"
            accessibilityLabel="Rechercher un parlementaire"
          />
          {loading ? (
            <ActivityIndicator size="small" color={colors.textTertiary} />
          ) : null}
        </View>

        {/* Chambre d'abord : c'est le filtre le plus large, et il conditionne
            les groupes proposés en dessous. */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chips}
        >
          {CHAMBRES.map((c) => (
            <Chip
              key={c.label}
              actif={chambre === c.valeur}
              label={c.label}
              onPress={() => choisirChambre(c.valeur)}
            />
          ))}
        </ScrollView>

        {groupesVisibles.length > 0 ? (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chips}
          >
            <Chip
              actif={!groupeId}
              label="Tous les groupes"
              onPress={() => setGroupeId(undefined)}
            />
            {groupesVisibles.map((g) => (
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
              title="Aucun parlementaire"
              subtitle="Essayez un autre nom, une autre chambre ou un autre groupe."
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
  list: {
    paddingHorizontal: spacing.lg,
    flexGrow: 1,
  },
  sep: {
    height: 1,
    backgroundColor: colors.border,
  },
});
