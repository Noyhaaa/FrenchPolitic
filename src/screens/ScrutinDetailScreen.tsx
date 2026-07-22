import { useState } from 'react';
import {
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

import { colors, mono, radius, serif, spacing, typography } from '@/theme';
import {
  ErrorView,
  GroupVoteRow,
  Legend,
  LigneFracture,
  LoadingView,
  OfflineBanner,
  QuestionsAmendementCard,
  ResultBar,
  SectionCard,
  SourceGrid,
  StatusBadge,
} from '@/components';
import { useScrutin } from '@/hooks';
import { PositionGroupe, StatutScrutin } from '@/types';
import {
  detailObjetAmendement,
  estVoteAmendement,
  estVoteSousAmendement,
  formatDateLong,
  libelleScrutin,
  statutLabel,
} from '@/utils/format';
import type { RootStackParamList } from '@/navigation/types';

type DetailRoute = RouteProp<RootStackParamList, 'ScrutinDetail'>;

/** Sort d'un (sous-)amendement → libellé + couleur (jamais la couleur seule §8). */
const SORT_SOUS = {
  adopte: { label: 'Adopté', color: colors.adopte },
  rejete: { label: 'Rejeté', color: colors.contre },
  retire: { label: 'Retiré', color: colors.textTertiary },
} as const;

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
  // Typage stack natif : `push` permet d'empiler la fiche vote d'un
  // sous-amendement par-dessus celle de son amendement parent.
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const insets = useSafeAreaInsets();
  const { data: scrutin, loading, refreshing, offline, error, retry, refresh } =
    useScrutin(route.params.scrutinId);
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
  // Titre = type du vote en clair ; l'objet officiel complet (le sujet exact)
  // reste affiché dessous — rien n'est perdu, tout reste sourcé (§2.5).
  const lib = libelleScrutin(scrutin.objet);
  // Fiche d'un vote d'amendement : entrée par les « 4 questions » (le « qui
  // était pour / contre » y vit) — pas de section « Vote par groupe ».
  const estAmendement = estVoteAmendement(scrutin.objet);
  const estSous = estVoteSousAmendement(scrutin.objet);
  const quoi = estSous ? 'le sous-amendement' : "l'amendement";
  const totalVoix =
    resultat.pour + resultat.contre + resultat.abstention + resultat.nonVotants;
  // Fracture à montrer seulement si les groupes ne sont pas unanimes.
  const campsDistincts = new Set(
    scrutin.positionsGroupes.map((g) => g.positionMajoritaire),
  ).size;

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
        {/* Type du vote + statut + date, puis l'objet officiel complet */}
        <StatusBadge statut={scrutin.statut} />
        <Text style={[typography.title, styles.title]}>{lib.titre}</Text>
        {lib.titre !== scrutin.objet ? (
          <Text style={[typography.readingBody, styles.objetOfficiel]}>
            {scrutin.objet}
          </Text>
        ) : null}
        <Text style={[typography.meta, styles.subtitle]}>
          {['Assemblée nationale', formatDateLong(scrutin.date), lib.complement]
            .filter(Boolean)
            .join(' · ')}
        </Text>

        {/* Résultat global EN TÊTE (§2.2 : voir le résultat tout de suite) —
            sur toutes les fiches vote, quel que soit le type. Verdict, grille
            des décomptes, barre combinée + échelle. Tout est factuel :
            décomptes officiels. */}
        <SectionCard title="Résultat du vote" flat>
          <VerdictCard statut={scrutin.statut} resultat={resultat} />

          <View style={styles.tallyGrid}>
            <TallyItem label="Pour" value={resultat.pour} total={totalVoix} color={colors.pour} />
            <View style={styles.tallySep} />
            <TallyItem label="Contre" value={resultat.contre} total={totalVoix} color={colors.contre} />
            <View style={styles.tallySep} />
            <TallyItem label="Abstention" value={resultat.abstention} total={totalVoix} color={colors.abstention} />
          </View>

          <View style={styles.barBlock}>
            <ResultBar
              height={6}
              segments={[
                { value: resultat.pour, color: colors.pour },
                { value: resultat.abstention, color: colors.abstention },
                { value: resultat.contre, color: colors.contre },
                { value: resultat.nonVotants, color: colors.nonVotant },
              ]}
            />
            <View style={styles.barScale}>
              <Text style={styles.barScaleText}>0</Text>
              {resultat.nonVotants > 0 ? (
                <Text style={styles.barScaleText}>
                  {resultat.nonVotants} non-votant{resultat.nonVotants > 1 ? 's' : ''}
                </Text>
              ) : null}
              <Text style={styles.barScaleText}>{totalVoix}</Text>
            </View>
          </View>
        </SectionCard>

        {/* Entrée de compréhension d'un vote d'amendement : ses 4 questions
            (§2.2) — le « qui était pour / contre » y est rendu depuis les
            positions de groupes du scrutin. */}
        {estAmendement ? (
          <QuestionsAmendementCard
            questions={scrutin.questions}
            positionsGroupes={scrutin.positionsGroupes}
            scrutinPublic={scrutin.scrutinPublic}
            sous={estSous}
          />
        ) : null}

        {/* Contenu de l'amendement (open data AN) : ce qu'il change (factuel) et
            son exposé sommaire — le « pourquoi » côté AUTEUR, donc en bloc
            attribué (§4.3), jamais présenté comme neutre. Masqué si absent (§2.5).
            Fond carte (pas le fond de page) : même niveau visuel que le bloc
            « Ce que dit l'auteur ». */}
        {scrutin.dispositif ? (
          <SectionCard title={`Ce que ${quoi} change`}>
            {scrutin.cible ? (
              <View style={styles.ciblePill}>
                <Text style={typography.badge}>{scrutin.cible}</Text>
              </View>
            ) : null}
            <Text style={typography.readingBody}>{scrutin.dispositif}</Text>
          </SectionCard>
        ) : null}

        {scrutin.exposeSommaire ? (
          <View style={styles.exposeCard}>
            <Text style={[typography.overline, styles.exposeTitle]}>
              Ce que dit l'auteur {estSous ? 'du sous-amendement' : "de l'amendement"}
            </Text>
            <View style={styles.pill}>
              <Text style={styles.pillText}>👤 Point de vue de l'auteur</Text>
            </View>
            <Text style={typography.readingQuote}>
              « {scrutin.exposeSommaire} »
            </Text>
          </View>
        ) : null}

        {/* Vote par groupe — votes sur le TEXTE uniquement : sur la fiche d'un
            amendement, le « qui était pour / contre » vit dans la carte des
            4 questions. Scrutins publics seulement (§3.2, §5.2).
            Tap sur un groupe (si nominatif dispo) → noms des votants. */}
        {estAmendement ? null : scrutin.scrutinPublic ? (
          <SectionCard title="Vote par groupe" flat>
            {/* Ligne de fracture : qui s'est opposé à qui, en un coup d'œil.
                Position majoritaire de chaque groupe — factuel, sourcé par le
                scrutin (§5.2), jamais un jugement. */}
            {campsDistincts >= 2 ? (
              <View style={styles.fracture}>
                <LigneFracture positionsGroupes={scrutin.positionsGroupes} />
              </View>
            ) : null}
            <View style={{ gap: spacing.sm }}>
              {scrutin.positionsGroupes.map((g) => {
                const depliable = aDesNoms(g);
                const ouvert = ouverts.has(g.groupeId);
                return (
                  <View key={g.groupeId} style={styles.groupCard}>
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
            <Text style={typography.readingBody}>
              Ce vote s'est fait à main levée : il n'existe pas de ventilation
              par groupe ni par député. Seul le résultat global est disponible.
            </Text>
          </SectionCard>
        )}

        {/* Sous-amendements de cet amendement (le cas échéant) — liste compacte
            (connecteur ↳, même langage visuel que le dépliage de la fiche
            dossier), chaque ligne ouvre la fiche de son propre vote (§7.5). */}
        {scrutin.sousAmendements && scrutin.sousAmendements.length > 0 && (
          <SectionCard
            title={`Sous-amendements (${scrutin.sousAmendements.length})`}
          >
            <View style={styles.sousListe}>
              {scrutin.sousAmendements.map((sa) => {
                const s = SORT_SOUS[sa.sort];
                // Extrait factuel (partie descriptive de l'objet), jamais
                // reformulé — restitué tel quel si pas de découpe nette (§2.5).
                const texte = detailObjetAmendement(sa) || sa.objet;
                const contenu = (
                  <View style={styles.sousRow}>
                    <Text style={styles.connecteur} importantForAccessibility="no">
                      ↳
                    </Text>
                    <View
                      style={[styles.dotPetit, { backgroundColor: s.color }]}
                      importantForAccessibility="no"
                    />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.sousTexte} numberOfLines={2}>
                        {texte}
                      </Text>
                      <Text style={typography.meta}>
                        n° {sa.numero ?? '—'} · {s.label.toLowerCase()}
                      </Text>
                    </View>
                    {sa.scrutinId ? (
                      <Text style={styles.sousChevron} importantForAccessibility="no">
                        ›
                      </Text>
                    ) : null}
                  </View>
                );
                return sa.scrutinId ? (
                  <Pressable
                    key={sa.id}
                    onPress={() =>
                      navigation.push('ScrutinDetail', {
                        scrutinId: sa.scrutinId!,
                      })
                    }
                    style={({ pressed }) => pressed && { opacity: 0.7 }}
                    accessibilityRole="button"
                    accessibilityLabel={`${sa.objet}. ${s.label}. Voir le vote.`}
                  >
                    {contenu}
                  </Pressable>
                ) : (
                  <View key={sa.id}>{contenu}</View>
                );
              })}
            </View>
          </SectionCard>
        )}

        {/* Source officielle du scrutin (réversibilité §7.5) */}
        {scrutin.sources.length > 0 && (
          <View style={styles.flatSection}>
            <Text style={typography.overline}>Sources officielles</Text>
            <SourceGrid sources={scrutin.sources} />
          </View>
        )}
      </ScrollView>
    </View>
  );
}

/** Verdict du vote (prototype) : icône + statut en serif + écart de voix. */
function VerdictCard({
  statut,
  resultat,
}: {
  statut: StatutScrutin;
  resultat: { pour: number; contre: number };
}) {
  const ui: Record<StatutScrutin, { fg: string; bg: string; icon: string }> = {
    adopte: { fg: colors.adopte, bg: colors.adopteSoft, icon: '✓' },
    rejete: { fg: colors.rejete, bg: colors.rejeteSoft, icon: '✕' },
    en_cours: { fg: colors.enCours, bg: colors.enCoursSoft, icon: '◷' },
  };
  const { fg, bg, icon } = ui[statut];
  const ecart = Math.abs(resultat.pour - resultat.contre);
  return (
    <View
      style={[styles.verdict, { backgroundColor: bg, borderColor: fg }]}
      accessibilityRole="text"
      accessibilityLabel={`${statutLabel(statut)}, écart de ${ecart} voix.`}
    >
      <View style={[styles.verdictIconWrap, { backgroundColor: bg }]}>
        <Text style={[styles.verdictIcon, { color: fg }]}>{icon}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={[styles.verdictLabel, { color: fg }]}>
          {statutLabel(statut)}
        </Text>
        <Text style={typography.bodySecondary}>
          Écart de {ecart} voix entre pour et contre
        </Text>
      </View>
    </View>
  );
}

function TallyItem({
  label,
  value,
  total,
  color,
}: {
  label: string;
  value: number;
  total: number;
  color: string;
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <View style={styles.tallyItem}>
      <Text style={[styles.tallyValue, { color }]}>{value}</Text>
      <Text style={styles.tallyPct}>{pct}%</Text>
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
  objetOfficiel: {
    marginTop: -spacing.md,
  },
  verdict: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  verdictIconWrap: {
    width: 48,
    height: 48,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  verdictIcon: {
    fontSize: 24,
    fontWeight: '800',
  },
  verdictLabel: {
    fontSize: 22,
    lineHeight: 27,
    fontWeight: '800',
    fontFamily: serif,
  },
  tallyGrid: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  tallySep: {
    width: 1,
    backgroundColor: colors.border,
  },
  tallyItem: {
    flex: 1,
    alignItems: 'center',
    gap: 2,
    paddingVertical: spacing.lg,
  },
  tallyValue: {
    fontSize: 22,
    fontWeight: '800',
    fontFamily: mono,
  },
  tallyPct: {
    fontSize: 10,
    fontFamily: mono,
    color: colors.textTertiary,
  },
  barBlock: {
    marginTop: spacing.md,
    gap: spacing.xs,
  },
  barScale: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  barScaleText: {
    fontSize: 10,
    fontFamily: mono,
    color: colors.textTertiary,
  },
  groupCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
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
  fracture: {
    marginBottom: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  ciblePill: {
    alignSelf: 'flex-start',
    borderRadius: radius.pill,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
    backgroundColor: colors.surfaceMuted,
    marginBottom: spacing.sm,
  },
  exposeCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    // Accent ambre : contenu « point de vue », comme l'exposé des motifs.
    borderLeftWidth: 3,
    borderLeftColor: colors.accentWarm,
  },
  exposeTitle: {
    marginBottom: spacing.md,
  },
  pill: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accentWarmSoft,
    borderRadius: radius.pill,
    paddingVertical: 4,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  pillText: {
    ...typography.badge,
    color: colors.accentWarm,
  },
  sousListe: {
    gap: spacing.xs,
  },
  sousRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    paddingVertical: spacing.sm,
  },
  connecteur: {
    color: colors.textTertiary,
    fontFamily: mono,
    fontSize: 13,
    lineHeight: 22,
  },
  dotPetit: {
    width: 7,
    height: 7,
    borderRadius: 4,
    marginTop: 8,
  },
  sousTexte: {
    ...typography.readingBody,
    fontSize: 15,
    lineHeight: 21,
  },
  sousChevron: {
    color: colors.textTertiary,
    fontSize: 20,
    fontWeight: '600',
    marginTop: 4,
  },
});
