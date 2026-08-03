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
  VoteDisputeTile,
} from '@/components';
import { themeEmoji } from '@/constants/themes';
import { useAccueil, useRecap } from '@/hooks';
import { useProfil } from '@/session/ProfilContext';
import { DossierListItem, SectionTheme, ThemeScrutin, VoteDisputeItem } from '@/types';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/**
 * Remonte les rangées des thèmes suivis, sans en retirer aucune.
 *
 * ⚠️ Le choix d'un lecteur **ordonne**, il ne filtre pas : masquer un texte
 * parce qu'il n'est pas dans ses thèmes reviendrait à lui cacher un vote qui a
 * bien eu lieu (§2.5). L'ordre relatif des rangées non choisies est celui de
 * l'API, inchangé — un tri stable, pour que deux lancements donnent le même fil.
 */
export function ordonnerSections(
  sections: SectionTheme[],
  themesSuivis: ThemeScrutin[],
): SectionTheme[] {
  if (themesSuivis.length === 0) return sections;
  const suivis = new Set<string>(themesSuivis);
  const enTete = sections.filter((s) => suivis.has(s.theme));
  const ensuite = sections.filter((s) => !suivis.has(s.theme));
  return [...enTete, ...ensuite];
}

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

/**
 * Rangée « Les votes les plus disputés » (§2.2 : voir où le Parlement s'est
 * divisé). L'ordre vient du backend, calculé sur les seuls décomptes officiels
 * — le sous-titre le dit, pour qu'aucun lecteur ne prenne le classement pour un
 * jugement sur les mesures (§4.3). Rangée vide → masquée (§2.5).
 */
function VotesDisputesRow({
  votes,
  onPress,
}: {
  votes: VoteDisputeItem[];
  onPress: (v: VoteDisputeItem) => void;
}) {
  if (votes.length === 0) return null;
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text style={typography.sectionTitle}>Les votes les plus disputés</Text>
      </View>
      <Text style={[typography.meta, styles.sectionSousTitre]}>
        Classés par l'écart de voix, l'abstention et la division des groupes.
      </Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.rail}
      >
        {votes.map((v) => (
          <VoteDisputeTile key={v.scrutinId} vote={v} onPress={onPress} />
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
  const { preferences } = useProfil();

  const onPressDossier = useCallback(
    (dossier: DossierListItem) =>
      navigation.navigate('DossierDetail', { dossierId: dossier.id }),
    [navigation],
  );

  // Un vote disputé ouvre sa fiche vote : c'est là que vivent la ventilation
  // par groupe et le nominatif qui expliquent la division.
  const onPressVoteDispute = useCallback(
    (vote: VoteDisputeItem) =>
      navigation.navigate('ScrutinDetail', { scrutinId: vote.scrutinId }),
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
  const sections = accueil
    ? ordonnerSections(accueil.sections, preferences.themes)
    : [];
  // Une rangée choisie est-elle effectivement remontée ? Sinon on n'annonce
  // rien : la mention doit décrire ce qui est à l'écran, pas l'intention.
  const themesRemontes =
    preferences.themes.length > 0 &&
    sections.some((s) => preferences.themes.includes(s.theme));

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

            <VotesDisputesRow
              votes={accueil.votesDisputes ?? []}
              onPress={onPressVoteDispute}
            />

            {recap ? (
              <View style={styles.recapWrap}>
                <RecapVotes recap={recap} />
              </View>
            ) : null}

            {/* Dit ce qui vient d'être fait à l'ordre des rangées : sans cette
                ligne, le lecteur prendrait cet ordre pour celui de la source. */}
            {themesRemontes ? (
              <Text style={styles.mentionOrdre}>Vos thèmes en premier</Text>
            ) : null}

            {sections.map((section) => (
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
  mentionOrdre: {
    ...typography.overline,
    color: colors.brand,
    paddingHorizontal: spacing.lg,
    marginBottom: -spacing.md,
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
  // Dit sur quoi porte le classement : sans cette ligne, « disputés » se lirait
  // comme un jugement de l'app plutôt que comme une lecture des décomptes.
  sectionSousTitre: {
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
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
