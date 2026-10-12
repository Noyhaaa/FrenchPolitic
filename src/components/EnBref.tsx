import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing, typography } from '@/theme';
import type { PhraseSourcee, ScrutinResume } from '@/types';
import { formatDateLong, libelleChambre } from '@/utils/format';
import { SectionCard } from './SectionCard';

interface Props {
  phrases: PhraseSourcee[];
  /** Le vote décisif (`voteDecisif`) : c'est de lui que parle la phrase des groupes. */
  decisif?: ScrutinResume;
}

/**
 * « En bref » : les phrases du résumé neutre que la fiche ne dit nulle part
 * ailleurs. Le résumé est composé par gabarit, sans LLM, depuis les seuls faits
 * des votes (`app/ai/gabarit.py`) ; chaque phrase porte l'identifiant du fait
 * qui l'étaie.
 *
 * On n'en retient que deux. Les autres répètent un bloc déjà à l'écran — nature
 * du texte (sous-titre), résultat du vote décisif (Q3 et carte du vote),
 * nombre d'amendements (section Amendements) — et un résumé qui redit la
 * fiche ne fait pas gagner les 30 secondes promises.
 *
 * La phrase des groupes est précédée du vote qu'elle décrit : sans lui,
 * « ont voté pour » ne dirait pas sur quoi.
 */
export function EnBref({ phrases, decisif }: Props) {
  const parSource = new Map(phrases.map((p) => [p.sourceId, p.phrase]));
  const trajectoire = parSource.get('trajectoire');
  const groupes = decisif ? parSource.get('positions_groupes') : undefined;
  if (!trajectoire && !groupes) return null;

  return (
    <SectionCard title="En bref">
      <View style={styles.liste}>
        {trajectoire ? (
          <Text style={typography.readingBody}>{trajectoire}</Text>
        ) : null}
        {groupes && decisif ? (
          <View>
            <Text style={styles.intitule}>
              {`VOTE DÉCISIF · ${libelleChambre(decisif.chambre).toUpperCase()} · ${formatDateLong(
                decisif.date,
              ).toUpperCase()}`}
            </Text>
            <Text style={typography.readingBody}>{groupes}</Text>
          </View>
        ) : null}
      </View>
    </SectionCard>
  );
}

const styles = StyleSheet.create({
  liste: {
    gap: spacing.md,
  },
  intitule: {
    ...typography.overline,
    color: colors.miniLabel,
    marginBottom: spacing.xs,
  },
});
