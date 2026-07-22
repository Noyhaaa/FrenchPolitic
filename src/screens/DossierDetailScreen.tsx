import { useState } from 'react';
import {
  Pressable,
  RefreshControl,
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
  AmendementsSection,
  ExposeMotifsCard,
  QuestionsCard,
  ErrorView,
  LoadingView,
  OfflineBanner,
  ResultBar,
  SectionCard,
  SourceGrid,
  StatusBadge,
  TrajectoireNavette,
} from '@/components';
import { useDossier } from '@/hooks';
import type { ScrutinResume } from '@/types';
import {
  formatDateLong,
  formatMicroResultat,
  formatTempsLecture,
  libelleScrutin,
  natureTexte,
  phasesNavette,
  statutLabel,
  voteDecisif,
} from '@/utils/format';
import type { RootStackParamList } from '@/navigation/types';

type DetailRoute = RouteProp<RootStackParamList, 'DossierDetail'>;

/** Nombre d'éléments montrés par liste avant le bouton « Voir plus » (lisibilité :
 * un dossier réel peut compter des dizaines de votes d'amendement). */
const APERCU_LISTE = 4;

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

/**
 * Le VOTE DÉCISIF du dossier, mis en avant en tête de la section des votes :
 * le vote sur l'ensemble du texte — celui qui scelle l'adoption ou le rejet,
 * à distinguer des votes d'articles et des motions pour que l'utilisateur
 * sache d'un coup d'œil quel vote a tranché (§2.2). Purement factuel : même
 * contenu qu'une ligne de vote, présentation accentuée + une phrase
 * explicative descriptive.
 */
