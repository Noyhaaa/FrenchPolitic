import { StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import type { EtatTexte, TexteAdopte } from '@/types';
import { formatDateLong } from '@/utils/format';
import { SourceLink } from './SourceLink';

interface Props {
  etat?: EtatTexte | null;
  texteAdopte?: TexteAdopte | null;
}

/**
 * La loi finale (§7.5) — ce que le texte est devenu, et où le lire.
 *
 * La fiche décrivait jusqu'ici le texte **déposé** de bout en bout : l'exposé de
 * son auteur, ses articles d'origine, et « qu'est-ce que ça change ? » au
 * conditionnel. Sur un texte promulgué, cette version n'existe plus — la navette
 * et les amendements l'ont modifiée. Cette carte donne la loi telle qu'elle
 * existe, et les deux liens pour la lire.
 *
 * ⚠️ **Deux liens, parce que ce sont deux choses.** Le texte *voté* est celui
 * que le Parlement a adopté ; le texte *en vigueur* (Légifrance) est celui qui
 * s'applique aujourd'hui, et une loi peut avoir été modifiée depuis sa
 * promulgation. Les confondre sous un seul lien laisserait croire que l'un vaut
 * l'autre.
 *
 * Le lien du texte voté disparaît quand l'archive ne le désigne pas (mesuré :
 * 76 lois sur 96), plutôt qu'un lien mort ou un « indisponible » (§2.5). Le
 * **corps** de la loi, lui, n'est jamais affiché : du droit codifié brut est
 * illisible — même doctrine que le dispositif du texte déposé.
 */
export function LoiCard({ etat, texteAdopte }: Props) {
  // La carte ne parle que d'une loi existante : sur un texte encore en navette,
  // il n'y a ni numéro, ni Journal officiel, ni texte définitif.
  if (etat?.etat !== 'promulgue') return null;

  const reference =
    etat.numeroLoi && etat.date
      ? `Loi n° ${etat.numeroLoi} du ${formatDateLong(etat.date)}`
      : null;
  const journalOfficiel = etat.dateJournalOfficiel
    ? `Journal officiel du ${formatDateLong(etat.dateJournalOfficiel)}`
    : null;
  const liens = [
    texteAdopte?.source,
    etat.urlLegifrance
      ? {
          type: 'texte' as const,
          libelle: 'Texte en vigueur (Légifrance)',
          url: etat.urlLegifrance,
        }
      : null,
  ].filter((s): s is NonNullable<typeof s> => s != null);

  if (!reference && !journalOfficiel && liens.length === 0) return null;

  return (
    <View style={styles.card}>
      <Text style={[typography.overline, styles.titre]}>La loi</Text>
      {reference ? <Text style={styles.reference}>{reference}</Text> : null}
      {journalOfficiel ? (
        <Text style={typography.meta}>{journalOfficiel}</Text>
      ) : null}
      {liens.length > 0 ? (
        <View style={styles.liens}>
          {liens.map((source) => (
            <SourceLink key={source.url} source={source} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    gap: spacing.xs,
  },
  titre: {
    marginBottom: spacing.xs,
  },
  reference: {
    ...typography.readingBody,
    fontSize: 16,
    lineHeight: 22,
    fontWeight: '700',
  },
  liens: {
    marginTop: spacing.md,
    gap: spacing.sm,
    alignItems: 'flex-start',
  },
});
