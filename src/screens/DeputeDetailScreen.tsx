import { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, radius, spacing, typography } from '@/theme';
import {
  Avatar,
  ErrorView,
  LoadingView,
  OfflineBanner,
  PortraitVoteCard,
  VoteHistoryFil,
} from '@/components';
import { useDepute } from '@/hooks';
import type { ObjetVote, VoteDepute } from '@/types';
import { formatDateLong } from '@/utils/format';
import type { RootStackParamList } from '@/navigation/types';

type DetailRoute = RouteProp<RootStackParamList, 'DeputeDetail'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

/** Filtres de l'historique — `undefined` = tous les votes. */
const FILTRES: ReadonlyArray<{ cle: ObjetVote | 'tous'; label: string }> = [
  { cle: 'tous', label: 'Tous' },
  { cle: 'dossier', label: 'Dossiers' },
  { cle: 'amendement', label: 'Amendements' },
  { cle: 'sous_amendement', label: 'Sous-amend.' },
];

/**
 * Fiche d'un député : identité, portrait de vote chiffré et historique de ses
 * votes en fil. Tout provient des scrutins publics (§5.2) ; rien n'est agrégé
 * en jugement (§7.4) et une donnée absente est masquée, pas comblée (§2.5).
 */
export function DeputeDetailScreen() {
  const route = useRoute<DetailRoute>();
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const [filtre, setFiltre] = useState<ObjetVote | 'tous'>('tous');
  const {
    data: depute,
    loading,
    refreshing,
    offline,
    error,
    retry,
    refresh,
    chargerPlus,
    chargeantPlus,
    finHistorique,
  } = useDepute(route.params.deputeId);

  const historique = useMemo(
    () =>
      filtre === 'tous'
        ? (depute?.historique ?? [])
        : (depute?.historique ?? []).filter((v) => v.objetType === filtre),
    [depute, filtre],
  );

  const ouvrirDossier = (vote: VoteDepute) => {
    if (vote.dossierId) {
      navigation.navigate('DossierDetail', { dossierId: vote.dossierId });
    }
  };

  const topBar = (
    <View style={styles.topBar}>
      <Pressable
        onPress={() => navigation.goBack()}
        style={styles.roundBtn}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel="Retour à l'annuaire"
      >
        <Text style={styles.roundBtnText}>‹</Text>
      </Pressable>
    </View>
  );

  if (loading && !depute) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        {topBar}
        <LoadingView label="Chargement de la fiche…" />
      </View>
    );
  }

  if (!depute) {
    const notFound = error === 'notfound';
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        {topBar}
        <ErrorView
          title={notFound ? 'Introuvable' : 'Oups'}
          message={
            notFound
              ? "Ce député n'a pas été trouvé."
              : error === 'network'
                ? 'Impossible de joindre le serveur. Vérifiez votre connexion.'
                : 'Une erreur est survenue. Réessayez dans un instant.'
          }
          onRetry={notFound ? undefined : retry}
        />
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {topBar}
      {offline ? <OfflineBanner /> : null}

      <ScrollView
        contentContainerStyle={[
          styles.scroll,
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
      >
        {/* 1. Identité */}
        <View style={styles.profil}>
          <Avatar
            nom={depute.nom}
            portraitUrl={depute.portraitUrl}
            groupeCouleur={depute.groupeCouleur}
            taille={66}
          />
          <View style={styles.identite}>
            <Text style={typography.title}>{depute.nom}</Text>
            <View
              style={[
                styles.badgeGroupe,
                { borderColor: depute.groupeCouleur },
              ]}
            >
              <View
                style={[
                  styles.badgePastille,
                  { backgroundColor: depute.groupeCouleur },
                ]}
                importantForAccessibility="no"
              />
              <Text style={styles.badgeTexte}>{depute.groupeNom}</Text>
            </View>
            {/* Circonscription et début de mandat : masqués si non documentés. */}
            <Text style={typography.meta}>
              {[
                depute.circonscription,
                depute.depuis ? `depuis le ${formatDateLong(depute.depuis)}` : null,
              ]
                .filter(Boolean)
                .join(' · ')}
            </Text>
          </View>
        </View>

        {/* 2. Portrait de vote chiffré */}
        <PortraitVoteCard portrait={depute.portrait} />

        {/* 3. Historique, filtrable par nature de vote */}
        <View style={styles.section}>
          <Text style={typography.overline}>Historique de vote</Text>
          <View style={styles.filtres}>
            {FILTRES.map((f) => (
              <Pressable
                key={f.cle}
                onPress={() => setFiltre(f.cle)}
                style={[styles.chip, filtre === f.cle && styles.chipActif]}
                accessibilityRole="button"
                accessibilityState={{ selected: filtre === f.cle }}
              >
                <Text
                  style={[
                    styles.chipTexte,
                    filtre === f.cle && styles.chipTexteActif,
                  ]}
                >
                  {f.label}
                </Text>
              </Pressable>
            ))}
          </View>

          {historique.length > 0 ? (
            <VoteHistoryFil votes={historique} onOpen={ouvrirDossier} />
          ) : (
            <Text style={styles.vide}>
              Aucun vote de ce type dans l'historique chargé.
            </Text>
          )}
        </View>

        {/* 4. Pagination — l'API sert l'historique par pages. */}
        {!finHistorique ? (
          <Pressable
            onPress={chargerPlus}
            disabled={chargeantPlus}
            style={styles.plus}
            accessibilityRole="button"
            accessibilityLabel="Charger les votes plus anciens"
          >
            {chargeantPlus ? (
              <ActivityIndicator size="small" color={colors.brand} />
            ) : (
              <Text style={styles.plusTexte}>Charger les votes plus anciens</Text>
            )}
          </Pressable>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  roundBtn: {
    width: 34,
    height: 34,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  roundBtnText: {
    color: colors.textPrimary,
    fontSize: 22,
    lineHeight: 26,
  },
  scroll: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    gap: spacing.xl,
  },
  profil: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.lg,
  },
  identite: {
    flex: 1,
    gap: spacing.sm,
  },
  badgeGroupe: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 6,
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingVertical: 3,
    paddingHorizontal: spacing.sm,
  },
  badgePastille: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  badgeTexte: {
    // Nom de groupe complet : `label` (et non `badge`, qui passe en capitales)
    // pour rester lisible sur les intitulés longs.
    ...typography.label,
    color: colors.textSecondary,
  },
  section: {
    gap: spacing.md,
  },
  filtres: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
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
  vide: {
    ...typography.bodySecondary,
  },
  plus: {
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  plusTexte: {
    ...typography.label,
    color: colors.brand,
  },
});
