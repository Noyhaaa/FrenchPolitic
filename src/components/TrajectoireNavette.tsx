import { Fragment, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { termeGlossaire } from '@/constants/glossaire';
import { colors, radius, spacing, typography } from '@/theme';
import { PhaseScrutin, StatutScrutin } from '@/types';
import { formatDateLong, libelleChambre, statutLabel } from '@/utils/format';
import { DefinitionGlossaire, MarqueurGlossaire } from './DefinitionGlossaire';

interface Props {
  phases: PhaseScrutin[];
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
 */
export function TrajectoireNavette({ phases }: Props) {
  // Une seule définition ouverte à la fois : la frise reste lisible, et le
  // lecteur compare les étapes plutôt que d'empiler des pavés de texte.
  const [ouverte, setOuverte] = useState<string | null>(null);
  if (phases.length === 0) return null;
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
});
