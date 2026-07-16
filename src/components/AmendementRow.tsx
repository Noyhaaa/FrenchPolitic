import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
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
 */
export function AmendementRow({ amendement: a, sous, parentNumero, onPress }: Props) {
  const sort = SORT_UI[a.sort];
  const detail = detailObjetAmendement(a);
  const nbSous = a.sousAmendements?.length ?? 0;

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

  if (!onPress) return contenu;
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => pressed && { opacity: 0.7 }}
      accessibilityRole="button"
      accessibilityLabel={`${a.objet}. ${sort.label}. Voir le détail du vote.`}
    >
      {contenu}
    </Pressable>
  );
}

const styles = StyleSheet.create({
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
    fontWeight: '600',
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
  chevron: {
    color: colors.textTertiary,
    fontSize: 24,
    fontWeight: '600',
  },
});
