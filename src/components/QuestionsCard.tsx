import { Fragment, ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';
import type { ArgumentGroupe, PositionVote, QuestionsCitoyennes } from '@/types';
import { libelleScrutin, positionLabel } from '@/utils/format';

interface Props {
  questions: QuestionsCitoyennes;
  /**
   * Le dossier est un événement autonome (motion de censure, déclaration) :
   * il n'a pas de texte, donc les questions qui portent sur un texte n'ont pas
   * d'objet. Voir `Dossier.estEvenementAutonome`.
   */
  evenementAutonome?: boolean;
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
 * qu'il a lui-même donné (§7.4). Réponse absente → « Information non
 * disponible » (§2.5).
 *
 * ⚠️ Aucun lien de source ici : ils vivent tous dans « Les documents du
 * dossier », en bas de fiche (§7.5). Ce qui reste, c'est le **nom** du document
 * dont sort la Q4 — lequel des trois a servi change le sens de la phrase.
 *
 * Les positions du désaccord sont celles exprimées sur UN vote précis, nommé
 * au-dessus d'elles : « pour » sur une motion de rejet préalable veut dire
 * « pour le rejet du texte », l'inverse de ce que le seul mot laisserait croire
 * (§7.4). Vote non reconnu par `libelleScrutin` → pas de ligne (§2.5), plutôt
 * que de recopier l'objet officiel entier.
 *
 * La Q2 dit exactement ce qu'elle montre, et rien de plus (§7.4) : son titre
 * suit les positions affichées (« désaccord » seulement s'il y a plusieurs sens
 * de vote), et une mention rappelle que la liste se limite aux groupes qui ont
 * pris la parole — mesuré en base, ils sont en moyenne 6 de moins que les
 * groupes ayant voté.
 */
export function QuestionsCard({ questions, evenementAutonome }: Props) {
  const desaccord = questions.desaccord;
  const objet = questions.desaccordObjet;
  const voteAncre = objet ? libelleScrutin(objet) : undefined;
  const libelleAncre =
    voteAncre && voteAncre.titre !== objet ? voteAncre.titre : undefined;
  // Le titre décrit ce qui est RÉELLEMENT à l'écran. Quand tous les groupes
  // affichés ont voté dans le même sens, parler de « désaccord » est faux — et
  // on ne le remplace pas par « unanimité », que cette liste ne prouve pas :
  // elle ne contient que les groupes qui ont pris la parole (§2.5). Sans
  // réponse, la question reste posée telle quelle : c'est le gabarit des 4
  // questions, et « information non disponible » y répond.
  const positions = desaccord ?? [];
  const unSeulSens =
    positions.length > 0 && new Set(positions.map((a) => a.sens)).size < 2;
  const questionDesaccord = unSeulSens
    ? 'Ce que les groupes ont dit'
    : 'Quel était le principal désaccord ?';
  // Les questions réellement posées. Sur un événement autonome (motion de
  // censure, déclaration), « pourquoi ce TEXTE » et « qu'est-ce que ça change »
  // n'ont pas d'objet : il n'y a pas de texte. On les retire au lieu de
  // répondre « information non disponible », qui ferait passer une absence de
  // sens pour une lacune de nos données (§2.5). Les restantes se renumérotent —
  // une pastille « 2 » sans « 1 » se lirait comme un bloc manquant.
  const blocs: { cle: string; rendu: (n: number) => ReactNode }[] = [];

  if (!evenementAutonome) {
    blocs.push({
      cle: 'pourquoi',
      rendu: (n) => (
        <QARow
          n={n}
          question="Pourquoi ce texte a-t-il été débattu ?"
          reponse={questions.pourquoi}
        />
      ),
    });
  }

  blocs.push({
    cle: 'desaccord',
    rendu: (n) => (
      <QARow n={n} question={questionDesaccord}>
        {desaccord && desaccord.length > 0 ? (
          <>
            {libelleAncre ? (
              <Text style={styles.ancre}>
                Positions exprimées lors du vote : {libelleAncre}
              </Text>
            ) : null}
            {/* Périmètre de la liste : seuls les groupes qui ont pris la parole
                ont un argument (explications de vote ou, à défaut, discussion
                générale — cf. `_construire_desaccord` côté ingestion). Sans
                cette mention, la carte se lit comme le panorama de l'hémicycle
                alors qu'elle n'en montre qu'une partie (§7.4). */}
            <Text style={styles.ancre}>
              Seuls les groupes qui se sont exprimés en séance figurent ici.
            </Text>
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
            {/* Le compte rendu de séance d'où sortent ces prises de parole est
                dans « Les documents du dossier », en bas de fiche — pas ici :
                la même URL deux fois sur une page n'ajoute rien (§7.5). Sa
                provenance, elle, reste écrite juste au-dessus (« exprimés en
                séance »). */}
          </>
        ) : (
          <Text style={[styles.reponse, styles.indispo]}>
            Information non disponible.
          </Text>
        )}
      </QARow>
    ),
  });

  blocs.push({
    cle: 'resultat',
    rendu: (n) => (
      <QARow n={n} question="Quel est le résultat du vote ?" reponse={questions.resultat} />
    ),
  });

  if (!evenementAutonome) {
    blocs.push({
      cle: 'changement',
      rendu: (n) => (
        // Q4 : la réponse vient du texte définitivement voté (la loi, à
        // l'indicatif), du dispositif du texte déposé (fait, au conditionnel)
        // ou, à défaut, de l'exposé des motifs (parole de l'auteur, signalée
        // par son préfixe §4.3).
        <QARow n={n} question="Qu'est-ce que ça change concrètement ?">
        {questions.changement ? (
          <>
            <Text style={styles.reponse}>{questions.changement}</Text>
            {/* Le NOM du document, pas son lien : celui-ci vit dans « Les
                documents du dossier » (§7.5). Mais lequel des trois a servi
                change le sens de la phrase — « le texte voté » décrit ce qui
                s'applique, « le texte déposé » une version que la navette a
                modifiée. Le taire laisserait les deux se lire pareil. */}
            {questions.changementSource ? (
              <Text style={styles.provenance}>
                D'après : {questions.changementSource.libelle}
              </Text>
            ) : null}
          </>
        ) : (
          <Text style={[styles.reponse, styles.indispo]}>
            Information non disponible.
          </Text>
        )}
        </QARow>
      ),
    });
  }

  return (
    <View style={styles.card}>
      <Text style={[typography.overline, styles.title]}>
        Le vote en {blocs.length} questions
      </Text>
      {blocs.map((bloc, i) => (
        <Fragment key={bloc.cle}>
          {i > 0 ? <View style={styles.sep} /> : null}
          {bloc.rendu(i + 1)}
        </Fragment>
      ))}
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
  ancre: {
    marginTop: spacing.xs,
    fontSize: 13,
    lineHeight: 19,
    color: colors.textTertiary,
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
  // Nom du document d'où sort la réponse — factuel, pas un lien (celui-ci vit
  // dans « Les documents du dossier »).
  provenance: {
    ...typography.meta,
    marginTop: spacing.sm,
    color: colors.textTertiary,
  },
});
