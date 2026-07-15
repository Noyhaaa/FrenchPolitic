import {
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, radius, spacing, typography } from '@/theme';
import {
  AiNotice,
  ErrorView,
  LoadingView,
  OfflineBanner,
  SectionCard,
  SourceGrid,
  StatusBadge,
} from '@/components';
import { useDossier } from '@/hooks';
import {
  formatDateLong,
  formatMicroResultat,
  formatTempsLecture,
  statutLabel,
} from '@/utils/format';
import type { RootStackParamList } from '@/navigation/types';

type DetailRoute = RouteProp<RootStackParamList, 'DossierDetail'>;

/** Emoji des publics concernés (maquette « Qui est concerné ? »). */
const publicEmoji: Record<string, string> = {
  Particuliers: '👥',
  Entreprises: '🏢',
  Collectivités: '🏛️',
  Associations: '🤝',
};

/** Petit intitulé de sous-bloc (CONTEXTE, OBJECTIF…). */
function MiniLabel({ children, color }: { children: string; color?: string }) {
  return (
    <Text style={[styles.miniLabel, color ? { color } : null]}>{children}</Text>
  );
}

/** Barre supérieure minimale (états chargement / erreur). */
function MinimalBar({ onBack }: { onBack: () => void }) {
  return (
    <View style={styles.topBar}>
      <Pressable
        onPress={onBack}
        style={styles.roundBtn}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel="Retour"
      >
        <Text style={styles.roundBtnText}>‹</Text>
      </Pressable>
    </View>
  );
}

