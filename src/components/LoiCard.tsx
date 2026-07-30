import { StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import type { EtatTexte } from '@/types';
import { formatDateLong } from '@/utils/format';

interface Props {
  etat?: EtatTexte | null;
}

/**
 * La loi finale (§7.5) — ce que le texte est devenu, et où le lire.
 *
 * La fiche décrivait jusqu'ici le texte **déposé** de bout en bout : l'exposé de
 * son auteur, ses articles d'origine, et « qu'est-ce que ça change ? » au
 * conditionnel. Sur un texte promulgué, cette version n'existe plus — la navette
 * et les amendements l'ont modifiée. Cette carte donne la loi telle qu'elle
 * existe : son numéro, sa date, son *Journal officiel*.
 *
 * ⚠️ **Pas de lien ici.** Le texte voté et le texte en vigueur sont deux
 * documents distincts — ce que le Parlement a adopté, et ce qui s'applique
 * aujourd'hui — et ils figurent tous deux dans « Les documents du dossier », en
 * bas de fiche, avec le reste (§7.5). Les répéter ici afficherait les mêmes
 * URLs deux fois sur une même page.
 *
 * La **référence écrite** reste, elle, indispensable : c'est elle qui permet de
 * retrouver la loi même si un lien vieillit. Le **corps** de la loi n'est jamais
 * affiché : du droit codifié brut est illisible — même doctrine que le
 * dispositif du texte déposé.
 */
export function LoiCard({ etat }: Props) {
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
  if (!reference && !journalOfficiel) return null;

  return (
    <View style={styles.card}>
      <Text style={[typography.overline, styles.titre]}>La loi</Text>
      {reference ? <Text style={styles.reference}>{reference}</Text> : null}
      {journalOfficiel ? (
        <Text style={typography.meta}>{journalOfficiel}</Text>
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
});
