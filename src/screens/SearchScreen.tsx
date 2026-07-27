import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  SectionList,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, radius, spacing, typography } from '@/theme';
import { DeputeRow, DossierCard, EmptyView } from '@/components';
import { themeEmoji } from '@/constants/themes';
import { useRecherche, useThemes } from '@/hooks';
import { DeputeListItem, DossierListItem } from '@/types';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/** Une entrée de résultat : un texte ou un député (sections distinctes). */
type Resultat =
  | { type: 'dossier'; dossier: DossierListItem }
  | { type: 'depute'; depute: DeputeListItem };

/** Chip de filtre, même gabarit que l'annuaire des députés. */
function Chip({
  actif,
  label,
  onPress,
}: {
  actif: boolean;
  label: string;
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
      <Text style={[styles.chipTexte, actif && styles.chipTexteActif]}>
        {label}
      </Text>
    </Pressable>
  );
}

/**
 * Recherche (§3.3) : un champ, des filtres de thème, et des résultats en deux
 * sections — les **textes** puis les **députés**.
 *
 * La requête est multi-termes et classée par pertinence côté API : tous les
 * mots sont exigés, pas forcément côte à côte ni dans le titre (l'index couvre
 * aussi les réponses « pourquoi » / « ce que ça change » et les publics
 * concernés). Un thème seul, sans mot-clé, parcourt le thème. Une section vide
 * est masquée (§2.5), et les députés disparaissent sous filtre de thème — un
 * thème ne qualifie pas une personne.
 */
export function SearchScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const [query, setQuery] = useState('');
  const [theme, setTheme] = useState<string | undefined>();
  const themes = useThemes();
  const { dossiers, deputes, loading, error } = useRecherche(query, theme);

  const onPressDossier = useCallback(
    (dossier: DossierListItem) =>
      navigation.navigate('DossierDetail', { dossierId: dossier.id }),
    [navigation],
  );
  const onPressDepute = useCallback(
    (depute: DeputeListItem) =>
      navigation.navigate('DeputeDetail', { deputeId: depute.id }),
    [navigation],
  );

  const sections: { titre: string; data: Resultat[] }[] = [];
  if (dossiers.length > 0) {
    sections.push({
      titre: 'Textes',
      data: dossiers.map((d) => ({ type: 'dossier', dossier: d })),
    });
  }
  if (deputes.length > 0) {
    sections.push({
      titre: 'Députés',
      data: deputes.map((d) => ({ type: 'depute', depute: d })),
    });
  }

  const chercheQuelqueChose = Boolean(query.trim() || theme);

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={typography.title}>Recherche</Text>
        <View style={styles.searchBox}>
          <Text style={styles.searchIcon}>🔍</Text>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Un thème, un texte, un député…"
            placeholderTextColor={colors.textTertiary}
            style={styles.input}
            returnKeyType="search"
            autoCorrect={false}
            clearButtonMode="while-editing"
            accessibilityLabel="Rechercher un dossier ou un député"
          />
          {loading ? (
            <ActivityIndicator size="small" color={colors.textTertiary} />
          ) : null}
        </View>

        {themes.length > 0 ? (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chips}
          >
            <Chip
              actif={!theme}
              label="Tous"
              onPress={() => setTheme(undefined)}
            />
            {themes.map((t) => (
              <Chip
                key={t.nom}
                actif={theme === t.nom}
                label={`${themeEmoji[t.nom] ?? ''} ${t.nom}`.trim()}
                onPress={() =>
                  setTheme((actuel) => (actuel === t.nom ? undefined : t.nom))
                }
              />
            ))}
          </ScrollView>
        ) : null}
      </View>

      <SectionList
        sections={sections}
        keyExtractor={(item) =>
          item.type === 'dossier' ? item.dossier.id : item.depute.id
        }
        contentContainerStyle={[
          styles.list,
          { paddingBottom: insets.bottom + spacing.xl },
        ]}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        stickySectionHeadersEnabled={false}
        renderSectionHeader={({ section }) =>
          // Un seul type de résultat → l'intitulé de section n'apprend rien.
          sections.length > 1 ? (
            <Text style={[typography.overline, styles.sectionTitre]}>
              {section.titre}
            </Text>
          ) : null
        }
        renderItem={({ item }) =>
          item.type === 'dossier' ? (
            <DossierCard dossier={item.dossier} onPress={onPressDossier} />
          ) : (
            <DeputeRow depute={item.depute} onPress={onPressDepute} />
          )
        }
        ItemSeparatorComponent={() => <View style={{ height: spacing.md }} />}
        ListEmptyComponent={
          loading ? null : error ? (
            <EmptyView
              title="Recherche indisponible"
              subtitle="Impossible de joindre le serveur. Réessayez."
            />
          ) : chercheQuelqueChose ? (
            <EmptyView
              title="Aucun résultat"
              subtitle="Essayez un autre mot-clé (ex. « logement », « énergie »)."
            />
          ) : (
            <EmptyView
              title="Recherchez un texte ou un député"
              subtitle="Tapez un mot-clé, ou choisissez un thème ci-dessus."
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
  chips: {
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  chip: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    paddingVertical: 6,
    paddingHorizontal: 13,
  },
  chipActif: {
    backgroundColor: colors.textPrimary,
  },
  chipTexte: {
    ...typography.label,
    color: colors.textSecondary,
  },
  chipTexteActif: {
    color: colors.textOnLight,
  },
  sectionTitre: {
    marginTop: spacing.md,
    marginBottom: spacing.sm,
    color: colors.textTertiary,
  },
  list: {
    paddingHorizontal: spacing.lg,
    flexGrow: 1,
  },
});