export function DossierDetailScreen() {
  const route = useRoute<DetailRoute>();
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const { data: dossier, loading, offline, error, retry } = useDossier(
    route.params.dossierId,
  );
  const goBack = () => navigation.goBack();

  if (loading && !dossier) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <MinimalBar onBack={goBack} />
        <LoadingView label="Chargement du dossier…" />
      </View>
    );
  }

  if (!dossier) {
    const notFound = error === 'notfound';
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <MinimalBar onBack={goBack} />
        <ErrorView
          title={notFound ? 'Introuvable' : 'Oups'}
          message={
            notFound
              ? "Ce dossier n'a pas été trouvé."
              : error === 'network'
                ? 'Impossible de joindre le serveur. Vérifiez votre connexion.'
                : 'Une erreur est survenue. Réessayez dans un instant.'
          }
          onRetry={notFound ? undefined : retry}
        />
      </View>
    );
  }

  const { resume } = dossier;
  const badge = dossier.phase ?? { label: undefined, statut: dossier.statut };
  const pourquoi = [
    resume.contexte && (['CONTEXTE', resume.contexte] as const),
    resume.objectif && (['OBJECTIF', resume.objectif] as const),
    resume.historique && (['HISTORIQUE', resume.historique] as const),
  ].filter(Boolean) as ReadonlyArray<readonly [string, string]>;

  const onShare = () =>
    Share.share({
      message: `${resume.titreClair} — Décrypté`,
    });

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Barre supérieure : retour · temps de lecture · partage */}
      <View style={styles.topBar}>
        <Pressable
          onPress={() => navigation.goBack()}
          style={styles.roundBtn}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel="Retour"
        >
          <Text style={styles.roundBtnText}>‹</Text>
        </Pressable>
        <Text style={typography.meta}>
          {formatTempsLecture(dossier.tempsLectureSec)}
        </Text>
        <Pressable
          onPress={onShare}
          style={styles.roundBtn}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel="Partager ce dossier"
        >
          <Text style={styles.roundBtnShare}>↗</Text>
        </Pressable>
      </View>

      {offline ? <OfflineBanner /> : null}

      <ScrollView
        contentContainerStyle={[
          styles.scroll,
          { paddingBottom: insets.bottom + 104 },
        ]}
        showsVerticalScrollIndicator={false}
      >
        {/* 1. Statut (phase de navette si dispo) + titre + date */}
        <StatusBadge statut={badge.statut} label={badge.label} />
        <Text style={[typography.title, styles.title]}>{resume.titreClair}</Text>
        <Text style={[typography.meta, styles.subtitle]}>
          Assemblée nationale · {formatDateLong(dossier.dateDernierScrutin)}
        </Text>

        {/* Badge « mis à jour » (§7.7) : le dossier a évolué depuis une
            consultation précédente (nouveau scrutin rattaché). */}
        {dossier.miseAJour ? (
          <View style={styles.updateBanner}>
            <Text style={styles.updateBannerText}>
              🔄 {dossier.miseAJour.label} · {formatDateLong(dossier.miseAJour.date)}
            </Text>
          </View>
        ) : null}

        {/* 2. Résumé neutre (pill « Résumé IA · neutre » comme la maquette).
            Si le résumé n'est pas encore généré, on ne comble pas (§2.5) :
            placeholder explicite renvoyant vers les sources officielles. */}
        <SectionCard>
          <View style={styles.resumePill}>
            <Text style={styles.resumePillText}>✦ Résumé IA · neutre</Text>
          </View>
          {resume.resume.length > 0 ? (
            resume.resume.map((p, i) => (
              <Text
                key={i}
                style={[
                  typography.body,
                  i < resume.resume.length - 1 && styles.resumeGap,
                ]}
              >
                {p.phrase}
              </Text>
            ))
          ) : (
            <Text style={[typography.bodySecondary, styles.resumePending]}>
              Résumé en préparation. En attendant, les votes du dossier et les
              sources officielles ci-dessous sont disponibles.
            </Text>
          )}
        </SectionCard>

        {/* 3. Pourquoi ce texte ? */}
        {pourquoi.length > 0 && (
          <SectionCard title="Pourquoi ce texte ?">
            <View style={{ gap: spacing.md }}>
              {pourquoi.map(([label, value]) => (
                <View key={label}>
                  <MiniLabel>{label}</MiniLabel>
                  <Text style={typography.bodySecondary}>{value}</Text>
                </View>
              ))}
            </View>
          </SectionCard>
        )}

        {/* 4. Ce qui change — titre hors carte, AVANT gris / APRÈS bleu (§4.5) */}
        {resume.changement && (
          <View style={styles.flatSection}>
            <Text style={typography.sectionTitle}>Ce qui change</Text>
            <View style={styles.changeRow}>
              <View style={[styles.changeCol, styles.changeAvant]}>
                <Text style={styles.avantLabel}>AVANT</Text>
                <Text style={typography.bodySecondary}>
                  {resume.changement.avant}
                </Text>
              </View>
              <View style={[styles.changeCol, styles.changeApres]}>
                <Text style={styles.apresLabel}>APRÈS</Text>
                <Text style={styles.apresText}>{resume.changement.apres}</Text>
              </View>
            </View>
          </View>
        )}

        {/* 5. Qui est concerné ? (masqué si non documenté — §3.2 point 6) */}
        {resume.publicConcerne.length > 0 && (
          <SectionCard title="Qui est concerné ?">
            <View style={styles.chips}>
              {resume.publicConcerne.map((p) => (
                <View key={p} style={styles.chip}>
                  <Text style={styles.chipEmoji}>{publicEmoji[p] ?? '👥'}</Text>
                  <Text style={typography.label}>{p}</Text>
                </View>
              ))}
            </View>
          </SectionCard>
        )}

        {/* 6. Les votes du dossier — liste compacte : une ligne par scrutin
            (objet + statut + micro-résultat), le détail (groupes, nominatif)
            se charge au tap (écran ScrutinDetail). Lisible même sur un texte
            avec beaucoup de votes. */}
        <SectionCard
          title={
            dossier.scrutins.length > 1
              ? `Les votes (${dossier.scrutins.length})`
              : 'Le vote'
          }
        >
          {dossier.scrutins.map((s, i) => (
            <Pressable
              key={s.id}
              onPress={() => navigation.navigate('ScrutinDetail', { scrutinId: s.id })}
              style={({ pressed }) => [
                styles.voteRow,
                i > 0 && styles.voteRowBorder,
                pressed && { opacity: 0.7 },
              ]}
              accessibilityRole="button"
              accessibilityLabel={`${s.objet}. ${statutLabel(s.statut)}, ${
                s.resultat.pour
              } pour, ${s.resultat.contre} contre. Voir le détail du vote.`}
            >
              <View style={styles.voteInfo}>
                <Text style={styles.voteObjet} numberOfLines={2}>
                  {s.objet}
                </Text>
                <View style={styles.voteMeta}>
                  <StatusBadge statut={s.statut} />
                  <Text style={typography.meta}>{formatDateLong(s.date)}</Text>
                </View>
                <Text style={typography.meta}>
                  {formatMicroResultat(s.resultat.pour, s.resultat.contre)}
                </Text>
              </View>
              <Text style={styles.voteChevron} importantForAccessibility="no">
                ›
              </Text>
            </Pressable>
          ))}
        </SectionCard>

        {/* 7. Amendements clés — bordure latérale colorée (maquette).
            Vide en V1 (nécessite les données de dossier — Phase 2). */}
        {dossier.amendements.length > 0 && (
          <SectionCard title="Amendements clés">
            <View style={{ gap: spacing.lg }}>
              {dossier.amendements.map((a) => (
                <View
                  key={a.id}
                  style={[
                    styles.amendement,
                    { borderLeftColor: amendementColor(a.sort) },
                  ]}
                >
                  <Text style={styles.amendementObjet}>{a.objet}</Text>
                  <View style={styles.amendementMeta}>
                    {a.auteur ? (
                      <Text style={typography.meta}>{a.auteur}</Text>
                    ) : null}
                    <AmendementSort sort={a.sort} />
                  </View>
                </View>
              ))}
            </View>
          </SectionCard>
        )}

        {/* 8. Sources officielles — titre hors carte, chips blanches (maquette) */}
        <View style={styles.flatSection}>
          <Text style={typography.sectionTitle}>Sources officielles</Text>
          <SourceGrid sources={dossier.sources} />
        </View>

        {/* Transparence IA + signalement */}
        <AiNotice
          confiance={resume.confiance}
          reluParHumain={resume.reluParHumain}
        />
      </ScrollView>

      {/* Bandeau flottant — assistant IA (V2, questions pré-cadrées §2.3) */}
      <View style={[styles.fabWrap, { paddingBottom: insets.bottom + spacing.md }]}>
        <Pressable
          style={({ pressed }) => [styles.fab, pressed && { opacity: 0.9 }]}
          accessibilityRole="button"
          accessibilityLabel="Poser une question sur ce dossier (assistant, à venir)"
        >
          <View style={styles.fabIconCircle}>
            <Text style={styles.fabIcon}>💬</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.fabTitle}>Une question sur ce texte ?</Text>
            <Text style={styles.fabSub}>Réponses sourcées · Assistant IA</Text>
          </View>
          <Text style={styles.fabArrow}>›</Text>
        </Pressable>
      </View>
    </View>
  );
}

