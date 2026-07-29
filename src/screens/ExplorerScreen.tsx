import { useCallback, useMemo, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, mono, radius, serifDisplay, serifDisplaySemi, spacing, typography } from '@/theme';
import { IconLigne, ThemeIcone } from '@/components';
import { useThemes } from '@/hooks';
import type { ThemeListItem, ThemeScrutin } from '@/types';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/** Une porte d'entrée de la rangée sous le champ de recherche. */
interface Entree {
  cle: string;
  label: string;
  icone: 'dossiers' | 'elus' | 'assistant' | 'glossaire';
  /** Mise en avant pervenche (le glossaire, qu'on veut faire découvrir). */
  accent?: boolean;
  onPress: () => void;
}

/**
 * Écran « Explorer » (§3.3) — remplace l'ancien SearchScreen.
 *
 * L'écran ne montre plus un vide en attente d'un mot : il propose des portes
 * d'entrée (textes, parlementaires, assistant, glossaire) puis les
 * **catégories**, mises en valeur — une en tête d'affiche, les autres en
 * rangées.
 *
 * ⚠️ Il **n'interroge pas** la recherche : chercher ou toucher une catégorie
 * OUVRE l'écran `Dossiers`, qui montre les résultats en chronologie. Explorer
 * fait découvrir, Dossiers montre ce qu'on a trouvé — deux rôles, deux pages.
 * Les afficher au même endroit ferait disparaître la découverte au premier mot
 * tapé, et le retour arrière n'aurait plus de sens.
 *
 * Aucune donnée inventée (§2.5) : les décomptes viennent de `useThemes`, et une
 * statistique non fournie est simplement masquée.
 */
