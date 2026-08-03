import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';
import type { PositionGroupe, QuestionsAmendement } from '@/types';
import { LigneFracture } from './LigneFracture';
import { QARow, stylesQA } from './QARow';

interface Props {
  /** Absent si l'ingestion n'a pas (encore) généré les questions. */
  questions?: QuestionsAmendement;
  /** Positions des groupes du scrutin — porte le « qui était pour / contre ». */
  positionsGroupes: PositionGroupe[];
  /** false = vote à main levée : pas de ventilation par groupe (§5.2). */
  scrutinPublic: boolean;
  /** true = sous-amendement (libellés adaptés). */
  sous?: boolean;
}

/**
 * « L'amendement en 4 questions » — l'entrée de compréhension de la fiche vote
 * d'un amendement ou sous-amendement (§2.2 : comprendre en 30 s), adaptation
 * de la carte « Le vote en 4 questions » de la fiche dossier. Même refonte
 * lisibilité : questions **numérotées** (pastille 1..4), réponse aérée, filet
 * fin entre chacune.
 *
 * - « Pourquoi » vient de l'exposé sommaire : point de vue de l'auteur, la
 *   réponse commence par « Selon son auteur » (§4.3).
 * - « Qu'est-ce qu'il changerait ? » vient du dispositif officiel (validé
 *   côté backend), au conditionnel.
 * - « Qui était pour, qui était contre ? » est rendu depuis les positions des
 *   groupes du scrutin (déterministe, jamais généré) — l'unanimité s'affiche
 *   aussi : c'est une réponse factuelle, pas une absence d'information.
 * - « Résultat » est composé déterministiquement depuis le vote.
 * Réponse absente → « Information non disponible » (§2.5).
 */
export function QuestionsAmendementCard({
  questions,
  positionsGroupes,
  scrutinPublic,
  sous,
}: Props) {
  const quoi = sous ? 'ce sous-amendement' : 'cet amendement';
  return (
    <View style={styles.card}>
      <Text style={[typography.overline, styles.title]}>
        {sous ? 'Le sous-amendement' : "L'amendement"} en 4 questions
      </Text>

      <QARow n={1} question={`Pourquoi ${quoi} ?`} reponse={questions?.pourquoi} />

      <View style={styles.sep} />

      <QARow
        n={2}
        question="Qu'est-ce qu'il changerait ?"
        reponse={questions?.changement}
      />

      <View style={styles.sep} />

      <QARow n={3} question="Qui était pour, qui était contre ?">
        {scrutinPublic && positionsGroupes.length > 0 ? (
          <View style={styles.fracture}>
            <LigneFracture positionsGroupes={positionsGroupes} afficherUnanimite />
          </View>
        ) : (
          <Text style={stylesQA.reponse}>
            Ce vote s'est fait à main levée : il n'existe pas de ventilation par
            groupe ni par parlementaire.
          </Text>
        )}
      </QARow>

      <View style={styles.sep} />

      <QARow n={4} question="Quel est le résultat ?" reponse={questions?.resultat} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  title: {
    marginBottom: spacing.lg,
  },
  sep: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.lg,
  },
  fracture: {
    marginTop: spacing.sm,
  },
});
