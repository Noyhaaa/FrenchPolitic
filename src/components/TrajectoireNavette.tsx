import { Fragment, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { termeGlossaire } from '@/constants/glossaire';
import { colors, radius, spacing, typography } from '@/theme';
import { EtatTexte, PhaseScrutin, StatutScrutin } from '@/types';
import { formatDateLong, libelleChambre, statutLabel } from '@/utils/format';
import { DefinitionGlossaire, MarqueurGlossaire } from './DefinitionGlossaire';

interface Props {
  phases: PhaseScrutin[];
  /** Où en est le texte aujourd'hui — absent = bloc de clôture masqué (§2.5). */
  etat?: EtatTexte | null;
}

/** Ce qu'on écrit pour un état donné : une affirmation, sa précision factuelle,
 * et le rappel de ce que la source ne dit pas. Jamais de phrase au futur. */
interface ContenuEtat {
  forte: string;
  statut: StatutScrutin;
  precision?: string;
  /** Ce que la source ne documente pas — dit explicitement plutôt que tu (§2.5). */
  mention?: string;
  /** Terme à expliquer ici, quand aucune pastille de la frise ne le porte. */
  terme?: string;
}

/**
 * Le texte du bloc « où en est le texte ? », état par état.
 *
 * ⚠️ Aucune de ces phrases n'annonce l'étape suivante, et c'est le cœur de la
 * règle : le calendrier parlementaire est une décision politique (inscription à
 * l'ordre du jour, convocation d'une CMP), pas une donnée qu'on pourrait lire
 * dans l'archive. Un texte encore en circulation reçoit donc son **dernier point
 * documenté**, suivi de ce que la source ne dit pas (§2.5).
 */
function contenuEtat(etat: EtatTexte): ContenuEtat | null {
  const date = etat.date ? formatDateLong(etat.date) : null;
  switch (etat.etat) {
    case 'promulgue': {
      // Le terme « Promulgation » est déjà expliqué par sa pastille dans la
      // frise juste au-dessus : pas de seconde aide au même endroit.
      const jo = etat.dateJournalOfficiel
        ? `, publiée au Journal officiel du ${formatDateLong(etat.dateJournalOfficiel)}`
        : '';
      const reference =
        etat.numeroLoi && date
          ? `Loi n° ${etat.numeroLoi} du ${date}${jo}.`
          : undefined;
      return { forte: "C'est la loi", statut: 'adopte', precision: reference };
    }
    case 'resolution':
      return {
        forte:
          etat.statut === 'rejete' ? 'Résolution rejetée' : 'Résolution adoptée',
        statut: etat.statut ?? 'adopte',
        precision: date ? `Le ${date}.` : undefined,
        // Seul état dont le mot-clé n'apparaît nulle part dans la frise (la
        // pastille dit « Lecture unique ») : c'est ici qu'il doit s'expliquer.
        terme: 'Résolution',
      };
    case 'retire':
      return {
        forte: 'Texte retiré par son auteur',
        statut: 'rejete',
        precision: date ? `Le ${date}.` : undefined,
      };
    case 'conseil_constitutionnel':
      return {
        forte: 'Devant le Conseil constitutionnel',
        statut: 'en_cours',
        precision: date ? `Saisi le ${date}.` : undefined,
        mention: "Sa décision n'est pas encore au dossier.",
      };
    case 'en_navette': {
      if (!etat.etape) return null;
      const chambre = etat.chambre ? `${libelleChambre(etat.chambre)} : ` : '';
      return {
        forte: "En cours d'examen",
        statut: 'en_cours',
        precision: `Dernière étape enregistrée — ${chambre}${etat.etape}${
          date ? `, le ${date}` : ''
        }.`,
        mention: "Aucune étape postérieure n'est publiée.",
      };
    }
  }
}

/** Icône + couleur par statut — jamais la couleur seule (RGAA §8) : le libellé
 * texte (« Adopté »…) accompagne toujours l'icône. */
const STATUT_UI: Record<StatutScrutin, { icon: string; color: string }> = {
  adopte: { icon: '✓', color: colors.adopte },
  rejete: { icon: '✕', color: colors.rejete },
  en_cours: { icon: '◷', color: colors.enCours },
};

/**
 * Frise de la trajectoire du texte **au Parlement** (fiche dossier) : les
 * étapes de la navette dans l'ordre chronologique — lectures à l'Assemblée ET
 * au Sénat, commission mixte paritaire, Conseil constitutionnel, promulgation.
 *
 * Elle est **calculée côté backend** (`Dossier.trajectoire`) depuis les actes
 * législatifs officiels du dossier : l'app ne peut pas la déduire des scrutins,
 * qui ne documentent que ce que chaque chambre a voté. Le statut d'une étape
 * n'est affiché que si la source le dit (§2.5 : une étape en cours s'affiche
 * avec sa seule date, on n'infère rien), et la chambre est écrite en toutes
 * lettres — jamais portée par la seule couleur (RGAA §8).
 *
 * Les libellés officiels sont du jargon (« Commission mixte paritaire »,
 * « Lecture définitive ») : une étape reconnue par le glossaire s'ouvre sur sa
 * définition, affichée SOUS la frise plutôt que dans la pastille, trop étroite
 * (§8). Étape non reconnue → pastille inerte, aucune explication devinée (§2.5).
 *
 * La frise, seule, ne raconte que le **passé** et laisse sans réponse la question
 * suivante : « et maintenant ? ». Elle se clôt donc sur l'**état actuel** du
 * texte (`Dossier.etat`), lu dans les mêmes actes officiels — promulgué, retiré,
 * devant le Conseil constitutionnel, résolution conclue, ou simplement la
 * dernière étape enregistrée. ⚠️ Jamais l'étape **suivante** : elle n'est pas
 * dans la source, et l'annoncer serait une prédiction (§2.5).
 */
export function TrajectoireNavette({ phases, etat }: Props) {
  // Une seule définition ouverte à la fois — pastilles ET bloc de clôture
  // partagent cet état : la carte reste lisible, et le lecteur compare les
  // étapes plutôt que d'empiler des pavés de texte.
  const [ouverte, setOuverte] = useState<string | null>(null);
  const clotureEtat = etat ? contenuEtat(etat) : null;
  if (phases.length === 0 && !clotureEtat) return null;
  const termeEtat = clotureEtat?.terme
    ? termeGlossaire(clotureEtat.terme)
    : undefined;
  return (
    <View style={styles.card}>
      <Text style={[typography.overline, styles.titre]}>
        Trajectoire au Parlement
      </Text>
      <View style={styles.steps}>
        {phases.map((p, i) => {
          const ui = p.statut ? STATUT_UI[p.statut] : null;
          const chambre = p.chambre ? libelleChambre(p.chambre) : null;
          const date = p.date ? formatDateLong(p.date) : null;
          // Une étape peut n'avoir ni statut ni date (rare) : on n'affiche
          // alors que son libellé officiel plutôt qu'une ligne vide.
          const detail = ui && p.statut ? statutLabel(p.statut) : date;
          const cle = `${p.label}-${p.chambre ?? 'commune'}`;
          const terme = termeGlossaire(p.label);
          const deplie = ouverte === cle;
          const description = [
            chambre ? `${chambre} :` : null,
            p.label,
            p.statut ? `: ${statutLabel(p.statut)}` : null,
            date ? `, ${date}` : null,
          ]
            .filter(Boolean)
            .join(' ');
          const contenu = (
            <>
              {chambre ? (
                <Text style={styles.stepChambre}>{chambre}</Text>
              ) : null}
              <View style={styles.stepTitre}>
                <Text style={styles.stepLabel}>{p.label}</Text>
                {terme ? <MarqueurGlossaire /> : null}
              </View>
              {ui && p.statut ? (
                <Text style={[styles.stepStatut, { color: ui.color }]}>
                  {ui.icon} {statutLabel(p.statut)}
                </Text>
              ) : detail ? (
                <Text style={styles.stepDate}>{detail}</Text>
              ) : null}
            </>
          );
          return (
            <Fragment key={cle}>
              {i > 0 ? (
                <Text style={styles.fleche} importantForAccessibility="no">
                  →
                </Text>
              ) : null}
              {terme ? (
                <Pressable
                  style={[styles.step, deplie && styles.stepOuverte]}
                  onPress={() => setOuverte(deplie ? null : cle)}
                  accessibilityRole="button"
                  accessibilityState={{ expanded: deplie }}
                  accessibilityLabel={`${description}. Définition de « ${terme.libelle} »`}
                >
                  {contenu}
                </Pressable>
              ) : (
                <View
                  style={styles.step}
                  accessibilityRole="text"
                  accessibilityLabel={description}
                >
                  {contenu}
                </View>
              )}
            </Fragment>
          );
        })}
      </View>
      {/* La définition de l'étape ouverte vit sous la frise : les pastilles
          s'enchaînent horizontalement et n'ont pas la place d'un paragraphe. */}
      {(() => {
        const active = phases.find(
          (p) => `${p.label}-${p.chambre ?? 'commune'}` === ouverte
        );
        const terme = active ? termeGlossaire(active.label) : undefined;
        return terme ? <DefinitionGlossaire terme={terme} /> : null;
      })()}

      {/* Clôture : où en est le texte aujourd'hui. La frise dit le passé, ce
          bloc dit le présent — et rien d'autre (§2.5). */}
      {clotureEtat ? (
        <View style={styles.etat}>
          <Text style={[typography.overline, styles.etatTitre]}>
            Où en est le texte ?
          </Text>
          <View style={styles.etatLigne}>
            {/* Glyphe + libellé : le statut n'est jamais porté par la seule
                couleur (RGAA §8). */}
            <Text
              style={[
                styles.etatForte,
                { color: STATUT_UI[clotureEtat.statut].color },
              ]}
            >
              {STATUT_UI[clotureEtat.statut].icon} {clotureEtat.forte}
            </Text>
            {termeEtat ? (
              <Pressable
                onPress={() => setOuverte(ouverte === 'etat' ? null : 'etat')}
                accessibilityRole="button"
                accessibilityState={{ expanded: ouverte === 'etat' }}
                accessibilityLabel={`Définition de « ${termeEtat.libelle} »`}
                hitSlop={8}
              >
                <MarqueurGlossaire />
              </Pressable>
            ) : null}
          </View>
          {clotureEtat.precision ? (
            <Text style={styles.etatPrecision}>{clotureEtat.precision}</Text>
          ) : null}
          {/* Ce que la source ne dit pas, dit explicitement — le lecteur sait
              alors que le silence est celui de l'archive, pas de l'app. */}
          {clotureEtat.mention ? (
            <Text style={styles.etatMention}>{clotureEtat.mention}</Text>
          ) : null}
          {ouverte === 'etat' && termeEtat ? (
            <DefinitionGlossaire terme={termeEtat} />
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
  },
  titre: {
    marginBottom: spacing.md,
  },
  steps: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: spacing.sm,
  },
  step: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    gap: 2,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  // L'étape dont la définition est ouverte : le lien entre la pastille et le
  // bloc sous la frise doit rester visible quand il y en a une dizaine.
  stepOuverte: {
    borderColor: colors.brand,
  },
  stepTitre: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  stepChambre: {
    ...typography.meta,
    color: colors.textTertiary,
  },
  stepLabel: {
    ...typography.label,
  },
  stepStatut: {
    ...typography.meta,
    fontWeight: '700',
  },
  stepDate: {
    ...typography.meta,
    color: colors.textTertiary,
  },
  fleche: {
    color: colors.textTertiary,
    fontSize: 16,
    fontWeight: '600',
  },
  // Séparé de la frise par un filet : ce n'est plus une étape de plus, c'est la
  // réponse à une autre question.
  etat: {
    marginTop: spacing.lg,
    paddingTop: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: spacing.xs,
  },
  etatTitre: {
    marginBottom: spacing.xs,
  },
  etatLigne: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  etatForte: {
    ...typography.readingBody,
    fontSize: 16,
    lineHeight: 22,
    fontWeight: '700',
  },
  etatPrecision: {
    ...typography.meta,
    color: colors.textSecondary,
  },
  etatMention: {
    ...typography.meta,
    color: colors.textTertiary,
  },
});
