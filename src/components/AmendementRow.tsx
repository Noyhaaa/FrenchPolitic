import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, serif, spacing, typography } from '@/theme';
import type { Amendement } from '@/types';
import { detailObjetAmendement, titreAmendement } from '@/utils/format';

const SORT_UI = {
  adopte: { label: 'Adopté', color: colors.adopte, bg: colors.adopteSoft },
  rejete: { label: 'Rejeté', color: colors.contre, bg: colors.rejeteSoft },
  retire: { label: 'Retiré', color: colors.textSecondary, bg: colors.surfaceMuted },
} as const;

interface Props {
  amendement: Amendement;
  /** true = sous-amendement (titre « Sous-amendement n° X »). */
  sous?: boolean;
  /** Numéro de l'amendement parent, pour situer un sous-amendement. */
  parentNumero?: string;
  /** Ouvre la fiche vote — absent si l'amendement n'a pas été mis aux voix. */
  onPress?: () => void;
}

/**
 * Ligne compacte d'amendement (ou de sous-amendement) : numéro + sort + auteur,
 * la partie descriptive de l'objet officiel en dessous (§4.5). Tout provient du
 * libellé officiel du scrutin — rien n'est reformulé (§2.5).
 *
 * Quand l'ingestion a récupéré le **contenu** de l'amendement (open data AN), un
 * dépliant « Contenu » montre ce qu'il change (dispositif, factuel) et son
 * **exposé sommaire** — le « pourquoi » côté AUTEUR, donc en bloc **attribué**
 * (§4.3), jamais présenté comme neutre.
 */
export function AmendementRow({ amendement: a, sous, parentNumero, onPress }: Props) {
  const [ouvert, setOuvert] = useState(false);
  const sort = SORT_UI[a.sort];
  const detail = detailObjetAmendement(a);
  const nbSous = a.sousAmendements?.length ?? 0;
  const aContenu = Boolean(a.dispositif || a.exposeSommaire);

  const contenu = (
    <View style={[styles.row, { borderLeftColor: sort.color }]}>
      <View style={styles.info}>
        <Text style={styles.titre} numberOfLines={2}>
          {titreAmendement(a, sous)}
        </Text>
        {detail ? (
          <Text style={typography.bodySecondary} numberOfLines={2}>
            {detail}
          </Text>
        ) : null}
        <View style={styles.meta}>
          <View style={[styles.sortPill, { backgroundColor: sort.bg }]}>
            <Text style={[typography.badge, { color: sort.color }]}>
              {sort.label}
            </Text>
          </View>
          {a.cible ? (
            <View style={styles.ciblePill}>
              <Text style={typography.badge}>{a.cible}</Text>
            </View>
          ) : null}
          {a.auteur ? <Text style={typography.meta}>{a.auteur}</Text> : null}
          {parentNumero ? (
            <Text style={typography.meta}>→ amendement n° {parentNumero}</Text>
          ) : null}
          {nbSous > 0 ? (
            <Text style={typography.meta}>
              {nbSous} sous-amendement{nbSous > 1 ? 's' : ''}
            </Text>
          ) : null}
        </View>
      </View>
      {onPress ? (
        <Text style={styles.chevron} importantForAccessibility="no">
          ›
        </Text>
      ) : null}
    </View>
  );

  const enveloppe = onPress ? (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => pressed && { opacity: 0.7 }}
      accessibilityRole="button"
      accessibilityLabel={`${a.objet}. ${sort.label}. Voir le détail du vote.`}
    >
      {contenu}
    </Pressable>
  ) : (
    contenu
  );

  if (!aContenu) return enveloppe;

  return (
    <View style={styles.bloc}>
      {enveloppe}
      <Pressable
        onPress={() => setOuvert((v) => !v)}
        style={styles.toggle}
        accessibilityRole="button"
        accessibilityLabel={
          ouvert
            ? "Masquer le contenu de l'amendement"
            : "Voir le contenu de l'amendement"
        }
      >
        <Text style={styles.toggleText}>
          {ouvert ? 'Masquer le contenu ▲' : 'Voir le contenu ▼'}
        </Text>
      </Pressable>

      {ouvert ? (
        <View style={styles.detail}>
          {/* Mini-cartes à fond distinct : même hiérarchie visuelle que la
              fiche vote (dispositif = carte neutre, exposé = carte attribuée
              à accent ambre). */}
          {a.dispositif ? (
            <View style={styles.detailCard}>
              <Text style={[typography.overline, styles.detailTitre]}>
                Ce que {sous ? 'le sous-amendement' : "l'amendement"} change
              </Text>
              <Text style={typography.bodySecondary}>{a.dispositif}</Text>
            </View>
          ) : null}
          {a.exposeSommaire ? (
            <View style={[styles.detailCard, styles.expose]}>
              <View style={styles.pill}>
                <Text style={styles.pillText}>👤 Selon l'auteur</Text>
              </View>
              <Text style={[typography.bodySecondary, styles.exposeQuote]}>
                « {a.exposeSommaire} »
              </Text>
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  bloc: {
    gap: spacing.xs,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    borderLeftWidth: 3,
    paddingLeft: spacing.md,
  },
  info: {
    flex: 1,
    gap: spacing.xs,
  },
  titre: {
    ...typography.body,
    fontWeight: '700',
    fontFamily: serif,
    fontSize: 14,
    lineHeight: 20,
  },
  meta: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: spacing.sm,
  },
  sortPill: {
    borderRadius: radius.pill,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
  },
  ciblePill: {
    borderRadius: radius.pill,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
    backgroundColor: colors.surfaceMuted,
  },
  chevron: {
    color: colors.textTertiary,
    fontSize: 24,
    fontWeight: '600',
  },
  toggle: {
    paddingLeft: spacing.md,
  },
  toggleText: {
    ...typography.meta,
    color: colors.brand,
    fontWeight: '600',
  },
  detail: {
    marginLeft: spacing.md,
    gap: spacing.sm,
  },
  detailCard: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.lg,
    padding: spacing.md,
  },
  detailTitre: {
    marginBottom: spacing.xs,
  },
  expose: {
    // Accent ambre : contenu « point de vue », comme l'exposé des motifs.
    borderLeftWidth: 3,
    borderLeftColor: colors.accentWarm,
  },
  pill: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accentWarmSoft,
    borderRadius: radius.pill,
    paddingVertical: 4,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  pillText: {
    ...typography.badge,
    color: colors.accentWarm,
  },
  exposeQuote: {
    fontStyle: 'italic',
  },
});
