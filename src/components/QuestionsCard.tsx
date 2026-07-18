import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';
import type { ArgumentGroupe, PositionVote, QuestionsCitoyennes } from '@/types';
import { positionLabel } from '@/utils/format';
import { SourceLink } from './SourceLink';

interface Props {
  questions: QuestionsCitoyennes;
}

/** Les 3 questions à réponse textuelle (Q2 « désaccord » est rendue à part). */
const ENTREES_TEXTE: { cle: 'pourquoi' | 'resultat' | 'changement'; question: string }[] = [
  { cle: 'pourquoi', question: 'Pourquoi les députés ont-ils débattu ?' },
  { cle: 'resultat', question: 'Quel est le résultat du vote ?' },
  { cle: 'changement', question: 'Qu’est-ce que ça change concrètement ?' },
];

const COULEUR_SENS: Record<PositionVote, string> = {
  pour: colors.pour,
  contre: colors.contre,
  abstention: colors.abstention,
  non_votant: colors.textSecondary,
};

/** Une réponse texte (Q1/Q3/Q4) ou « information non disponible » (§2.5). */
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
 * Q2 « principal désaccord » : les positions que **les groupes formulent
 * eux-mêmes** en explication de vote. Même gabarit pour chaque groupe (§7.4) :
 * pastille de sens (jamais la couleur seule — libellé texte, §8/RGAA), nom du
 * groupe, puis son argument. Le sens vient du scrutin ; l'argument est la
 * paraphrase neutre validée de ses mots. Aucune synthèse de notre part.
 */
function Desaccord({ arguments: args }: { arguments: ArgumentGroupe[] }) {
  return (
    <View>
      <Text style={styles.question}>Quel était le principal désaccord ?</Text>
      <View style={styles.positions}>
        {args.map((a, i) => (
          <View key={`${a.groupe}-${i}`} style={styles.position}>
            <View style={styles.positionEntete}>
              <View
                style={[styles.pastille, { backgroundColor: COULEUR_SENS[a.sens] }]}
                importantForAccessibility="no"
              />
              <Text style={styles.groupe}>{a.groupe}</Text>
              <Text style={[styles.sens, { color: COULEUR_SENS[a.sens] }]}>
                {positionLabel(a.sens)}
              </Text>
            </View>
            <Text style={typography.body}>{a.argument}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

/**
 * « Le vote en 4 questions » — l'entrée de compréhension de la fiche dossier
 * (§2.2 : comprendre en 30 s, langage simple §8).
 *
 * Réponses ancrées sur une source officielle ; une réponse absente affiche
 * « Information non disponible » (§2.5). « Changement » commence par « Selon
 * l'auteur du texte » (point de vue du déposant, §4.3) ; « désaccord » juxtapose
 * les explications de vote **attribuées** aux groupes (§7.4), avec lien vers le
 * compte rendu (§7.5).
 */
export function QuestionsCard({ questions }: Props) {
  const desaccord = questions.desaccord;
  return (
    <View style={styles.card}>
      <Text style={[typography.overline, styles.title]}>
        Le vote en 4 questions
      </Text>
      <View style={styles.list}>
        <ReponseTexte question={ENTREES_TEXTE[0].question} reponse={questions.pourquoi} />

        {desaccord && desaccord.length > 0 ? (
          <View>
            <Desaccord arguments={desaccord} />
            {questions.desaccordSource ? (
              <View style={styles.source}>
                <SourceLink source={questions.desaccordSource} />
              </View>
            ) : null}
          </View>
        ) : (
          <ReponseTexte question="Quel était le principal désaccord ?" />
        )}

        <ReponseTexte question={ENTREES_TEXTE[1].question} reponse={questions.resultat} />
        <ReponseTexte question={ENTREES_TEXTE[2].question} reponse={questions.changement} />
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
  positions: {
    gap: spacing.md,
  },
  position: {
    gap: 2,
  },
  positionEntete: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  pastille: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  groupe: {
    ...typography.label,
    flexShrink: 1,
  },
  sens: {
    ...typography.meta,
    marginLeft: 'auto',
    fontWeight: '600',
  },
  source: {
    marginTop: spacing.md,
    alignSelf: 'flex-start',
  },
});