export function ExplorerScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const [query, setQuery] = useState('');
  // Écrêtage des catégories, même geste que les listes longues de la fiche
  // dossier (`AmendementsSection`) : un aperçu, puis « Voir les N autres ».
  const [toutesCategories, setToutesCategories] = useState(false);
  const themes = useThemes();

  /**
   * Toute recherche OUVRE l'écran Dossiers : Explorer fait découvrir, Dossiers
   * montre les résultats. Les deux ne doivent pas se ressembler, et surtout pas
   * se remplacer l'un l'autre sur place — sinon on ne sait plus où l'on est, et
   * revenir en arrière effacerait la page de découverte.
   */
  const ouvrirResultats = useCallback(
    (params: { query: string; theme?: ThemeScrutin }) =>
      navigation.navigate('Dossiers', params),
    [navigation],
  );

  /** Les catégories les mieux fournies d'abord : la vedette est la première. */
  const classees = useMemo<ThemeListItem[]>(
    () => [...themes].sort((a, b) => b.nombre - a.nombre),
    [themes],
  );
  const vedette = classees[0];
  const suivantes = toutesCategories ? classees.slice(1) : classees.slice(1, 5);
  const restantes = Math.max(classees.length - 5, 0);
  const total = useMemo(
    () => classees.reduce((somme, t) => somme + t.nombre, 0),
    [classees],
  );

  const entrees: Entree[] = [
    {
      cle: 'dossiers',
      label: 'Dossiers',
      icone: 'dossiers',
      // Sans mot ni catégorie : la chronologie de tous les textes, du plus
      // récent au plus ancien. C'est « parcourir », le pendant de « chercher ».
      onPress: () => ouvrirResultats({ query: '' }),
    },
    {
      cle: 'elus',
      label: 'Élus',
      icone: 'elus',
      onPress: () => navigation.navigate('MainTabs', { screen: 'Deputes' }),
    },
    {
      cle: 'assistant',
      label: 'Assistant',
      icone: 'assistant',
      onPress: () => navigation.navigate('MainTabs', { screen: 'Assistant' }),
    },
    {
      cle: 'glossaire',
      label: 'Glossaire',
      icone: 'glossaire',
      accent: true,
      onPress: () => navigation.navigate('Glossaire'),
    },
  ];

  // La saisie ne cherche pas au fil des frappes : elle prépare une requête que
  // la touche « Rechercher » emmène sur l'écran Dossiers. Rien à débouncer ici,
  // donc — c'est cet écran-là qui interroge l'API.
  const lancerRecherche = () => {
    const terme = query.trim();
    if (terme) ouvrirResultats({ query: terme });
  };

  const champRecherche = (
    <View style={styles.searchBox}>
      <IconLigne name="loupe" color={colors.brand} size={18} strokeWidth={2} />
      <TextInput
        value={query}
        onChangeText={setQuery}
        onSubmitEditing={lancerRecherche}
        placeholder="Dossier, texte, élu, terme…"
        placeholderTextColor={colors.textTertiary}
        style={styles.input}
        returnKeyType="search"
        autoCorrect={false}
        clearButtonMode="while-editing"
        accessibilityLabel="Rechercher un dossier, un élu ou un terme"
      />
    </View>
  );

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={styles.eyebrow}>Décrypté · S’informer</Text>
        <Text style={styles.titre}>Explorer</Text>
        {total > 0 ? (
          <Text style={styles.chapeau}>
            {total} dossiers, {classees.length} catégories, 1 glossaire pour tout
            décoder.
          </Text>
        ) : null}
        {champRecherche}
      </View>

      {
        <ScrollView
          contentContainerStyle={[
            styles.decouverte,
            { paddingBottom: insets.bottom + spacing.xxxl },
          ]}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.entrees}>
            {entrees.map((entree) => (
              <Pressable
                key={entree.cle}
                onPress={entree.onPress}
                style={[styles.entree, entree.accent && styles.entreeAccent]}
                accessibilityRole="button"
                accessibilityLabel={entree.label}
              >
                <IconLigne
                  name={entree.icone}
                  color={entree.accent ? colors.splashLigneSoft : colors.brand}
                  size={20}
                />
                <Text
                  style={[
                    styles.entreeLabel,
                    entree.accent && styles.entreeLabelAccent,
                  ]}
                  numberOfLines={1}
                >
                  {entree.label}
                </Text>
              </Pressable>
            ))}
          </View>

          {vedette ? (
            <>
              {/* Pas de faux lien à droite du titre : tout ce qui ressemble à
                  une action doit en être une. Le décompte, lui, est un fait. */}
              <View style={styles.sectionEntete}>
                <Text style={typography.overline}>Catégories</Text>
                <Text style={styles.lienDiscret}>{classees.length}</Text>
              </View>

              <Pressable
                onPress={() => ouvrirResultats({ query: '', theme: vedette.nom })}
                accessibilityRole="button"
                accessibilityLabel={
                  'Catégorie ' + vedette.nom + ', ' + vedette.nombre + ' dossiers'
                }
                style={styles.vedetteWrap}
              >
                <LinearGradient
                  colors={[
                    'rgba(139,156,244,0.19)',
                    'rgba(139,156,244,0.04)',
                    colors.surface,
                  ]}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 0.9, y: 1 }}
                  style={styles.vedette}
                >
                  <View style={styles.vedetteEyebrowLigne}>
                    <View style={styles.puce} />
                    <Text style={styles.vedetteEyebrow}>
                      La plus fournie en dossiers
                    </Text>
                  </View>

                  <View style={styles.vedetteHaut}>
                    <View style={styles.vedetteTexte}>
                      <Text style={styles.vedetteTitre}>{vedette.nom}</Text>
                      <Text style={styles.vedetteSous}>
                        {vedette.nombre} textes suivis, du dépôt au vote final
                      </Text>
                    </View>
                    <View style={styles.vedettePastille}>
                      <IconLigne
                        name="chevronDroite"
                        color={colors.splashLigneSoft}
                        size={18}
                        strokeWidth={2}
                      />
                    </View>
                  </View>

                  <View style={styles.stats}>
                    <View>
                      <Text style={styles.statValeur}>{vedette.nombre}</Text>
                      <Text style={styles.statLabel}>dossiers</Text>
                    </View>
                    <View style={styles.statSeparateur} />
                    <View>
                      <Text style={styles.statValeur}>
                        {Math.round((vedette.nombre / Math.max(total, 1)) * 100)}%
                      </Text>
                      <Text style={styles.statLabel}>du fil</Text>
                    </View>
                  </View>
                </LinearGradient>
              </Pressable>

              <View style={styles.rangees}>
                {suivantes.map((categorie, index) => (
                  <Pressable
                    key={categorie.nom}
                    onPress={() =>
                      ouvrirResultats({ query: '', theme: categorie.nom })
                    }
                    accessibilityRole="button"
                    accessibilityLabel={
                      'Catégorie ' +
                      categorie.nom +
                      ', ' +
                      categorie.nombre +
                      ' dossiers'
                    }
                  >
                    {index > 0 ? <View style={styles.filet} /> : null}
                    <View style={styles.rangee}>
                      <View style={styles.rangeeIcone}>
                        <ThemeIcone theme={categorie.nom} color={colors.brand} />
                      </View>
                      <View style={styles.rangeeTexte}>
                        <Text style={styles.rangeeTitre} numberOfLines={1}>
                          {categorie.nom}
                        </Text>
                        <Text style={styles.rangeeMeta}>
                          {categorie.nombre} DOSSIERS
                        </Text>
                      </View>
                      <IconLigne
                        name="chevronDroite"
                        color={colors.textTertiary}
                        size={17}
                        strokeWidth={2}
                      />
                    </View>
                  </Pressable>
                ))}
              </View>

              {/* Le bouton déplie vraiment la liste — il ne renvoyait qu'au
                  champ de recherche, qui ne montre aucune catégorie. */}
              {restantes > 0 ? (
                <Pressable
                  onPress={() => setToutesCategories((t) => !t)}
                  style={styles.boutonFantome}
                  accessibilityRole="button"
                  accessibilityState={{ expanded: toutesCategories }}
                  accessibilityLabel={
                    toutesCategories
                      ? 'Réduire la liste des catégories'
                      : `Voir les ${restantes} autres catégories`
                  }
                >
                  <Text style={styles.boutonFantomeTexte}>
                    {toutesCategories
                      ? 'Réduire ▲'
                      : `Voir les ${restantes} autres ▼`}
                  </Text>
                </Pressable>
              ) : null}
            </>
          ) : null}
        </ScrollView>
      }
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
  },
  eyebrow: {
    fontFamily: mono,
    fontSize: 10.5,
    fontWeight: '700',
    letterSpacing: 1.7,
    textTransform: 'uppercase',
    color: colors.brand,
  },
  titre: {
    fontFamily: serifDisplay,
    fontSize: 32,
    lineHeight: 38,
    letterSpacing: -0.5,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  chapeau: {
    ...typography.bodySecondary,
    marginTop: spacing.xs + 2,
    maxWidth: 290,
  },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm + 2,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: 'rgba(139,156,244,0.5)',
    borderRadius: radius.lg - 2,
    paddingHorizontal: spacing.lg - 1,
    marginTop: spacing.lg + 1,
  },
  input: { flex: 1, paddingVertical: spacing.md + 2, ...typography.body },
  decouverte: { paddingHorizontal: spacing.xl },
  entrees: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
  entree: {
    flex: 1,
    alignItems: 'center',
    gap: spacing.sm - 1,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xs,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md + 1,
  },
  entreeAccent: {
    backgroundColor: colors.brandSoft,
    borderColor: 'rgba(139,156,244,0.32)',
  },
  entreeLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.82)',
  },
  entreeLabelAccent: { color: colors.splashLigneSoft },
  sectionEntete: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.xxl + 2,
    marginBottom: spacing.md,
  },
  lienDiscret: { fontSize: 11.5, fontWeight: '600', color: colors.textTertiary },
  vedetteWrap: {
    borderRadius: radius.xl - 2,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(139,156,244,0.26)',
  },
  vedette: { padding: spacing.lg + 1 },
  vedetteEyebrowLigne: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  puce: {
    width: 6,
    height: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
  },
  vedetteEyebrow: {
    fontFamily: mono,
    fontSize: 9.5,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
    color: colors.textSecondary,
  },
  vedetteHaut: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    gap: spacing.md,
  },
  vedetteTexte: { flex: 1 },
  vedetteTitre: {
    fontFamily: serifDisplay,
    fontSize: 25,
    lineHeight: 29,
    letterSpacing: -0.4,
    color: colors.textPrimary,
  },
  vedetteSous: { ...typography.bodySecondary, fontSize: 13, marginTop: 5 },
  vedettePastille: {
    width: 34,
    height: 34,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(139,156,244,0.18)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stats: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.lg - 2,
    marginTop: spacing.lg - 2,
    paddingTop: spacing.md + 1,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.09)',
  },
  statValeur: {
    fontFamily: mono,
    fontSize: 17,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  statLabel: {
    fontFamily: mono,
    fontSize: 9.5,
    fontWeight: '500',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    color: colors.textTertiary,
    marginTop: 3,
  },
  statSeparateur: {
    width: 1,
    height: 26,
    backgroundColor: 'rgba(255,255,255,0.09)',
  },
  rangees: {
    marginTop: spacing.md - 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.xl - 2,
    overflow: 'hidden',
  },
  filet: {
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.06)',
    marginLeft: 71,
  },
  rangee: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md + 1,
    paddingVertical: spacing.md + 3,
    paddingHorizontal: spacing.lg,
  },
  rangeeIcone: {
    width: 42,
    height: 42,
    borderRadius: radius.md,
    backgroundColor: colors.brandSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rangeeTexte: { flex: 1 },
  rangeeTitre: {
    fontFamily: serifDisplaySemi,
    fontSize: 17,
    lineHeight: 21,
    letterSpacing: -0.2,
    color: colors.textPrimary,
  },
  rangeeMeta: {
    fontFamily: mono,
    fontSize: 11,
    fontWeight: '500',
    letterSpacing: 0.3,
    color: colors.miniLabel,
    marginTop: 5,
  },
  boutonFantome: {
    marginTop: spacing.md,
    paddingVertical: spacing.md + 1,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(139,156,244,0.25)',
    borderRadius: radius.md + 1,
  },
  boutonFantomeTexte: { fontSize: 13, fontWeight: '600', color: colors.brand },
});