function amendementColor(sort: 'adopte' | 'rejete' | 'retire'): string {
  return { adopte: colors.pour, rejete: colors.contre, retire: colors.abstention }[
    sort
  ];
}

function AmendementSort({ sort }: { sort: 'adopte' | 'rejete' | 'retire' }) {
  const map = {
    adopte: { label: 'Adopté', color: colors.adopte, bg: colors.adopteSoft },
    rejete: { label: 'Rejeté', color: colors.contre, bg: '#F6E5D9' },
    retire: { label: 'Retiré', color: colors.textSecondary, bg: colors.surfaceMuted },
  }[sort];
  return (
    <View style={[styles.sortPill, { backgroundColor: map.bg }]}>
      <Text style={[typography.badge, { color: map.color }]}>{map.label}</Text>
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
    justifyContent: 'space-between',
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
  roundBtnShare: {
    fontSize: 16,
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
    fontSize: 22,
    lineHeight: 28,
  },
  subtitle: {
    marginTop: -spacing.md,
  },
  updateBanner: {
    alignSelf: 'flex-start',
    backgroundColor: colors.brandSoft,
    borderRadius: radius.pill,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    marginTop: -spacing.sm,
  },
  updateBannerText: {
    ...typography.badge,
    color: colors.brand,
  },
  resumePill: {
    alignSelf: 'flex-start',
    backgroundColor: colors.brandSoft,
    borderRadius: radius.pill,
    paddingVertical: 4,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  resumePillText: {
    ...typography.badge,
    color: colors.brand,
  },
  resumeGap: {
    marginBottom: spacing.md,
  },
  resumePending: {
    fontStyle: 'italic',
  },
  miniLabel: {
    ...typography.overline,
    color: colors.miniLabel,
    marginBottom: 2,
  },
  flatSection: {
    gap: spacing.md,
  },
  voteRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
  },
  voteRowBorder: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  voteInfo: {
    flex: 1,
    gap: spacing.xs,
  },
  voteObjet: {
    ...typography.body,
    fontWeight: '600',
    fontSize: 14,
    lineHeight: 20,
  },
  voteMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  voteChevron: {
    color: colors.textTertiary,
    fontSize: 24,
    fontWeight: '600',
  },
  changeRow: {
    flexDirection: 'row',
    alignItems: 'stretch',
    gap: spacing.md,
  },
  changeCol: {
    flex: 1,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.xs,
  },
  changeAvant: {
    backgroundColor: colors.surfaceMuted,
  },
  changeApres: {
    backgroundColor: colors.brandSoft,
  },
  avantLabel: {
    ...typography.overline,
    fontStyle: 'italic',
    color: colors.textTertiary,
  },
  apresLabel: {
    ...typography.overline,
    color: colors.brand,
  },
  apresText: {
    ...typography.bodySecondary,
    color: colors.brand,
    fontWeight: '600',
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  chipEmoji: {
    fontSize: 13,
  },
  amendement: {
    borderLeftWidth: 3,
    paddingLeft: spacing.md,
    gap: spacing.xs,
  },
  amendementObjet: {
    ...typography.body,
    fontWeight: '600',
    fontSize: 14,
    lineHeight: 20,
  },
  amendementMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  sortPill: {
    borderRadius: radius.pill,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
  },
  fabWrap: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacing.lg,
  },
  fab: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.brand,
    borderRadius: radius.xl,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  fabIconCircle: {
    width: 36,
    height: 36,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(255,255,255,0.25)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  fabIcon: {
    fontSize: 17,
  },
  fabTitle: {
    ...typography.cardTitle,
    color: colors.textOnAccent,
    fontSize: 15,
  },
  fabSub: {
    ...typography.meta,
    color: colors.brandSoft,
  },
  fabArrow: {
    color: colors.textOnAccent,
    fontSize: 22,
    fontWeight: '700',
  },
});
