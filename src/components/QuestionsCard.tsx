import { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';
import type { ArgumentGroupe, PositionVote, QuestionsCitoyennes } from '@/types';
import { positionLabel } from '@/utils/format';
import { SourceLink } from './SourceLink';

interface Props {
  questions: QuestionsCitoyennes;
}

const COULEUR_SENS: Record<PositionVote, string> = {
  pour: colors.pour,
  contre: colors.contre,
  abstention: colors.abstention,
  non_votant: colors.textSecondary,
};

/** Pastille numérotée (1..4) devant chaque question. */
function Numero({ n }: { n: number }) {
  return (
    <View style={styles.numero}>
      <Text style={styles.numeroTexte}>{n}</Text>
    </View>
  );
}

/** Une ligne question + réponse (Q1/Q3/Q4). */
function QARow({
  n,
  question,
  reponse,
  children,
}: {
  n: number;
  question: string;
  reponse?: string;
  children?: ReactNode;
}) {
  return (
    <View style={styles.qrow}>
      <Numero n={n} />
      <View style={styles.qbody}>
        <Text style={styles.question}>{question}</Text>
        {children ??
          (reponse ? (
            <Text style={styles.reponse}>{reponse}</Text>
          ) : (
            <Text style={[styles.reponse, styles.indispo]}>
              Information non disponible.
            </Text>
          ))}
      </View>
    </View>
  );
}

/**
 * « Le vote en 4 questions » — l'entrée de compréhension de la fiche dossier
 * (§2.2 : comprendre en 30 s, §8 langage simple).
 *
 * Refonte lisibilité : chaque question est **numérotée** (pastille 1..4) et
 * suivie de sa réponse aérée, séparées par un filet fin — fini le mur de petits
 * labels. Le désaccord (Q2) devient des **cartes de groupe** : pastille de sens
 * + LIBELLÉ (jamais la couleur seule, §8/RGAA), nom du groupe, puis l'argument
 * qu'il a lui-même donné (§7.4), avec lien vers le compte rendu (§7.5).
 * Réponse absente → « Information non disponible » (§2.5).
 */
export function QuestionsCard({ questions }: Props) {
  const desaccord = questions.desaccord;
  return (
    <View style={styles.card}>
      <Text style={[typography.overline, styles.title]}>
        Le vote en 4 questions
      </Text>

      <QARow n={1} question="Pourquoi les députés ont-ils débattu ?" reponse={questions.pourquoi} />

      <View style={styles.sep} />

      <QARow n={2} question="Quel était le principal désaccord ?">
        {desaccord && desaccord.length > 0 ? (
          <>
            <View style={styles.groupes}>
              {desaccord.map((a: ArgumentGroupe, i) => (
                <View key={`${a.groupe}-${i}`} style={styles.groupe}>
                  <View style={styles.groupeEntete}>
                    <View
                      style={[styles.dot, { backgroundColor: COULEUR_SENS[a.sens] }]}
                      importantForAccessibility="no"
                    />
                    <Text style={styles.groupeNom} numberOfLines={1}>
                      {a.groupe}
                    </Text>
                    <Text style={[styles.sens, { color: COULEUR_SENS[a.sens] }]}>
                      {positionLabel(a.sens)}
                    </Text>
                  </View>
                  <Text style={styles.argument}>{a.argument}</Text>
                </View>
              ))}
            </View>
            {questions.desaccordSource ? (
              <View style={styles.source}>
                <SourceLink source={questions.desaccordSource} />
              </View>
            ) : null}
          </>
        ) : (
          <Text style={[styles.reponse, styles.indispo]}>
            Information non disponible.
          </Text>
        )}
      </QARow>

      <View style={styles.sep} />

      <QARow n={3} question="Quel est le résultat du vote ?" reponse={questions.resultat} />

      <View style={styles.sep} />

      <QARow n={4} question="Qu'est-ce que ça change concrètement ?" reponse={questions.changement} />
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
  qrow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  qbody: {
    flex: 1,
  },
  numero: {
    width: 26,
    height: 26,
    borderRadius: radius.pill,
    backgroundColor: colors.brandSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  numeroTexte: {
    ...typography.badge,
    fontSize: 12,
    color: colors.brand,
  },
  question: {
    fontSize: 15,
    lineHeight: 21,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  reponse: {
    marginTop: spacing.xs,
    fontSize: 15,
    lineHeight: 23,
    color: colors.textSecondary,
  },
  indispo: {
    fontStyle: 'italic',
  },
  groupes: {
    marginTop: spacing.sm,
    gap: spacing.sm,
  },
  groupe: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    paddingVertical: spacing.sm + 3,
    paddingHorizontal: spacing.md,
  },
  groupeEntete: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  dot: {
    width: 9,
    height: 9,
    borderRadius: 5,
  },
  groupeNom: {
    ...typography.label,
    color: colors.textPrimary,
    flexShrink: 1,
  },
  sens: {
    ...typography.badge,
    marginLeft: 'auto',
  },
  argument: {
    marginTop: spacing.xs + 2,
    fontSize: 13.5,
    lineHeight: 20,
    color: colors.textSecondary,
  },
  source: {
    marginTop: spacing.sm,
    alignSelf: 'flex-start',
  },
});
