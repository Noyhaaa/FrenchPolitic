import { useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import type { PositionVote, VoteDepute } from '@/types';
import {
  formatDateLong,
  libelleObjetVote,
  libellePositionVotee,
  moisAnnee,
} from '@/utils/format';

/** Couleur du nœud et de la pastille selon le sens du vote (§8 : toujours
 *  accompagnée du libellé, jamais la couleur seule). */
const COULEUR_POSITION: Record<PositionVote, string> = {
  pour: colors.pour,
  contre: colors.contre,
  abstention: colors.abstention,
  non_votant: colors.nonVotant,
};

interface Mois {
  cle: string;
  label: string;
  votes: VoteDepute[];
}

/** Regroupe l'historique par mois, en conservant l'ordre reçu (récent → ancien). */
function grouperParMois(votes: VoteDepute[]): Mois[] {
  const mois: Mois[] = [];
  for (const v of votes) {
    const cle = v.date.slice(0, 7);
    const dernier = mois[mois.length - 1];
    if (dernier && dernier.cle === cle) dernier.votes.push(v);
    else mois.push({ cle, label: moisAnnee(v.date), votes: [v] });
  }
  return mois;
}

function Entree({
  vote,
  onOpen,
}: {
  vote: VoteDepute;
  onOpen?: (vote: VoteDepute) => void;
}) {
  const couleur = COULEUR_POSITION[vote.position];
  const sens = libellePositionVotee(vote.position);

  const contenu = (
    <View style={styles.entree}>
      {/* Nœud du fil, posé sur le rail. */}
      <View
        style={[styles.noeud, { backgroundColor: couleur, shadowColor: couleur }]}
        importantForAccessibility="no"
      />
      <View style={styles.corps}>
        <View style={styles.badges}>
          <View style={[styles.pastille, { borderColor: couleur }]}>
            <Text style={[styles.pastilleTexte, { color: couleur }]}>{sens}</Text>
          </View>
          {/* Fait déduit : la position du député diffère de celle de la
              majorité de son groupe sur ce même scrutin. Descriptif, jamais
              évaluatif (§7.4). */}
          {vote.contreSonGroupe ? (
            <View style={styles.pastilleEcart}>
              <Text style={styles.pastilleEcartTexte}>⚡ Contre son groupe</Text>
            </View>
          ) : null}
        </View>

        <Text style={styles.titre} numberOfLines={2}>
          {vote.titre}
        </Text>

        <Text style={typography.meta}>
          {libelleObjetVote(vote.objetType)} · {formatDateLong(vote.date)}
        </Text>
      </View>
    </View>
  );

  if (!onOpen || !vote.dossierId) return contenu;
  return (
    <Pressable
      onPress={() => onOpen(vote)}
      style={({ pressed }) => pressed && { opacity: 0.7 }}
      accessibilityRole="button"
      accessibilityLabel={`${sens}. ${vote.titre}. ${
        vote.contreSonGroupe ? 'Contre son groupe. ' : ''
      }Ouvrir le dossier.`}
    >
      {contenu}
    </Pressable>
  );
}

interface Props {
  votes: VoteDepute[];
  /** Ouvre le dossier lié (absent → l'entrée n'est pas tappable). */
  onOpen?: (vote: VoteDepute) => void;
}

/**
 * Historique de vote d'un député, en fil chronologique groupé par mois. Chaque
 * entrée porte le sens du vote (pastille couleur **et** libellé, §8), la nature
 * de ce qui était voté, la date et le titre officiel. Rien n'est agrégé ni
 * commenté : ce sont les scrutins publics tels quels (§5.2, §2.5).
 */
export function VoteHistoryFil({ votes, onOpen }: Props) {
  const mois = useMemo(() => grouperParMois(votes), [votes]);

  return (
    <View style={styles.fil}>
      {mois.map((m) => (
        <View key={m.cle} style={styles.groupe}>
          <Text style={[typography.overline, styles.moisTitre]}>{m.label}</Text>
          <View style={styles.entrees}>
            {/* Rail vertical continu derrière les nœuds du mois. */}
            <View style={styles.rail} importantForAccessibility="no" />
            {m.votes.map((v) => (
              <Entree key={v.scrutinId} vote={v} onOpen={onOpen} />
            ))}
          </View>
        </View>
      ))}
    </View>
  );
}

const RAIL_X = 5; // centre du rail : la moitié de la largeur du nœud (12 px)

const styles = StyleSheet.create({
  fil: {
    gap: spacing.xl,
  },
  groupe: {
    gap: spacing.md,
  },
  moisTitre: {
    marginLeft: spacing.xxl,
  },
  entrees: {
    position: 'relative',
  },
  rail: {
    position: 'absolute',
    left: RAIL_X,
    top: spacing.sm,
    bottom: spacing.sm,
    width: 2,
    backgroundColor: colors.borderStrong,
  },
  entree: {
    flexDirection: 'row',
    gap: spacing.lg,
    paddingBottom: spacing.lg,
  },
  noeud: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginTop: 3,
    // Halo : détache le nœud du rail (iOS shadow / Android elevation).
    shadowOpacity: 0.5,
    shadowRadius: 5,
    shadowOffset: { width: 0, height: 0 },
    elevation: 4,
  },
  corps: {
    flex: 1,
    gap: spacing.sm,
  },
  badges: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  pastille: {
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
  },
  pastilleTexte: {
    ...typography.badge,
  },
  pastilleEcart: {
    backgroundColor: colors.accentWarmSoft,
    borderRadius: radius.pill,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
  },
  pastilleEcartTexte: {
    ...typography.badge,
    color: colors.accentWarm,
  },
  titre: {
    ...typography.readingBody,
    fontSize: 16,
    lineHeight: 23,
  },
});
