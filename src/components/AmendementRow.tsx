import { useState } from 'react';
import {
  LayoutAnimation,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  UIManager,
  View,
} from 'react-native';

import { colors, radius, serifItalic, spacing, typography } from '@/theme';
import type { Amendement } from '@/types';
import {
  cibleCourte,
  detailObjetAmendement,
  pointsDispositif,
  substitutionValeur,
} from '@/utils/format';

// Animation de dépliage fluide sur Android.
if (
  Platform.OS === 'android' &&
  UIManager.setLayoutAnimationEnabledExperimental
) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const SORT_UI = {
  adopte: { label: 'Adopté', color: colors.adopte, fond: colors.adopteSoft },
  rejete: { label: 'Rejeté', color: colors.contre, fond: colors.rejeteSoft },
  retire: {
    label: 'Retiré',
    color: colors.textTertiary,
    fond: colors.surfaceMuted,
  },
} as const;

/** Au-delà de ce nombre de lignes, l'exposé sommaire est replié (§8 : on ne
 *  noie pas la lecture sous un pavé — « Lire la suite » donne le texte entier). */
const LIGNES_CITATION = 3;

/** Longueur à partir de laquelle une citation dépasse `LIGNES_CITATION` sur un
 *  écran de téléphone : en deçà, inutile de proposer « Lire la suite ». */
const SEUIL_CITATION = 170;

/**
 * Une phrase courte et FACTUELLE pour la ligne repliée : première phrase du
 * dispositif (extrait officiel), sinon la partie descriptive de l'objet,
 * sinon l'objet complet. On extrait/tronque, on ne reformule jamais (§2.5).
 */
function resumeLigne(a: Amendement): string {
  const base = a.dispositif || detailObjetAmendement(a) || a.objet;
  const premiere = base.split('. ')[0].trim();
  return premiere && premiere.length < base.length ? `${premiere}.` : base;
}

/** Repère de localisation : « Art. 4 · n° 1071 ». Chaque partie est masquée si
 *  la donnée manque — on n'affiche pas de « — » à la place (§2.5). */
function repere(a: Amendement): string {
  return [a.cible ? cibleCourte(a.cible) : null, a.numero ? `n° ${a.numero}` : null]
    .filter(Boolean)
    .join(' · ');
}

/**
 * « Ce que ça change » : le FAIT, neutre. Quand le dispositif applique la
 * formule officielle de substitution de valeur, on met la comparaison en tête
 * (avant → après, la nouvelle valeur en pervenche) ; le détail suit, découpé
 * en points quand le texte lui-même énumère ses instructions. Repli (§2.5) :
 * aucune valeur détectée → le dispositif officiel s'affiche tel quel. Rien
 * n'est reformulé, tout est extrait verbatim.
 */
function CeQueCaChange({ dispositif }: { dispositif: string }) {
  const substitution = substitutionValeur(dispositif);
  const points = pointsDispositif(dispositif);

  return (
    <View style={styles.bloc}>
      <Text style={typography.overline}>Ce que ça change</Text>

      {substitution ? (
        <View
          style={styles.comparaison}
          accessibilityRole="text"
          accessibilityLabel={`Remplace ${substitution.avant} par ${substitution.apres}`}
        >
          <Text style={styles.valeurAvant}>{substitution.avant}</Text>
          <Text style={styles.fleche} importantForAccessibility="no">
            →
          </Text>
          <Text style={styles.valeurApres}>{substitution.apres}</Text>
        </View>
      ) : null}

      {points.length ? (
        <View style={styles.points}>
          {points.map((p, i) => (
            <View key={i} style={styles.point}>
              {/* Puce neutre : un « + » laisserait entendre un ajout, alors que
                  le point peut tout aussi bien supprimer ou remplacer (§4.3). */}
              <Text style={styles.puce} importantForAccessibility="no">
                •
              </Text>
              <Text style={styles.pointTexte}>{p}</Text>
            </View>
          ))}
        </View>
      ) : (
        <Text style={styles.corps}>{dispositif}</Text>
      )}
    </View>
  );
}

/**
 * « Pourquoi · selon l'auteur » : le POINT DE VUE, jamais fondu dans le texte
 * neutre (§4.3). Citation ambre italique, écourtée à trois lignes tant que le
 * lecteur n'a pas demandé la suite.
 */
