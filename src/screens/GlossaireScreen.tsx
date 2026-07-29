import { useMemo, useState } from 'react';
import {
  Pressable,
  ScrollView,
  SectionList,
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
import { EmptyView, IconLigne } from '@/components';
import { GLOSSAIRE, motDuJour, sectionsGlossaire } from '@/constants/glossaire';
import { LIBELLES_CATEGORIE } from '@/types/glossaire';
import type { CategorieTerme, TermeGlossaire } from '@/types/glossaire';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

const CATEGORIES = Object.keys(LIBELLES_CATEGORIE) as CategorieTerme[];

/** Enlève accents et casse pour une recherche tolérante. */
function normalise(valeur: string) {
  return valeur
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

/**
 * Glossaire — l'index (§3.3).
 *
 * Le jargon parlementaire est le premier mur devant un texte de loi : cet écran
 * le fait tomber. Un mot du jour en tête (déterministe, il change à minuit),
 * des familles en filtre, puis les termes groupés par lettre — chacun avec sa
 * définition courte, pour qu'on comprenne sans même ouvrir la fiche.
 */
export function GlossaireScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const [query, setQuery] = useState('');
  const [categorie, setCategorie] = useState<CategorieTerme | undefined>();

  const vedette = useMemo(() => motDuJour(), []);

  const sections = useMemo(() => {
    const recherche = normalise(query.trim());
    const filtres = GLOSSAIRE.filter((terme) => {
      if (categorie && terme.categorie !== categorie) return false;
      if (!recherche) return true;
      return (
        normalise(terme.libelle).includes(recherche) ||
        normalise(terme.definition).includes(recherche)
      );
    });
    return sectionsGlossaire(filtres);
  }, [query, categorie]);

  const compte = useMemo(
    () =>
      CATEGORIES.reduce<Record<string, number>>((acc, cle) => {
        acc[cle] = GLOSSAIRE.filter((t) => t.categorie === cle).length;
        return acc;
      }, {}),
    [],
  );

  const ouvrir = (terme: TermeGlossaire) =>
    navigation.navigate('GlossaireTerme', { termeId: terme.id });

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <SectionList
        sections={sections}
        keyExtractor={(terme) => terme.id}
        contentContainerStyle={[
          styles.liste,
          { paddingBottom: insets.bottom + spacing.xxxl },
        ]}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        stickySectionHeadersEnabled={false}
        ListHeaderComponent={
          <View>
            <Pressable
              onPress={navigation.goBack}
              style={styles.retour}
              accessibilityRole="button"
              accessibilityLabel="Revenir à Explorer"
              hitSlop={8}
            >
              <IconLigne
                name="chevronGauche"
                color={colors.textSecondary}
                size={20}
                strokeWidth={2}
              />
              <Text style={styles.retourTexte}>Explorer</Text>
            </Pressable>

            <Text style={styles.eyebrow}>Décrypté · Glossaire</Text>
            <Text style={styles.titre}>Le glossaire</Text>
            <Text style={styles.chapeau}>
              {GLOSSAIRE.length} mots du Parlement, traduits en français clair.
            </Text>

            <View style={styles.searchBox}>
              <IconLigne name="loupe" color={colors.brand} size={18} strokeWidth={2} />
              <TextInput
                value={query}
                onChangeText={setQuery}
                placeholder="Chercher un terme…"
                placeholderTextColor={colors.textTertiary}
                style={styles.input}
                returnKeyType="search"
                autoCorrect={false}
                clearButtonMode="while-editing"
                accessibilityLabel="Chercher un terme du glossaire"
              />
            </View>

            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.chips}
            >
              <Pressable
                onPress={() => setCategorie(undefined)}
                style={[styles.chip, !categorie && styles.chipActif]}
                accessibilityRole="button"
                accessibilityState={{ selected: !categorie }}
              >
                <Text style={[styles.chipTexte, !categorie && styles.chipTexteActif]}>
                  Tous · {GLOSSAIRE.length}
                </Text>
              </Pressable>
              {CATEGORIES.map((cle) => {
                const actif = categorie === cle;
                return (
                  <Pressable
                    key={cle}
                    onPress={() => setCategorie(actif ? undefined : cle)}
                    style={[styles.chip, actif && styles.chipActif]}
                    accessibilityRole="button"
                    accessibilityState={{ selected: actif }}
                  >
                    <Text style={[styles.chipTexte, actif && styles.chipTexteActif]}>
                      {LIBELLES_CATEGORIE[cle]}
                      {compte[cle] ? ' · ' + compte[cle] : ''}
                    </Text>
                  </Pressable>
                );
              })}
            </ScrollView>

            {!query.trim() && !categorie ? (
              <Pressable
                onPress={() => ouvrir(vedette)}
                style={styles.vedetteWrap}
                accessibilityRole="button"
                accessibilityLabel={'Mot du jour : ' + vedette.libelle}
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
                    <Text style={styles.vedetteEyebrow}>Le mot du jour</Text>
                  </View>
                  <View style={styles.vedetteTitreLigne}>
                    <Text style={styles.vedetteTitre}>{vedette.libelle}</Text>
                    {vedette.nature ? (
                      <Text style={styles.vedetteNature}>
                        {vedette.nature} · {LIBELLES_CATEGORIE[vedette.categorie]}
                      </Text>
                    ) : null}
                  </View>
                  <Text style={styles.vedetteDefinition}>{vedette.definition}</Text>
                  <View style={styles.vedettePied}>
                    <Text style={styles.vedettePiedMeta}>
                      {vedette.etapes
                        ? vedette.etapes.length + ' étapes expliquées'
                        : LIBELLES_CATEGORIE[vedette.categorie]}
                    </Text>
                    <Text style={styles.vedettePiedLien}>Lire la fiche →</Text>
                  </View>
                </LinearGradient>
              </Pressable>
            ) : null}
          </View>
        }
        renderSectionHeader={({ section }) => (
          <View style={styles.lettreLigne}>
            <Text style={styles.lettre}>{section.lettre}</Text>
            <View style={styles.lettreFilet} />
            <Text style={styles.lettreCompte}>
              {section.data.length} TERME{section.data.length > 1 ? 'S' : ''}
            </Text>
          </View>
        )}
        renderItem={({ item, index, section }) => (
          <Pressable
            onPress={() => ouvrir(item)}
            accessibilityRole="button"
            accessibilityLabel={item.libelle + '. ' + item.definition}
            style={[
              styles.carteTerme,
              index === 0 && styles.carteHaut,
              index === section.data.length - 1 && styles.carteBas,
            ]}
          >
            {index > 0 ? <View style={styles.filet} /> : null}
            <View style={styles.terme}>
              <View style={styles.termeTexte}>
                <View style={styles.termeTitreLigne}>
                  <Text style={styles.termeTitre}>{item.libelle}</Text>
                  <Text style={styles.termeCategorie}>
                    {LIBELLES_CATEGORIE[item.categorie]}
                  </Text>
                </View>
                <Text style={styles.termeDefinition} numberOfLines={2}>
                  {item.definition}
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
        )}
        ListEmptyComponent={
          <EmptyView
            title="Aucun terme"
            subtitle="Essayez un autre mot, ou retirez le filtre."
          />
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  liste: { paddingHorizontal: spacing.xl, flexGrow: 1 },
  retour: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm + 2,
    paddingTop: spacing.md,
    paddingBottom: spacing.lg - 2,
  },
  retourTexte: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
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
  chapeau: { ...typography.bodySecondary, marginTop: spacing.xs + 2, maxWidth: 300 },
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
  chips: { gap: spacing.sm, paddingVertical: spacing.md - 1 },
  chip: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg - 2,
  },
  chipActif: {
    backgroundColor: colors.brandSoft,
    borderColor: 'rgba(139,156,244,0.32)',
  },
  chipTexte: { fontSize: 12.5, fontWeight: '600', color: 'rgba(255,255,255,0.72)' },
  chipTexteActif: { color: colors.splashLigneSoft },
  vedetteWrap: {
    marginTop: spacing.xs,
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
  vedetteTitreLigne: {
    flexDirection: 'row',
    alignItems: 'baseline',
    flexWrap: 'wrap',
    gap: spacing.sm + 2,
  },
  vedetteTitre: {
    fontFamily: serifDisplay,
    fontSize: 27,
    lineHeight: 31,
    letterSpacing: -0.5,
    color: colors.textPrimary,
  },
  vedetteNature: {
    fontFamily: mono,
    fontSize: 10.5,
    fontWeight: '500',
    letterSpacing: 0.4,
    textTransform: 'uppercase',
    color: colors.textTertiary,
  },
  vedetteDefinition: {
    ...typography.body,
    fontSize: 13.5,
    lineHeight: 20,
    color: 'rgba(255,255,255,0.65)',
    marginTop: spacing.sm,
  },
  vedettePied: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.lg - 2,
    paddingTop: spacing.md + 1,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.09)',
  },
  vedettePiedMeta: { fontSize: 11.5, fontWeight: '500', color: colors.miniLabel },
  vedettePiedLien: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.splashLigneSoft,
  },
  lettreLigne: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md - 1,
    marginTop: spacing.lg + 2,
    marginBottom: spacing.sm + 2,
  },
  lettre: {
    fontFamily: serifDisplay,
    fontSize: 19,
    color: colors.textPrimary,
  },
  lettreFilet: {
    flex: 1,
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.11)',
  },
  lettreCompte: {
    fontFamily: mono,
    fontSize: 10.5,
    fontWeight: '500',
    letterSpacing: 0.5,
    color: colors.textTertiary,
  },
  carteTerme: {
    backgroundColor: colors.surface,
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderColor: colors.border,
  },
  carteHaut: {
    borderTopWidth: 1,
    borderTopLeftRadius: radius.xl - 2,
    borderTopRightRadius: radius.xl - 2,
  },
  carteBas: {
    borderBottomWidth: 1,
    borderBottomLeftRadius: radius.xl - 2,
    borderBottomRightRadius: radius.xl - 2,
  },
  filet: {
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.06)',
    marginHorizontal: spacing.lg,
  },
  terme: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
    paddingVertical: spacing.md + 3,
    paddingHorizontal: spacing.lg,
  },
  termeTexte: { flex: 1 },
  termeTitreLigne: {
    flexDirection: 'row',
    alignItems: 'baseline',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  termeTitre: {
    fontFamily: serifDisplaySemi,
    fontSize: 17,
    lineHeight: 21,
    letterSpacing: -0.2,
    color: colors.textPrimary,
  },
  termeCategorie: {
    fontFamily: mono,
    fontSize: 9.5,
    fontWeight: '500',
    letterSpacing: 0.4,
    textTransform: 'uppercase',
    color: colors.textTertiary,
  },
  termeDefinition: {
    ...typography.bodySecondary,
    fontSize: 12.5,
    lineHeight: 17,
    marginTop: spacing.xs,
  },
});
