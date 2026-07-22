import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, spacing, typography } from '@/theme';
import type { DeputeListItem } from '@/types';
import { Avatar } from './Avatar';

interface Props {
  depute: DeputeListItem;
  onPress: (depute: DeputeListItem) => void;
}

/**
 * Une ligne de l'annuaire : portrait, nom, puis groupe et circonscription en
 * repère mono. Même gabarit pour tous les députés, quel que soit leur groupe
 * (§7.4 : symétrie de traitement).
 */
export function DeputeRow({ depute, onPress }: Props) {
  return (
    <Pressable
      onPress={() => onPress(depute)}
      style={({ pressed }) => [styles.ligne, pressed && styles.pressee]}
      accessibilityRole="button"
      accessibilityLabel={`${depute.nom}, ${depute.groupeNom}, ${depute.circonscription}. Voir sa fiche.`}
    >
      <Avatar
        nom={depute.nom}
        portraitUrl={depute.portraitUrl}
        groupeCouleur={depute.groupeCouleur}
        taille={44}
      />
      <View style={styles.textes}>
        <Text style={styles.nom} numberOfLines={1}>
          {depute.nom}
        </Text>
        <Text style={typography.meta} numberOfLines={1}>
          {[depute.groupeNom, depute.circonscription].filter(Boolean).join(' · ')}
        </Text>
      </View>
      <Text style={styles.chevron} importantForAccessibility="no">
        ›
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  ligne: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
  },
  pressee: {
    opacity: 0.7,
  },
  textes: {
    flex: 1,
    gap: 3,
  },
  nom: {
    ...typography.readingBody,
    fontSize: 17,
    lineHeight: 22,
  },
  chevron: {
    color: colors.textTertiary,
    fontSize: 22,
    fontWeight: '600',
  },
});
