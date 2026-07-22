import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, serifDisplaySemi, spacing, typography } from '@/theme';
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
 * Ligne compacte d'amendement (ou de sous-amendement) : numéro + sort + auteur.
 * Tout provient du libellé officiel du scrutin — rien n'est reformulé (§2.5).
 *
 * Quand l'ingestion a récupéré le **contenu** (open data AN), le dépliant
 * « Contenu » n'est plus deux cartes grises empilées mais une **colonne de
 * lecture** (§8, « donner envie de lire ») : un fil vertical relie deux temps —
 * d'abord le FAIT (« ce que ça change », dispositif, neutre), puis la VOIX
 * (« selon l'auteur », exposé sommaire, point de vue → accent ambre, italique,
 * jamais présenté comme neutre, §4.3). Texte de lecture en serif de labeur.
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
        <View style={styles.lecture}>
          {/* Le fil qui relie les deux temps de lecture. */}
          <View style={styles.rail} />

          {a.dispositif ? (
            <View style={styles.temps}>
              <View style={[styles.dot, { backgroundColor: sort.color }]} />
              <Text style={[typography.overline, styles.tempsLabel]}>
                Ce que {sous ? 'le sous-amendement' : "l'amendement"} change
              </Text>
              <Text style={[typography.readingBody, styles.tempsTexte]}>
                {a.dispositif}
              </Text>
            </View>
          ) : null}

          {a.exposeSommaire ? (
            <View style={[styles.temps, a.dispositif && styles.tempsGap]}>
              <View style={[styles.dot, styles.dotWarm]} />
              <Text style={[typography.overline, styles.tempsLabelWarm]}>
                Pourquoi · Selon l'auteur
              </Text>
              <Text style={[typography.readingQuote, styles.tempsTexte]}>
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
    ...typography.cardTitle,
    fontFamily: serifDisplaySemi,
    fontSize: 15,
    lineHeight: 21,
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
  // --- Colonne de lecture ---
  lecture: {
    position: 'relative',
    marginLeft: spacing.md,
    marginTop: spacing.sm,
    paddingLeft: 30,
  },
  rail: {
    position: 'absolute',
    left: 5,
    top: 6,
    bottom: 6,
    width: 2,
    backgroundColor: colors.borderStrong,
  },
  temps: {
    position: 'relative',
  },
  tempsGap: {
    marginTop: spacing.xl,
  },
  dot: {
    position: 'absolute',
    left: -25,
    top: 2,
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  dotWarm: {
    backgroundColor: colors.accentWarm,
  },
  tempsLabel: {
    color: colors.textSecondary,
  },
  tempsLabelWarm: {
    color: colors.accentWarm,
  },
  tempsTexte: {
    marginTop: spacing.sm,
  },
});
