import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';
import type { PositionGroupe, QuestionsAmendement } from '@/types';
import { LigneFracture } from './LigneFracture';

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

/** Une réponse texte ou « information non disponible » (§2.5). */
function ReponseTexte({ question, reponse }: { question: string; reponse?: string }) {
  return (
    <View>
      <Text style={styles.question}>{question}</Text>
      {reponse ? (
        <Text style={typography.body}>{reponse}</Text>
      ) : (
        <Text style={[typography.bodySecondary, styles.indisponible]}>
          Information non disponible.
        </Text>
      )}
    </View>
  );
}

/**
 * « L'amendement en 4 questions » — l'entrée de compréhension de la fiche vote
 * d'un amendement ou sous-amendement (§2.2 : comprendre en 30 s), adaptation
 * de la carte « Le vote en 4 questions » de la fiche dossier.
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
      <View style={styles.list}>
        <ReponseTexte
          question={`Pourquoi ${quoi} ?`}
          reponse={questions?.pourquoi}
        />
        <ReponseTexte
          question="Qu'est-ce qu'il changerait ?"
          reponse={questions?.changement}
        />

        <View>
          <Text style={styles.question}>Qui était pour, qui était contre ?</Text>
          {scrutinPublic && positionsGroupes.length > 0 ? (
            <View style={styles.fracture}>
              <LigneFracture
                positionsGroupes={positionsGroupes}
                afficherUnanimite
              />
            </View>
          ) : (
            <Text style={typography.bodySecondary}>
              Ce vote s'est fait à main levée : il n'existe pas de ventilation
              par groupe ni par député.
            </Text>
          )}
        </View>

        <ReponseTexte
          question="Quel est le résultat ?"
          reponse={questions?.resultat}
        />
      </View>
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
    marginBottom: spacing.md,
  },
  list: {
    gap: spacing.lg,
  },
  question: {
    ...typography.label,
    color: colors.brand,
    marginBottom: spacing.xs,
  },
  indisponible: {
    fontStyle: 'italic',
  },
  fracture: {
    marginTop: spacing.xs,
  },
});
