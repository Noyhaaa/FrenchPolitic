import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, radius, spacing, typography } from '@/theme';
import {
  ErrorView,
  GroupVoteRow,
  Legend,
  LoadingView,
  OfflineBanner,
  ResultBar,
  SectionCard,
  SourceGrid,
  StatusBadge,
} from '@/components';
import { useScrutin } from '@/hooks';
import { PositionGroupe } from '@/types';
import { formatDateLong } from '@/utils/format';
import type { RootStackParamList } from '@/navigation/types';

type DetailRoute = RouteProp<RootStackParamList, 'ScrutinDetail'>;

/** Un groupe a-t-il un détail nominatif à montrer ? (§5.2, absent = masqué §2.5) */
function aDesNoms(g: PositionGroupe): boolean {
  return Boolean(
    g.nomsPour?.length || g.nomsContre?.length || g.nomsAbstention?.length,
  );
}

/** Liste des votants d'une position (« CONTRE (10) : … »), si documentée. */
function NomsPosition({
  label,
  noms,
  color,
}: {
  label: string;
  noms?: string[];
  color: string;
}) {
  if (!noms || noms.length === 0) return null;
  return (
    <View style={styles.nomsBloc}>
      <Text style={[styles.nomsLabel, { color }]}>
        {label} ({noms.length})
      </Text>
      <Text style={styles.nomsListe}>{noms.join(' · ')}</Text>
    </View>
  );
}

/**
 * Détail d'un vote : résultat global, ventilation par groupe, et — pour les
 * scrutins publics quand la source le fournit — les noms des votants,
 * dépliables groupe par groupe (§5.2). Contenu 100 % factuel : pas d'AiNotice
 * ici, rien n'est généré.
 */