function PourquoiAuteur({ exposeSommaire }: { exposeSommaire: string }) {
  const [tout, setTout] = useState(false);
  const long = exposeSommaire.length > SEUIL_CITATION;

  return (
    <View style={styles.bloc}>
      <Text style={typography.overline}>Pourquoi · selon l'auteur</Text>
      <Text
        style={styles.citation}
        numberOfLines={tout || !long ? undefined : LIGNES_CITATION}
      >
        {exposeSommaire}
      </Text>
      {long ? (
        <Pressable
          onPress={() => setTout((v) => !v)}
          accessibilityRole="button"
          accessibilityLabel={
            tout
              ? "Replier l'exposé sommaire"
              : "Lire tout l'exposé sommaire de l'auteur"
          }
        >
          <Text style={styles.lien}>{tout ? 'Replier' : 'Lire la suite'}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

interface Props {
  amendement: Amendement;
  /** Ouvre la fiche vote d'un scrutin (amendement OU sous-amendement). */
  onOpenScrutin?: (scrutinId: string) => void;
}

/**
 * Ligne d'amendement en « teaser éditorial » : pastille de verdict (couleur ET
 * libellé, §8) + repère de localisation, une phrase factuelle sur deux lignes,
 * l'auteur en italique. Au tap, la ligne se DÉPLIE en deux blocs distincts —
 * le FAIT (« Ce que ça change », dispositif neutre) puis la VOIX (« Pourquoi ·
 * selon l'auteur », exposé sommaire attribué, §4.3) — suivis du statut du vote
 * ET de ses sous-amendements imbriqués (connecteur ↳, tappables vers leur
 * propre vote). Plus de seconde liste de sous-amendements : la hiérarchie est
 * portée par le dépliage. Tout provient du libellé officiel (§2.5).
 */
export function AmendementRow({ amendement: a, onOpenScrutin }: Props) {
  const [ouvert, setOuvert] = useState(false);
  const sort = SORT_UI[a.sort];
  const sous = a.sousAmendements ?? [];
  const localisation = repere(a);

  const toggle = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setOuvert((v) => !v);
  };

  return (
    <View style={[styles.carte, ouvert && styles.carteOuverte]}>
      <Pressable
        onPress={toggle}
        style={styles.entete}
        accessibilityRole="button"
        accessibilityLabel={`${a.objet}. ${sort.label}. ${
          ouvert ? 'Masquer' : 'Voir'
        } le détail.`}
      >
        <View style={styles.enteteHaut}>
          <View style={[styles.verdict, { backgroundColor: sort.fond }]}>
            <View
              style={[styles.dot, { backgroundColor: sort.color }]}
              importantForAccessibility="no"
            />
            <Text style={[styles.verdictTexte, { color: sort.color }]}>
              {sort.label}
            </Text>
          </View>
          {localisation ? (
            <Text style={styles.repere}>{localisation}</Text>
          ) : null}
        </View>

        <Text style={styles.resume} numberOfLines={ouvert ? undefined : 2}>
          {resumeLigne(a)}
        </Text>

        <View style={styles.enteteBas}>
          {/* Auteur absent → on n'écrit rien à la place (§2.5) ; la ligne garde
              seulement son chevron. */}
          <Text style={styles.auteur} numberOfLines={1}>
            {[
              a.auteur,
              sous.length ? `${sous.length} sous-amend.` : null,
            ]
              .filter(Boolean)
              .join(' · ')}
          </Text>
          <Text
            style={[styles.caret, ouvert && styles.caretOuvert]}
            importantForAccessibility="no"
          >
            {ouvert ? '⌃' : '›'}
          </Text>
        </View>
      </Pressable>

      {ouvert ? (
        <View style={styles.panneau}>
          {a.dispositif ? <CeQueCaChange dispositif={a.dispositif} /> : null}
          {a.exposeSommaire ? (
            <PourquoiAuteur exposeSommaire={a.exposeSommaire} />
          ) : null}

          {/* Statut du vote de l'amendement. Le décompte (312 pour · 220
              contre) vit sur `ScrutinDetail` — l'objet `Amendement` ne le porte
              pas ; on n'invente pas de chiffres (§2.5). */}
          <View style={styles.piedVote}>
            <Text style={styles.statut}>{sort.label}</Text>
            {a.scrutinId && onOpenScrutin ? (
              <Pressable
                onPress={() => onOpenScrutin(a.scrutinId!)}
                accessibilityRole="button"
                accessibilityLabel="Voir le vote de cet amendement"
              >
                <Text style={styles.lien}>Voir le vote ›</Text>
              </Pressable>
            ) : null}
          </View>

          {sous.length ? (
            <View style={styles.sousWrap}>
              <Text style={[typography.overline, styles.sousTitre]}>
                {sous.length} sous-amendement{sous.length > 1 ? 's' : ''}
              </Text>
              {sous.map((sa) => {
                const s = SORT_UI[sa.sort];
                const contenu = (
                  <View style={styles.sousRow}>
                    <Text
                      style={styles.connecteur}
                      importantForAccessibility="no"
                    >
                      ↳
                    </Text>
                    <View
                      style={[styles.dotPetit, { backgroundColor: s.color }]}
                      importantForAccessibility="no"
                    />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.sousTexte}>{resumeLigne(sa)}</Text>
                      <Text style={typography.meta}>
                        n° {sa.numero ?? '—'} · {s.label.toLowerCase()}
                      </Text>
                    </View>
                  </View>
                );
                return sa.scrutinId && onOpenScrutin ? (
                  <Pressable
                    key={sa.id}
                    onPress={() => onOpenScrutin(sa.scrutinId!)}
                    style={({ pressed }) => pressed && { opacity: 0.7 }}
                    accessibilityRole="button"
                    accessibilityLabel={`${sa.objet}. ${s.label}. Voir le vote.`}
                  >
                    {contenu}
                  </Pressable>
                ) : (
                  <View key={sa.id}>{contenu}</View>
                );
              })}
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  carte: {
    marginHorizontal: -spacing.sm,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
  },
  carteOuverte: {
    backgroundColor: colors.surfaceMuted,
  },
  entete: {
    paddingVertical: spacing.md + 2,
    gap: spacing.sm,
  },
  enteteHaut: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  verdict: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderRadius: radius.pill,
    paddingVertical: 3,
    paddingHorizontal: spacing.sm,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  verdictTexte: {
    ...typography.badge,
  },
  repere: {
    ...typography.meta,
    flexShrink: 1,
  },
  resume: {
    ...typography.readingBody,
    fontSize: 17,
    lineHeight: 24,
  },
  enteteBas: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  auteur: {
    flex: 1,
    fontFamily: serifItalic,
    fontStyle: 'italic',
    fontSize: 14,
    lineHeight: 20,
    color: colors.textSecondary,
  },
  caret: {
    color: colors.textTertiary,
    fontSize: 22,
    fontWeight: '600',
  },
  caretOuvert: {
    color: colors.brand,
    fontSize: 15,
  },
  panneau: {
    paddingBottom: spacing.md,
    gap: spacing.lg,
  },
  bloc: {
    gap: spacing.sm,
  },
  comparaison: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  valeurAvant: {
    ...typography.label,
    fontFamily: typography.meta.fontFamily,
    fontSize: 14,
    color: colors.textTertiary,
    textDecorationLine: 'line-through',
  },
  fleche: {
    ...typography.label,
    color: colors.textTertiary,
  },
  valeurApres: {
    ...typography.label,
    fontFamily: typography.meta.fontFamily,
    fontSize: 14,
    color: colors.brand,
    backgroundColor: colors.brandSoft,
    borderRadius: radius.sm,
    paddingVertical: 2,
    paddingHorizontal: 6,
    overflow: 'hidden',
  },
  corps: {
    ...typography.readingBody,
    color: colors.textSecondary,
  },
  points: {
    gap: spacing.sm,
  },
  point: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  puce: {
    ...typography.readingBody,
    color: colors.textTertiary,
  },
  pointTexte: {
    ...typography.readingBody,
    flex: 1,
    color: colors.textSecondary,
  },
  citation: {
    ...typography.readingQuote,
    color: colors.accentWarm,
    borderLeftWidth: 2,
    borderLeftColor: colors.accentWarmSoft,
    paddingLeft: spacing.md,
  },
  piedVote: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  statut: {
    ...typography.meta,
    color: colors.textSecondary,
  },
  lien: {
    ...typography.meta,
    color: colors.brand,
    fontWeight: '600',
  },
  sousWrap: {
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  sousTitre: {
    marginBottom: spacing.sm,
  },
  sousRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    paddingVertical: spacing.sm - 2,
  },
  connecteur: {
    color: colors.textTertiary,
    fontFamily: typography.meta.fontFamily,
    fontSize: 13,
    lineHeight: 22,
  },
  dotPetit: {
    width: 7,
    height: 7,
    borderRadius: 4,
    marginTop: 8,
  },
  sousTexte: {
    ...typography.readingBody,
    fontSize: 15,
    lineHeight: 21,
  },
});
