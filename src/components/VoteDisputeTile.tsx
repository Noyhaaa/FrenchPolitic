import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';
import { VoteDisputeItem } from '@/types';
import {
  formatDateRelative,
  libelleChambreCourt,
  libelleScrutin,
} from '@/utils/format';
import { StatusBadge } from './StatusBadge';
import { MiniResultat } from './MiniResultat';

interface Props {
  vote: VoteDisputeItem;
  onPress: (vote: VoteDisputeItem) => void;
}

/** Même largeur que `DossierTile` : les rangées de l'accueil s'alignent. */
export const DISPUTE_TILE_WIDTH = 240;

/**
 * Vignette de la rangée « Les votes les plus disputés ».
 *
 * Tout ce qu'elle affiche est un **décompte officiel** : l'écart de voix, les
 * trois totaux, le nombre de groupes divisés. Aucun qualificatif sur la mesure
 * elle-même (§4.3) — « disputé » décrit le scrutin, pas ce qui était voté, et
 * le lecteur a les chiffres sous les yeux pour en juger lui-même.
 *
 * Pas de vignette teintée ni d'emoji, contrairement à `DossierTile` : ici le
 * fait, ce sont les chiffres ; les mettre en avant est le propos de la carte.
 */
export function VoteDisputeTile({ vote, onPress }: Props) {
  const { pour, contre, abstention } = vote.resultat;
  const { titre } = libelleScrutin(vote.objet, vote.typeMotion);
  // Écrit en toutes lettres : le chiffre seul (« 10 ») ne se lit pas.
  const ecart = `${vote.ecart} voix d'écart`;
  // Absent au Sénat : la délégation de vote par groupe y rend le fait
  // indéfendable — on masque plutôt que d'afficher un artefact (§2.5, §7.4).
  const divises =
    vote.groupesDisperses != null && vote.groupesDisperses > 0
      ? `${vote.groupesDisperses} groupe${
          vote.groupesDisperses > 1 ? 's' : ''
        } divisé${vote.groupesDisperses > 1 ? 's' : ''}`
      : null;

  return (
    <Pressable
      onPress={() => onPress(vote)}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      accessibilityRole="button"
      accessibilityLabel={
        `${titre}, ${vote.dossierTitre}. ${pour} pour, ${contre} contre, ` +
        `${abstention} abstentions. ${ecart}.`
      }
    >
      <View style={styles.header}>
        <StatusBadge statut={vote.statut} />
        <Text style={typography.meta}>{libelleChambreCourt(vote.chambre)}</Text>
      </View>

      <Text style={[typography.cardTitle, styles.titre]} numberOfLines={1}>
        {titre}
      </Text>
      <Text style={[typography.meta, styles.dossier]} numberOfLines={2}>
        {vote.dossierTitre}
      </Text>

      <MiniResultat resultat={vote.resultat} height={4} />

      {/* Les décomptes en clair : la barre ne porte jamais l'information
          seule (§7 point 3, RGAA §8). */}
      <Text style={styles.decomptes}>
        {pour} pour · {contre} contre · {abstention} abst.
      </Text>

      <View style={styles.footer}>
        <Text style={[typography.meta, styles.ecart]}>{ecart}</Text>
        <Text style={typography.meta}>{formatDateRelative(vote.date)}</Text>
      </View>
      {divises ? <Text style={typography.meta}>{divises}</Text> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    width: DISPUTE_TILE_WIDTH,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
  },
  pressed: {
    opacity: 0.85,
    transform: [{ scale: 0.97 }],
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  titre: {
    fontSize: 14,
    lineHeight: 19,
  },
  dossier: {
    lineHeight: 16,
    minHeight: 32,
  },
  decomptes: {
    ...typography.meta,
    color: colors.textSecondary,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  ecart: {
    color: colors.textPrimary,
  },
});
