import { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';

/**
 * Styles de la ligne question/réponse. Exportés parce que les appelants
 * rendent parfois leur propre contenu dans une `QARow` (une ligne de fracture,
 * une mention de vote à main levée) et doivent alors écrire un texte de réponse
 * identique à ceux que la ligne compose elle-même.
 */
export const stylesQA = StyleSheet.create({
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
});

/**
 * Une ligne « question + réponse » numérotée, partagée par les **deux** cartes
 * en 4 questions : « Le vote en 4 questions » (fiche dossier, `QuestionsCard`)
 * et « L'amendement en 4 questions » (fiche vote, `QuestionsAmendementCard`).
 *
 * Les deux cartes posent les mêmes questions à deux échelles différentes ; leur
 * ligne était écrite deux fois, les sept styles compris (à l'octet près). Une
 * seule définition, pour que la même app ne présente pas la même chose de deux
 * façons (§7.4) et qu'un ajustement de lisibilité s'applique aux deux d'un coup.
 *
 * Réponse absente → « Information non disponible » (§2.5 : jamais de
 * comblement). `children` permet de rendre autre chose qu'un texte.
 */
export function QARow({
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
    <View style={stylesQA.qrow}>
      <View style={stylesQA.numero}>
        <Text style={stylesQA.numeroTexte}>{n}</Text>
      </View>
      <View style={stylesQA.qbody}>
        <Text style={stylesQA.question}>{question}</Text>
        {children ??
          (reponse ? (
            <Text style={stylesQA.reponse}>{reponse}</Text>
          ) : (
            <Text style={[stylesQA.reponse, stylesQA.indispo]}>
              Information non disponible.
            </Text>
          ))}
      </View>
    </View>
  );
}