export function ScrutinDetailScreen() {
  const route = useRoute<DetailRoute>();
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const { data: scrutin, loading, offline, error, retry } = useScrutin(
    route.params.scrutinId,
  );
  const [ouverts, setOuverts] = useState<ReadonlySet<string>>(new Set());
  const goBack = () => navigation.goBack();

  const toggleGroupe = (groupeId: string) =>
    setOuverts((prev) => {
      const next = new Set(prev);
      if (next.has(groupeId)) next.delete(groupeId);
      else next.add(groupeId);
      return next;
    });

  const topBar = (
    <View style={styles.topBar}>
      <Pressable
        onPress={goBack}
        style={styles.roundBtn}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel="Retour au dossier"
      >
        <Text style={styles.roundBtnText}>‹</Text>
      </Pressable>
    </View>
  );

  if (loading && !scrutin) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        {topBar}
        <LoadingView label="Chargement du vote…" />
      </View>
    );
  }

  if (!scrutin) {
    const notFound = error === 'notfound';
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        {topBar}
        <ErrorView
          title={notFound ? 'Introuvable' : 'Oups'}
          message={
            notFound
              ? "Ce vote n'a pas été trouvé."
              : error === 'network'
                ? 'Impossible de joindre le serveur. Vérifiez votre connexion.'
                : 'Une erreur est survenue. Réessayez dans un instant.'
          }
          onRetry={notFound ? undefined : retry}
        />
      </View>
    );
  }

  const { resultat } = scrutin;

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
      >
        {/* Objet du vote + statut + date */}
        <StatusBadge statut={scrutin.statut} />
        <Text style={[typography.title, styles.title]}>{scrutin.objet}</Text>
        <Text style={[typography.meta, styles.subtitle]}>
          Assemblée nationale · {formatDateLong(scrutin.date)}
        </Text>

        {/* Résultat global : barre + décomptes */}
        <SectionCard title="Résultat du vote">
          <ResultBar
            height={12}
            segments={[
              { value: resultat.pour, color: colors.pour },
              { value: resultat.contre, color: colors.contre },
              { value: resultat.abstention, color: colors.abstention },
              { value: resultat.nonVotants, color: colors.nonVotant },
            ]}
          />
          <View style={styles.tally}>
            <TallyItem label="Pour" value={resultat.pour} color={colors.pour} align="flex-start" />
            <TallyItem label="Contre" value={resultat.contre} color={colors.contre} align="center" />
            <TallyItem label="Abstention" value={resultat.abstention} color={colors.textSecondary} align="flex-end" />
          </View>
        </SectionCard>

        {/* Vote par groupe — scrutins publics uniquement (§3.2, §5.2).
            Tap sur un groupe (si nominatif dispo) → noms des votants. */}
        {scrutin.scrutinPublic ? (
          <SectionCard title="Vote par groupe">
            <View style={{ gap: spacing.lg }}>
              {scrutin.positionsGroupes.map((g) => {
                const depliable = aDesNoms(g);
                const ouvert = ouverts.has(g.groupeId);
                return (
                  <View key={g.groupeId}>
                    {depliable ? (
                      <Pressable
                        onPress={() => toggleGroupe(g.groupeId)}
                        accessibilityRole="button"
                        accessibilityLabel={`${g.groupeNom} : ${
                          ouvert ? 'masquer' : 'afficher'
                        } le détail des votants`}
                      >
                        <GroupVoteRow groupe={g} />
                        <Text style={styles.deplieHint}>
                          {ouvert ? 'Masquer les votants ▲' : 'Voir les votants ▼'}
                        </Text>
                      </Pressable>
                    ) : (
                      <GroupVoteRow groupe={g} />
                    )}
                    {depliable && ouvert ? (
                      <View style={styles.nomsWrap}>
                        <NomsPosition label="POUR" noms={g.nomsPour} color={colors.pour} />
                        <NomsPosition label="CONTRE" noms={g.nomsContre} color={colors.contre} />
                        <NomsPosition label="ABSTENTION" noms={g.nomsAbstention} color={colors.textSecondary} />
                      </View>
                    ) : null}
                  </View>
                );
              })}
            </View>
            <View style={styles.legend}>
              <Legend
                items={[
                  { label: 'Pour', color: colors.pour },
                  { label: 'Contre', color: colors.contre },
                  { label: 'Abstention', color: colors.abstention },
                ]}
              />
            </View>
            {/* Nominatif absent partout → on l'explique, sans combler (§2.5). */}
            {!scrutin.positionsGroupes.some(aDesNoms) && (
              <Text style={[typography.meta, styles.nominatifAbsent]}>
                Le détail nominatif des votants n'est pas disponible pour ce
                vote.
              </Text>
            )}
          </SectionCard>
        ) : (
          <SectionCard title="Vote par groupe">
            <Text style={typography.bodySecondary}>
              Ce vote s'est fait à main levée : il n'existe pas de ventilation
              par groupe ni par député. Seul le résultat global est disponible.
            </Text>
          </SectionCard>
        )}

        {/* Source officielle du scrutin (réversibilité §7.5) */}
        {scrutin.sources.length > 0 && (
          <View style={styles.flatSection}>
            <Text style={typography.sectionTitle}>Sources officielles</Text>
            <SourceGrid sources={scrutin.sources} />
          </View>
        )}
      </ScrollView>
    </View>
  );
}

function TallyItem({
  label,
  value,
  color,
  align,
}: {
  label: string;
  value: number;
  color: string;
  align: 'flex-start' | 'center' | 'flex-end';
}) {
  return (
    <View style={[styles.tallyItem, { alignItems: align }]}>
      <Text style={[styles.tallyValue, { color }]}>{value}</Text>
      <Text style={typography.meta}>{label}</Text>
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
    fontSize: 22,
    lineHeight: 24,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  scroll: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    gap: spacing.lg,
  },
  title: {
    marginTop: -spacing.sm,
    fontSize: 20,
    lineHeight: 26,
  },
  subtitle: {
    marginTop: -spacing.md,
  },
  tally: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.md,
  },
  tallyItem: {
    flex: 1,
    gap: 2,
  },
  tallyValue: {
    fontSize: 22,
    fontWeight: '800',
  },
  deplieHint: {
    ...typography.meta,
    color: colors.brand,
    marginTop: spacing.xs,
  },
  nomsWrap: {
    marginTop: spacing.sm,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.lg,
    padding: spacing.md,
    gap: spacing.md,
  },
  nomsBloc: {
    gap: 2,
  },
  nomsLabel: {
    ...typography.overline,
  },
  nomsListe: {
    ...typography.meta,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  legend: {
    marginTop: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  nominatifAbsent: {
    marginTop: spacing.md,
    fontStyle: 'italic',
  },
  flatSection: {
    gap: spacing.md,
  },
});
