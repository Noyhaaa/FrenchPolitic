import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { colors, radius, spacing, typography } from '@/theme';
import type { TermeGlossaire } from '@/types/glossaire';
import type { RootStackParamList } from '@/navigation/types';

interface Props {
  terme: TermeGlossaire;
}

/**
 * Marqueur signalant qu'un terme a une définition (§8). Il accompagne toujours
 * un libellé texte : l'aide n'est jamais portée par la seule couleur (RGAA §8),
 * et le caractère est décoratif — c'est l'élément qui le contient qui porte
 * l'`accessibilityLabel`.
 */
export const MARQUEUR_GLOSSAIRE = 'ⓘ';

export function MarqueurGlossaire() {
  return (
    <Text style={styles.marqueur} importantForAccessibility="no">
      {MARQUEUR_GLOSSAIRE}
    </Text>
  );
}

/**
 * Définition d'un terme de procédure, dépliée à la demande **là où le mot
 * s'affiche** — une étape de la frise, le titre d'une fiche vote.
 *
 * Même geste que l'exposé des motifs ou le contenu d'un amendement
 * (`ExposeMotifsCard`, `AmendementRow`) : rien ne s'ouvre tant que le lecteur
 * ne le demande, et le contenu est un **fait de procédure**, pas un commentaire
 * sur le texte concerné (§4.3).
 *
 * La définition n'est pas un cul-de-sac : quand le terme a plus à dire (déroulé
 * « Concrètement », faux amis, dossiers où le mot apparaît), un lien mène à sa
 * fiche complète. C'est le même contenu des deux côtés — une seule source,
 * `constants/glossaire.ts`.
 */
export function DefinitionGlossaire({ terme }: Props) {
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  return (
    <View style={styles.bloc}>
      <Text style={styles.terme} accessibilityRole="header">
        {terme.libelle}
      </Text>
      <Text style={styles.definition}>{terme.definition}</Text>
      <Pressable
        onPress={() => navigation.navigate('GlossaireTerme', { termeId: terme.id })}
        accessibilityRole="button"
        accessibilityLabel={`Lire la fiche du terme « ${terme.libelle} »`}
        hitSlop={8}
      >
        <Text style={styles.lien}>Lire la fiche →</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  marqueur: {
    ...typography.meta,
    color: colors.brand,
  },
  bloc: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.brandSoft,
    gap: spacing.xs,
  },
  terme: {
    ...typography.label,
    color: colors.textPrimary,
  },
  definition: {
    fontSize: 13.5,
    lineHeight: 20,
    color: colors.textSecondary,
  },
  lien: {
    marginTop: spacing.xs,
    fontSize: 12,
    fontWeight: '600',
    color: colors.splashLigneSoft,
  },
});
