import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { GLOSSAIRE_PAR_ID } from '@/constants/glossaire';
import { colors, spacing, typography } from '@/theme';
import type { MiseAuPoint } from '@/types';
import { DefinitionGlossaire, MarqueurGlossaire } from './DefinitionGlossaire';
import { SectionCard } from './SectionCard';

interface Props {
  misesAuPoint: MiseAuPoint[];
  onOuvrirDepute: (deputeId: string) => void;
}

/**
 * Ce que des députés ont déclaré après le vote, tel que l'Assemblée le publie
 * avec le scrutin. Les phrases sont celles de l'Assemblée, mot pour mot ; la
 * mention de l'article 68 du Règlement aussi.
 *
 * Un fait à côté du vote, pas une correction : le décompte, les groupes et la
 * liste nominative au-dessus restent ceux du vote enregistré, et aucune
 * statistique (« contre son groupe », portrait) n'en tient compte. On ne dit
 * jamais non plus ce que le résultat « aurait été » : c'est une hypothèse, pas
 * une donnée (§2.5).
 */
export function MisesAuPointCard({ misesAuPoint, onOuvrirDepute }: Props) {
  const [definitionOuverte, setDefinitionOuverte] = useState(false);
  if (misesAuPoint.length === 0) return null;
  const terme = GLOSSAIRE_PAR_ID['mise-au-point'];
  const declarations = misesAuPoint.filter((m) => m.nature === 'mise_au_point');
  const pannes = misesAuPoint.filter((m) => m.nature === 'dysfonctionnement');

  // Le nom reste cliquable DANS la phrase officielle, comme dans la liste
  // nominative : on découpe la phrase autour du nom, sans la réécrire.
  const ligne = (m: MiseAuPoint, i: number) => {
    const debut = m.phrase.indexOf(m.nom);
    if (!m.deputeId || debut < 0) {
      return (
        <Text key={i} style={typography.readingBody}>
          {m.phrase}
        </Text>
      );
    }
    return (
      <Text key={i} style={typography.readingBody}>
        {m.phrase.slice(0, debut)}
        <Text
          style={styles.nomLien}
          onPress={() => onOuvrirDepute(m.deputeId as string)}
          accessibilityRole="link"
          accessibilityLabel={`Ouvrir la fiche de ${m.nom}`}
        >
          {m.nom}
        </Text>
        {m.phrase.slice(debut + m.nom.length)}
      </Text>
    );
  };

  return (
    <SectionCard title="Mises au point">
      <View style={styles.bloc}>
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
              <Text style={styles.aideTexte}>Qu'est-ce qu'une mise au point ?</Text>
              <MarqueurGlossaire />
            </Pressable>
            {definitionOuverte ? <DefinitionGlossaire terme={terme} /> : null}
          </>
        ) : null}
        <Text style={typography.meta}>
          (Sous réserve des dispositions de l'article 68, alinéa 4, du Règlement de
          l'Assemblée nationale)
        </Text>
        {declarations.length > 0 ? (
          <View style={styles.liste}>{declarations.map(ligne)}</View>
        ) : null}
        {pannes.length > 0 ? (
          <View style={styles.liste}>
            <Text style={styles.intitule}>DYSFONCTIONNEMENT DU SYSTÈME DE VOTE</Text>
            {pannes.map(ligne)}
          </View>
        ) : null}
      </View>
    </SectionCard>
  );
}

const styles = StyleSheet.create({
  bloc: {
    gap: spacing.md,
  },
  liste: {
    gap: spacing.sm,
  },
  aide: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  aideTexte: {
    ...typography.meta,
    color: colors.textSecondary,
  },
  intitule: {
    ...typography.overline,
    color: colors.miniLabel,
  },
  nomLien: {
    textDecorationLine: 'underline',
    color: colors.textPrimary,
  },
});
