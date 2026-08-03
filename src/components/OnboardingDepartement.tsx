import { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { colors, radius, serifDisplay, spacing, typography } from '@/theme';
import { useDeputes } from '@/hooks';
import type { DeputeListItem } from '@/types';
import { IconLigne } from './IconLigne';

/**
 * Étape 4 — le département.
 *
 * ⚠️ La maquette proposait dix **régions**. Rien en base ne relie une région à
 * un élu : les parlementaires portent une circonscription en texte libre
 * (« Gironde, 4ᵉ circ. » à l'Assemblée, « Aveyron » au Sénat). La liste
 * affichée ici est donc **dérivée de l'annuaire réel** — aucun département
 * n'est écrit en dur, et aucun n'apparaît si aucun parlementaire ne s'y
 * rattache (§2.5).
 *
 * C'est aussi ce qui rend la promesse tenable : le département choisi ouvre
 * une vraie recherche dans l'annuaire, où la circonscription est indexée.
 */

/**
 * Département d'une circonscription : ce qui précède la virgule, sinon le
 * libellé entier (les sénateurs n'ont pas de numéro de circonscription).
 * Chaîne vide = non documentée → on ne devine pas, on écarte.
 */
export function departementDe(circonscription: string): string | null {
  const brut = circonscription.split(',')[0]?.trim();
  return brut ? brut : null;
}

function departements(deputes: DeputeListItem[]): string[] {
  const vus = new Set<string>();
  for (const d of deputes) {
    const dep = departementDe(d.circonscription);
    if (dep) vus.add(dep);
  }
  return [...vus].sort((a, b) => a.localeCompare(b, 'fr'));
}

interface Props {
  selection: string | null;
  onSelect: (departement: string | null) => void;
}

export function OnboardingDepartement({ selection, onSelect }: Props) {
  // Annuaire complet (sans filtre) : c'est la liste mise en cache, donc
  // disponible hors-ligne après un premier chargement.
  const { deputes, loading } = useDeputes('');
  const [filtre, setFiltre] = useState('');

  const liste = useMemo(() => departements(deputes), [deputes]);
  const visibles = useMemo(() => {
    const q = filtre.trim().toLowerCase();
    if (!q) return liste;
    return liste.filter((d) => d.toLowerCase().includes(q));
  }, [liste, filtre]);

  return (
    <View style={styles.bloc}>
      <View style={styles.entete}>
        <Text style={styles.titre}>Où votez-vous ?</Text>
        <Text style={styles.chapeau}>
          Votre département met vos parlementaires à portée de main. C’est
          facultatif, et modifiable à tout moment.
        </Text>

        <View style={styles.recherche}>
          <IconLigne name="loupe" color={colors.textTertiary} size={17} strokeWidth={1.7} />
          <TextInput
            value={filtre}
            onChangeText={setFiltre}
            placeholder="Chercher un département"
            placeholderTextColor={colors.textTertiary}
            autoCorrect={false}
            clearButtonMode="while-editing"
            accessibilityLabel="Chercher un département"
            style={styles.saisie}
          />
        </View>
      </View>

      {loading && liste.length === 0 ? (
        <View style={styles.attente}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.liste}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
        >
          {visibles.length === 0 ? (
            <Text style={styles.vide}>
              {liste.length === 0
                ? 'L’annuaire n’a pas pu être chargé. Vous pourrez choisir votre département plus tard depuis votre profil.'
                : 'Aucun département ne correspond.'}
            </Text>
          ) : (
            visibles.map((dep) => {
              const actif = selection === dep;
              return (
                <Pressable
                  key={dep}
                  // Re-toucher le département choisi le retire : le choix reste
                  // facultatif jusqu'au bout.
                  onPress={() => onSelect(actif ? null : dep)}
                  style={({ pressed }) => [
                    styles.ligne,
                    actif && styles.ligneActive,
                    pressed && styles.pressee,
                  ]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: actif }}
                  accessibilityLabel={`Département : ${dep}`}
                >
                  <IconLigne
                    name="epingle"
                    color={actif ? colors.brand : colors.textTertiary}
                    size={16}
                    strokeWidth={1.7}
                  />
                  <Text style={[styles.libelle, actif && styles.libelleActif]}>{dep}</Text>
                  {actif ? (
                    <IconLigne name="check" color={colors.brand} size={16} strokeWidth={2.2} />
                  ) : null}
                </Pressable>
              );
            })
          )}
        </ScrollView>
      )}
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
  recherche: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm + 2,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg - 2,
    paddingHorizontal: spacing.lg - 1,
    marginTop: spacing.sm,
  },
  saisie: { flex: 1, paddingVertical: spacing.md + 2, ...typography.body },
  attente: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  liste: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xl,
    gap: spacing.sm,
  },
  ligne: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingVertical: spacing.md + 2,
    paddingHorizontal: spacing.lg,
  },
  ligneActive: { borderColor: 'rgba(139,156,244,0.38)', backgroundColor: colors.brandSoft },
  pressee: { opacity: 0.85 },
  libelle: { ...typography.label, flex: 1, fontSize: 14, color: colors.textSecondary },
  libelleActif: { color: colors.textPrimary },
  vide: { ...typography.bodySecondary, color: colors.textTertiary },
});