function VoteDecisifCard({
  scrutin,
  onPress,
}: {
  scrutin: ScrutinResume;
  onPress: () => void;
}) {
  const lib = libelleScrutin(scrutin.objet);
  const { resultat } = scrutin;
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.decisifCard, pressed && { opacity: 0.7 }]}
      accessibilityRole="button"
      accessibilityLabel={`Vote décisif : ${scrutin.objet}. ${statutLabel(
        scrutin.statut,
      )}, ${resultat.pour} pour, ${resultat.contre} contre. Voir le détail du vote.`}
    >
      <Text style={styles.decisifLabel}>Vote décisif</Text>
      <Text style={styles.voteObjet}>{lib.titre}</Text>
      <View style={styles.voteMeta}>
        <StatusBadge statut={scrutin.statut} />
        <Text style={typography.meta}>
          {formatDateLong(scrutin.date)}
          {lib.complement ? ` · ${lib.complement}` : ''}
        </Text>
      </View>
      <Text style={typography.meta}>
        {formatMicroResultat(resultat.pour, resultat.contre)}
      </Text>
      <ResultBar
        height={6}
        segments={[
          { value: resultat.pour, color: colors.pour },
          { value: resultat.abstention, color: colors.abstention },
          { value: resultat.contre, color: colors.contre },
          { value: resultat.nonVotants, color: colors.nonVotant },
        ]}
      />
      <Text style={[typography.meta, styles.decisifExplication]}>
        C'est ce vote, sur l'ensemble du texte, qui décide de son adoption ou
        de son rejet.
      </Text>
    </Pressable>
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
  const { data: dossier, loading, refreshing, offline, error, retry, refresh } =
    useDossier(route.params.dossierId);
  const goBack = () => navigation.goBack();
  // Listes longues repliées par défaut (votes, amendements, sous-amendements).
  const [listesDepliees, setListesDepliees] = useState<ReadonlySet<string>>(
    new Set(),
  );
  const basculerListe = (cle: string) =>
    setListesDepliees((prev) => {
      const next = new Set(prev);
      if (next.has(cle)) next.delete(cle);
      else next.add(cle);
      return next;
    });
  const visibles = <T,>(liste: T[], cle: string): T[] =>
    listesDepliees.has(cle) || liste.length <= APERCU_LISTE
      ? liste
      : liste.slice(0, APERCU_LISTE);
  const boutonVoirPlus = (longueur: number, cle: string, libelle: string) =>
    longueur > APERCU_LISTE ? (
      <Pressable
        onPress={() => basculerListe(cle)}
        accessibilityRole="button"
        accessibilityLabel={
          listesDepliees.has(cle)
            ? `Réduire la liste des ${libelle}`
            : `Voir les ${longueur - APERCU_LISTE} autres ${libelle}`
        }
      >
        <Text style={styles.voirPlus}>
          {listesDepliees.has(cle)
            ? 'Réduire la liste ▲'
            : `Voir les ${longueur - APERCU_LISTE} autres ${libelle} ▼`}
        </Text>
      </Pressable>
    ) : null;

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
  // Le vote décisif (sur l'ensemble du texte) sort de la liste : mis en avant
  // en tête de section pour que l'utilisateur voie quel vote a tranché — les
  // autres votes (articles, motions…) restent en liste compacte.
  const decisif = voteDecisif(dossier.scrutins);
  const autresVotes = decisif
    ? dossier.scrutins.filter((s) => s.id !== decisif.id)
    : dossier.scrutins;
  // Frise des phases de navette documentées par les votes AN (vide → masquée).
  const phases = phasesNavette(dossier.scrutins);
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
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={refresh}
            tintColor={colors.brand}
          />
        }
      >
        {/* 1. Statut (phase de navette si dispo) + titre + date */}
        <StatusBadge statut={badge.statut} label={badge.label} />
        <Text style={[typography.title, styles.title]}>{resume.titreClair}</Text>
        {/* Nature du texte (projet / proposition de loi…) quand le titre
            officiel la porte — l'utilisateur situe le sujet d'un coup d'œil. */}
        <Text style={[typography.meta, styles.subtitle]}>
          {[
            natureTexte(dossier.titreOfficiel),
            'Assemblée nationale',
            formatDateLong(dossier.dateDernierScrutin),
          ]
            .filter(Boolean)
            .join(' · ')}
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

        {/* 1bis. Trajectoire à l'Assemblée — frise des phases de navette que
            les libellés des votes documentent (1re lecture, CMP, lecture
            définitive…), statut d'une phase = son vote sur l'ensemble.
            Masquée si aucune phase documentée (§2.5). */}
        {phases.length > 0 ? <TrajectoireNavette phases={phases} /> : null}

        {/* 2. Le vote en 4 questions — l'entrée de compréhension (§2.2) :
            pourquoi / désaccord / résultat / changement, en langage simple.
            Réponse absente = « information non disponible » (§2.5). */}
        {resume.questions ? <QuestionsCard questions={resume.questions} /> : null}

        {/* 2ter. Exposé des motifs — le « pourquoi » selon l'AUTEUR du texte.
            Bloc distinct et attribué (contenu non neutre §4.3), placé après le
            résumé neutre. Absent tant que le PDF officiel n'a pas été récupéré
            (§2.5). */}
        {dossier.exposeMotifs ? (
          <ExposeMotifsCard expose={dossier.exposeMotifs} />
        ) : null}

        {/* 3. Pourquoi ce texte ? */}
        {pourquoi.length > 0 && (
          <SectionCard title="Pourquoi ce texte ?">
            <View style={{ gap: spacing.md }}>
              {pourquoi.map(([label, value]) => (
                <View key={label}>
                  <MiniLabel>{label}</MiniLabel>
                  <Text style={typography.readingBody}>{value}</Text>
                </View>
              ))}
            </View>
          </SectionCard>
        )}

        {/* 4. Ce qui change — titre hors carte, AVANT gris / APRÈS bleu (§4.5) */}
        {resume.changement && (
          <View style={styles.flatSection}>
            <Text style={typography.overline}>Ce qui change</Text>
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

        {/* 6. Les votes sur le texte — le VOTE DÉCISIF (sur l'ensemble) est mis
            en avant en tête, les autres votes (articles, motions…) suivent en
            liste compacte : une ligne par scrutin (objet + statut +
            micro-résultat), le détail (groupes, nominatif) se charge au tap
            (écran ScrutinDetail). Les votes d'amendement, eux, sont dans la
            section « Amendements » ci-dessous. */}
        {dossier.scrutins.length > 0 && (
        <SectionCard
          title={
            dossier.scrutins.length > 1
              ? `Les votes sur le texte (${dossier.scrutins.length})`
              : 'Le vote sur le texte'
          }
        >
          {decisif ? (
            <VoteDecisifCard
              scrutin={decisif}
              onPress={() =>
                navigation.navigate('ScrutinDetail', { scrutinId: decisif.id })
              }
            />
          ) : null}
          {decisif && autresVotes.length > 0 ? (
            <MiniLabel>LES AUTRES VOTES</MiniLabel>
          ) : null}
          {visibles(autresVotes, 'votes').map((s, i) => {
            // Titre = type du vote en clair (« Vote sur l'ensemble », « Motion
            // de censure »…) — le sujet, c'est le dossier lui-même ; l'objet
            // officiel complet reste sur la fiche vote (§7.5).
            const lib = libelleScrutin(s.objet);
            return (
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
                    {lib.titre}
                  </Text>
                  <View style={styles.voteMeta}>
                    <StatusBadge statut={s.statut} />
                    <Text style={typography.meta}>
                      {formatDateLong(s.date)}
                      {lib.complement ? ` · ${lib.complement}` : ''}
                    </Text>
                  </View>
                  <Text style={typography.meta}>
                    {formatMicroResultat(s.resultat.pour, s.resultat.contre)}
                  </Text>
                </View>
                <Text style={styles.voteChevron} importantForAccessibility="no">
                  ›
                </Text>
              </Pressable>
            );
          })}
          {boutonVoirPlus(autresVotes.length, 'votes', 'votes')}
        </SectionCard>
        )}

        {/* 7. Amendements — liste dé-densifiée : barre de synthèse + filtres,
            une ligne calme par amendement qui se déplie à la demande. Ses
            sous-amendements sont révélés dans le dépliage (plus de seconde
            liste séparée), chacun tappable vers son propre vote. */}
        {dossier.amendements.length > 0 && (
          <AmendementsSection
            amendements={dossier.amendements}
            onOpenScrutin={(scrutinId) =>
              navigation.navigate('ScrutinDetail', { scrutinId })
            }
          />
        )}

        {/* 8. Sources officielles du DOSSIER (dossier législatif…). La source
            de chaque vote ou amendement vit sur sa propre fiche — pas de
            doublon ici. Masqué si rien au niveau dossier (§2.5). */}
        {dossier.sources.length > 0 && (
          <View style={styles.flatSection}>
            <Text style={typography.overline}>Sources officielles</Text>
            <SourceGrid sources={dossier.sources} />
          </View>
        )}

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
  miniLabel: {
    ...typography.overline,
    color: colors.miniLabel,
    marginBottom: 2,
  },
  flatSection: {
    gap: spacing.md,
  },
  decisifCard: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    // Accent brand : le vote mis en avant (même code visuel qu'un bloc accentué).
    borderLeftWidth: 3,
    borderLeftColor: colors.brand,
    padding: spacing.lg,
    gap: spacing.xs,
    marginBottom: spacing.md,
  },
  decisifLabel: {
    ...typography.overline,
    color: colors.brand,
  },
  decisifExplication: {
    marginTop: spacing.xs,
    color: colors.textTertiary,
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
    ...typography.cardTitle,
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
  voirPlus: {
    ...typography.meta,
    color: colors.brand,
    fontWeight: '600',
    paddingTop: spacing.sm,
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
    color: colors.textOnAccent,
    opacity: 0.75,
  },
  fabArrow: {
    color: colors.textOnAccent,
    fontSize: 22,
    fontWeight: '700',
  },
});
