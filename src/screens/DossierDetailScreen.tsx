import { useState } from 'react';
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
  AmendementRow,
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
  libelleScrutin,
  natureTexte,
  statutLabel,
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
  // Sous-amendements du dossier, à plat, avec le numéro de leur amendement
  // parent pour les situer (section dédiée, distincte des amendements).
  const sousAmendements = dossier.amendements.flatMap((a) =>
    (a.sousAmendements ?? []).map((sa) => ({ sa, parentNumero: a.numero })),
  );
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

        {/* 6. Les votes sur le texte — liste compacte : une ligne par scrutin
            (objet + statut + micro-résultat), le détail (groupes, nominatif)
            se charge au tap (écran ScrutinDetail). Les votes d'amendement, eux,
            sont dans la section « Amendements » ci-dessous. */}
        {dossier.scrutins.length > 0 && (
        <SectionCard
          title={
            dossier.scrutins.length > 1
              ? `Les votes sur le texte (${dossier.scrutins.length})`
              : 'Le vote sur le texte'
          }
        >
          {visibles(dossier.scrutins, 'votes').map((s, i) => {
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
          {boutonVoirPlus(dossier.scrutins.length, 'votes', 'votes')}
        </SectionCard>
        )}

        {/* 7. Amendements — lignes compactes (numéro + sort + auteur), sans
            répéter la formule « l'amendement n° X de M. Y » de chaque objet.
            Si l'amendement a été mis aux voix (scrutinId), la ligne ouvre la
            page du vote (qui a voté pour/contre) — ses sous-amendements y sont
            aussi listés. Sinon (amendement retiré…), la ligne est informative. */}
        {dossier.amendements.length > 0 && (
          <SectionCard title={`Amendements (${dossier.amendements.length})`}>
            <View style={{ gap: spacing.md }}>
              {visibles(dossier.amendements, 'amendements').map((a) => (
                <AmendementRow
                  key={a.id}
                  amendement={a}
                  onPress={
                    a.scrutinId
                      ? () =>
                          navigation.navigate('ScrutinDetail', {
                            scrutinId: a.scrutinId!,
                          })
                      : undefined
                  }
                />
              ))}
              {boutonVoirPlus(dossier.amendements.length, 'amendements', 'amendements')}
            </View>
          </SectionCard>
        )}

        {/* 8. Sous-amendements — section dédiée (distincte des amendements),
            chaque ligne rappelle l'amendement visé et ouvre son propre vote. */}
        {sousAmendements.length > 0 && (
          <SectionCard title={`Sous-amendements (${sousAmendements.length})`}>
            <View style={{ gap: spacing.md }}>
              {visibles(sousAmendements, 'sous-amendements').map(
                ({ sa, parentNumero }) => (
                  <AmendementRow
                    key={sa.id}
                    amendement={sa}
                    sous
                    parentNumero={parentNumero}
                    onPress={
                      sa.scrutinId
                        ? () =>
                            navigation.navigate('ScrutinDetail', {
                              scrutinId: sa.scrutinId!,
                            })
                        : undefined
                    }
                  />
                ),
              )}
              {boutonVoirPlus(
                sousAmendements.length,
                'sous-amendements',
                'sous-amendements',
              )}
            </View>
          </SectionCard>
        )}

        {/* 9. Sources officielles du DOSSIER (dossier législatif…). La source
            de chaque vote ou amendement vit sur sa propre fiche — pas de
            doublon ici. Masqué si rien au niveau dossier (§2.5). */}
        {dossier.sources.length > 0 && (
          <View style={styles.flatSection}>
            <Text style={typography.sectionTitle}>Sources officielles</Text>
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
    color: colors.brandSoft,
  },
  fabArrow: {
    color: colors.textOnAccent,
    fontSize: 22,
    fontWeight: '700',
  },
});
