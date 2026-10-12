import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { GLOSSAIRE_PAR_ID } from '@/constants/glossaire';
import { colors, spacing, typography } from '@/theme';
import type { AmendementsCommission } from '@/types';
import { DefinitionGlossaire, MarqueurGlossaire } from './DefinitionGlossaire';
import { SectionCard } from './SectionCard';

interface Props {
  commissions: AmendementsCommission[];
}

const pluriel = (n: number, mot: string) => `${n} ${mot}${n > 1 ? 's' : ''}`;

/**
 * Ce que la commission saisie au fond a fait du texte avant la séance : combien
 * d'amendements elle a adoptés et rejetés, par commission nommée.
 *
 * Un **décompte**, pas un vote : aucune voix, aucun groupe, aucun nom — la
 * source ne donne que le sort de chaque amendement. Les commissions pour avis
 * (qui ne modifient pas le texte) et celles du Sénat n'y sont pas : le titre
 * dit donc exactement ce que le chiffre compte (§2.5). « Saisie au fond » est
 * du jargon, expliqué par le glossaire à la demande (§8).
 */
export function AmendementsCommissionCard({ commissions }: Props) {
  const [definitionOuverte, setDefinitionOuverte] = useState(false);
  if (commissions.length === 0) return null;
  const terme = GLOSSAIRE_PAR_ID['commission-saisie-au-fond'];

  return (
    <SectionCard title="En commission à l'Assemblée">
      <View style={styles.liste}>
        {commissions.map((c) => (
          <View
            key={c.commission}
            accessible
            accessibilityLabel={`${c.commission} : ${pluriel(
              c.adoptes,
              'amendement adopté',
            )}, ${pluriel(c.rejetes, 'rejeté')}.`}
          >
            <Text style={typography.label}>{c.commission}</Text>
            <Text style={typography.meta}>
              {pluriel(c.adoptes, 'amendement adopté')} ·{' '}
              {pluriel(c.rejetes, 'rejeté')}
            </Text>
          </View>
        ))}
      </View>
      {terme ? (
        <>
          <Pressable
            onPress={() => setDefinitionOuverte((o) => !o)}
            accessibilityRole="button"
            accessibilityState={{ expanded: definitionOuverte }}
            accessibilityLabel={`${terme.libelle}. Définition.`}
            style={styles.aide}
            hitSlop={8}
          >
            <Text style={styles.aideTexte}>Commission saisie au fond</Text>
            <MarqueurGlossaire />
          </Pressable>
          {definitionOuverte ? <DefinitionGlossaire terme={terme} /> : null}
        </>
      ) : null}
      <Text style={[typography.meta, styles.provenance]}>
        D'après l'archive officielle des amendements de l'Assemblée nationale.
      </Text>
    </SectionCard>
  );
}

const styles = StyleSheet.create({
  liste: {
    gap: spacing.md,
  },
  aide: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: spacing.md,
  },
  aideTexte: {
    ...typography.meta,
    color: colors.textSecondary,
  },
  provenance: {
    marginTop: spacing.sm,
  },
});
