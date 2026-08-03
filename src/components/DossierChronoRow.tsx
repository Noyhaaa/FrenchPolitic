import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, mono, radius, serifDisplaySemi, spacing } from '@/theme';
import { DossierListItem, StatutScrutin } from '@/types';
import { formatDateRelative, libelleChambreCourt } from '@/utils/format';
import { ResultBar, segmentsMotionCensure } from './ResultBar';

/** Couleur du filet et de la pastille — le statut est toujours aussi porté par un texte. */
const COULEUR: Record<StatutScrutin, string> = {
  adopte: colors.adopte,
  rejete: colors.rejete,
  en_cours: colors.enCours,
};

interface Props {
  dossier: DossierListItem;
  /** Première ligne de son groupe : pas de trait au-dessus de la pastille. */
  premier?: boolean;
  /** Dernière ligne de son groupe : pas de trait en dessous. */
  dernier?: boolean;
  onPress: (dossier: DossierListItem) => void;
}

/**
 * Une entrée de la chronologie des dossiers (écran Dossiers).
 *
 * Format volontairement différent de `DossierCard` (le fil d'accueil) : pas de
 * carte, une colonne vertébrale de dates et un résultat réduit à son chiffre.
 * C'est ce qui fait qu'on reconnaît la page de résultats au premier regard.
 *
 * Quand le dernier vote n'était pas nominatif, la barre est REMPLACÉE par la
 * mention qui l'explique (§5.2) — on ne laisse jamais un vide inexpliqué, et on
 * n'affiche pas de barre que la source ne documente pas (§2.5).
 */
export function DossierChronoRow({ dossier, premier, dernier, onPress }: Props) {
  const couleur = COULEUR[dossier.statut];
  const resultat = dossier.resultatDernierScrutin;
  const chambre = dossier.chambres[dossier.chambres.length - 1];
  // ⚠️ Motion de censure : l'article 49 ne fait recenser que les voix
  // favorables, donc « 267 – 0 » se lirait comme une unanimité. On montre les
  // voix recueillies face au seuil, seul rapport qui décide (§7.4).
  const requises =
    dossier.typeVoteDernierScrutin === 'motion_censure'
      ? dossier.suffragesRequisDernierScrutin
      : undefined;

  const mention =
    dossier.nombreScrutins === 0
      ? 'Pas encore mis aux voix'
      : 'Vote à main levée — pas de nominatif';

  return (
    <Pressable
      onPress={() => onPress(dossier)}
      style={({ pressed }) => [styles.ligne, pressed && styles.pressed]}
      accessibilityRole="button"
      accessibilityLabel={
        dossier.titreClair +
        '. ' +
        formatDateRelative(dossier.date) +
        '. ' +
        (resultat
          ? requises
            ? resultat.pour + ' voix pour, ' + requises + ' requises.'
            : resultat.pour + ' pour, ' + resultat.contre + ' contre.'
          : mention + '.')
      }
    >
      <View style={styles.frise}>
        <View
          style={[
            styles.traitHaut,
            { backgroundColor: premier ? 'transparent' : colors.borderStrong },
          ]}
        />
        <View style={[styles.pastille, { borderColor: couleur }]} />
        {dernier ? null : <View style={styles.traitBas} />}
      </View>

      <View style={[styles.contenu, dernier && styles.contenuDernier]}>
        <Text style={[styles.date, { color: couleur }]}>
          {formatDateRelative(dossier.date)}
        </Text>
        <Text style={styles.titre}>{dossier.titreClair}</Text>

        <View style={styles.meta}>
          {chambre ? (
            <Text style={styles.chambre}>{libelleChambreCourt(chambre)}</Text>
          ) : null}
          {dossier.natureTexte ? (
            <Text style={styles.nature}>{dossier.natureTexte}</Text>
          ) : null}
        </View>

        {resultat ? (
          <View style={styles.resultat}>
            <View style={styles.barre}>
              <ResultBar
                height={4}
                segments={
                  requises
                    ? segmentsMotionCensure(resultat.pour, requises)
                    : [
                        { value: resultat.pour, color: colors.pour },
                        { value: resultat.contre, color: colors.contre },
                      ]
                }
              />
            </View>
            <Text style={styles.chiffres}>
              {resultat.pour}
              <Text style={styles.tiret}>{requises ? ' / ' : ' – '}</Text>
              {requises ?? resultat.contre}
            </Text>
          </View>
        ) : (
          <Text style={styles.mention}>{mention}</Text>
        )}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  ligne: { flexDirection: 'row', gap: spacing.lg - 2 },
  pressed: { opacity: 0.7 },
  frise: { width: 11, alignItems: 'center' },
  traitHaut: { width: 2, height: 19 },
  pastille: {
    width: 11,
    height: 11,
    borderRadius: radius.pill,
    borderWidth: 2.5,
    backgroundColor: colors.background,
  },
  traitBas: { flex: 1, width: 2, backgroundColor: colors.borderStrong },
  contenu: { flex: 1, paddingBottom: spacing.xl },
  contenuDernier: { paddingBottom: 0 },
  date: {
    fontFamily: mono,
    fontSize: 10,
    fontWeight: '600',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
    paddingTop: spacing.lg,
  },
  titre: {
    fontFamily: serifDisplaySemi,
    fontSize: 17.5,
    lineHeight: 23,
    letterSpacing: -0.2,
    color: colors.textPrimary,
    marginTop: 7,
  },
  meta: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 7,
    marginTop: 9,
  },
  chambre: {
    fontFamily: mono,
    fontSize: 10,
    fontWeight: '600',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    color: 'rgba(255,255,255,0.75)',
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm - 3,
    paddingVertical: 4,
    paddingHorizontal: 7,
  },
  nature: {
    fontFamily: mono,
    fontSize: 10,
    fontWeight: '500',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    color: colors.miniLabel,
  },
  resultat: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm + 2,
    marginTop: 11,
  },
  barre: { flex: 1 },
  chiffres: {
    fontFamily: mono,
    fontSize: 11.5,
    fontWeight: '700',
    letterSpacing: -0.2,
    color: colors.textPrimary,
  },
  tiret: { color: colors.textTertiary },
  mention: {
    fontFamily: mono,
    fontSize: 10.5,
    fontWeight: '500',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    color: colors.miniLabel,
    marginTop: 10,
  },
});
