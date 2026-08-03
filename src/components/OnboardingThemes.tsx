import { useMemo } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, mono, serifDisplay, spacing, typography } from '@/theme';
import { themeEmoji } from '@/constants/themes';
import { useThemes } from '@/hooks';
import type { ThemeScrutin } from '@/types';
import { Chip } from './Chip';
import { BarreProgression } from './ProgressionEtapes';

/**
 * Étape 3 — les thèmes suivis.
 *
 * Les catégories proposées sont **celles qui existent réellement en base**
 * (`GET /themes`, via `useThemes`), avec leur nombre de dossiers : proposer un
 * thème vide ferait promettre un fil qu'on n'a pas (§2.5). Hors-ligne, la liste
 * est vide et l'étape le dit — elle n'invente pas de catalogue.
 *
 * Ce que le choix fait est écrit noir sur blanc : il **remonte** des rangées de
 * l'accueil, il n'en cache aucune. Rien n'est filtré, rien n'est masqué.
 */

export const THEMES_MINIMUM = 3;

interface Props {
  selection: ThemeScrutin[];
  onToggle: (theme: ThemeScrutin) => void;
}

export function OnboardingThemes({ selection, onToggle }: Props) {
  const themes = useThemes();

  // Les plus fournis d'abord : la première rangée montre ce sur quoi l'app a
  // le plus à dire. `useThemes` renvoie déjà les décomptes réels.
  const ordonnes = useMemo(
    () => [...themes].sort((a, b) => b.nombre - a.nombre),
    [themes],
  );

  const restants = Math.max(0, THEMES_MINIMUM - selection.length);

  return (
    <View style={styles.bloc}>
      <View style={styles.entete}>
        <Text style={styles.titre}>Quels sujets vous intéressent ?</Text>
        <Text style={styles.chapeau}>
          Choisissez-en au moins {THEMES_MINIMUM}. Vos thèmes passent en tête de
          l’accueil — aucun autre n’est masqué pour autant.
        </Text>
        <BarreProgression part={selection.length / THEMES_MINIMUM} />
        <Text style={styles.compteur}>
          {selection.length} choisi{selection.length > 1 ? 's' : ''} ·{' '}
          {restants > 0 ? `${restants} de plus` : 'minimum atteint'}
        </Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.grille}
        showsVerticalScrollIndicator={false}
      >
        {ordonnes.length === 0 ? (
          <Text style={styles.vide}>
            Les catégories n’ont pas pu être chargées. Vous pourrez les choisir plus
            tard depuis votre profil.
          </Text>
        ) : (
          ordonnes.map((t) => {
            const theme = t.nom as ThemeScrutin;
            return (
              <Chip
                key={t.nom}
                large
                actif={selection.includes(theme)}
                label={`${t.nom} · ${t.nombre}`}
                emoji={themeEmoji[theme] ?? themeEmoji.Autre}
                action="Suivre le thème"
                onPress={() => onToggle(theme)}
              />
            );
          })
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  bloc: { flex: 1 },
  entete: { paddingHorizontal: spacing.xl, gap: spacing.sm },
  titre: {
    fontFamily: serifDisplay,
    fontSize: 30,
    lineHeight: 36,
    letterSpacing: -0.5,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  chapeau: { ...typography.bodySecondary },
  compteur: {
    fontFamily: mono,
    fontSize: 10.5,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    color: colors.brand,
  },
  grille: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm + 2,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xl,
  },
  vide: { ...typography.bodySecondary, color: colors.textTertiary },
});
