import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import type { Amendement } from '@/types';
import { AmendementRow } from './AmendementRow';

type Filtre = 'tous' | 'adopte' | 'rejete' | 'retire';

const SEGMENTS = [
  { k: 'adopte', couleur: colors.adopte, label: 'adoptés' },
  { k: 'rejete', couleur: colors.contre, label: 'rejetés' },
  { k: 'retire', couleur: colors.textTertiary, label: 'retirés' },
] as const;

/** Nombre d'amendements montrés avant le bouton « Voir les N autres »
 *  (3 = ce que présente l'écran 2a ; monte-le si tu veux en montrer plus). */
const APERCU = 3;

interface Props {
  amendements: Amendement[];
  /** Ouvre la fiche vote d'un scrutin (amendement ou sous-amendement). */
  onOpenScrutin?: (scrutinId: string) => void;
}

function Chip({
  actif,
  label,
  onPress,
}: {
  actif: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.chip, actif && styles.chipActif]}
      accessibilityRole="button"
      accessibilityState={{ selected: actif }}
    >
      <Text style={[styles.chipTexte, actif && styles.chipTexteActif]}>
        {label}
      </Text>
    </Pressable>
  );
}

/**
 * Section « Amendements » de la fiche dossier. Dé-densifie une liste qui peut
 * compter des dizaines d'entrées : une barre de synthèse (part de chaque sort)
 * + des compteurs donnent l'ensemble d'un coup d'œil, des filtres réduisent la
 * liste, et chaque amendement tient sur une ligne calme (voir `AmendementRow`)
 * qui se déplie à la demande — sous-amendements révélés au dépliage, pas de
 * seconde liste. Les longues listes sont écrêtées à `APERCU` (« Voir les N
 * autres »). Aucune couleur ne porte seule l'information (§8/RGAA).
 */
export function AmendementsSection({ amendements, onOpenScrutin }: Props) {
  const [filtre, setFiltre] = useState<Filtre>('tous');
  const [tout, setTout] = useState(false);

  const compte = useMemo(
    () => ({
      adopte: amendements.filter((a) => a.sort === 'adopte').length,
      rejete: amendements.filter((a) => a.sort === 'rejete').length,
      retire: amendements.filter((a) => a.sort === 'retire').length,
    }),
    [amendements],
  );

  if (amendements.length === 0) return null;

  const filtree =
    filtre === 'tous'
      ? amendements
      : amendements.filter((a) => a.sort === filtre);
  const visibles = tout ? filtree : filtree.slice(0, APERCU);

  return (
    <View style={styles.card}>
      <Text style={[typography.overline, styles.titre]}>
        Amendements ({amendements.length})
      </Text>

      {/* Barre de synthèse */}
      <View style={styles.barre}>
        {SEGMENTS.map((s) =>
          compte[s.k] ? (
            <View
              key={s.k}
              style={{ flex: compte[s.k], backgroundColor: s.couleur }}
            />
          ) : null,
        )}
      </View>
      <View style={styles.legende}>
        {SEGMENTS.map((s) =>
          compte[s.k] ? (
            <View key={s.k} style={styles.legItem}>
              <View style={[styles.pastille, { backgroundColor: s.couleur }]} />
              <Text style={styles.legTexte}>
                {compte[s.k]} {s.label}
              </Text>
            </View>
          ) : null,
        )}
      </View>

      {/* Filtres */}
      <View style={styles.filtres}>
        <Chip
          actif={filtre === 'tous'}
          onPress={() => setFiltre('tous')}
          label={`Tous · ${amendements.length}`}
        />
        {compte.adopte ? (
          <Chip
            actif={filtre === 'adopte'}
            onPress={() => setFiltre('adopte')}
            label="Adoptés"
          />
        ) : null}
        {compte.rejete ? (
          <Chip
            actif={filtre === 'rejete'}
            onPress={() => setFiltre('rejete')}
            label="Rejetés"
          />
        ) : null}
      </View>

      {/* Liste épurée */}
      <View style={styles.liste}>
        {visibles.map((a, i) => (
          <View key={a.id} style={i > 0 ? styles.sep : undefined}>
            <AmendementRow amendement={a} onOpenScrutin={onOpenScrutin} />
          </View>
        ))}
      </View>

      {filtree.length > APERCU ? (
        <Pressable
          onPress={() => setTout((v) => !v)}
          accessibilityRole="button"
          accessibilityLabel={
            tout
              ? 'Réduire la liste des amendements'
              : `Voir les ${filtree.length - APERCU} autres amendements`
          }
        >
          <Text style={styles.voirPlus}>
            {tout
              ? 'Réduire la liste ▲'
              : `Voir les ${filtree.length - APERCU} autres ▼`}
          </Text>
        </Pressable>
      ) : null}
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
  titre: {
    marginBottom: spacing.md,
  },
  barre: {
    flexDirection: 'row',
    height: 8,
    borderRadius: radius.pill,
    overflow: 'hidden',
  },
  legende: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
    marginTop: spacing.sm + 2,
  },
  legItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  pastille: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  legTexte: {
    ...typography.meta,
    color: colors.textSecondary,
  },
  filtres: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: spacing.lg,
  },
  chip: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    paddingVertical: 6,
    paddingHorizontal: 13,
  },
  chipActif: {
    backgroundColor: colors.textPrimary,
  },
  chipTexte: {
    ...typography.label,
    color: colors.textSecondary,
  },
  chipTexteActif: {
    color: colors.textOnLight,
  },
  liste: {
    marginTop: spacing.md,
  },
  sep: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  voirPlus: {
    ...typography.meta,
    color: colors.brand,
    fontWeight: '600',
    paddingTop: spacing.md,
  },
});
