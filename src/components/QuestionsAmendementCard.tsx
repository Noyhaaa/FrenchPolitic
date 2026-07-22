import { ReactNode } from 'react';
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

/** Pastille numérotée (1..4) devant chaque question — miroir de QuestionsCard. */
function Numero({ n }: { n: number }) {
  return (
    <View style={styles.numero}>
      <Text style={styles.numeroTexte}>{n}</Text>
    </View>
  );
}

/** Une ligne question + réponse (texte, ou contenu libre via children). */
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
          <Text style={styles.reponse}>
            Ce vote s'est fait à main levée : il n'existe pas de ventilation par
            groupe ni par député.
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
  fracture: {
    marginTop: spacing.sm,
  },
});
