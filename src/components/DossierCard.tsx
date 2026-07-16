import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';
import { DossierListItem } from '@/types';
import {
  formatDateRelative,
  formatTempsLecture,
  natureTexte,
} from '@/utils/format';
import { StatusBadge } from './StatusBadge';
import { ThemeAvatar } from './ThemeAvatar';
import { MiniResultat } from './MiniResultat';

interface Props {
  dossier: DossierListItem;
  onPress: (dossier: DossierListItem) => void;
}

/** Carte du fil (§3.1) — réutilisée aussi dans la recherche (§3.3). */
export function DossierCard({ dossier, onPress }: Props) {
  const nbVotes =
    dossier.nombreScrutins > 1
      ? `${dossier.nombreScrutins} votes`
      : `${dossier.nombreScrutins} vote`;

  return (
    <Pressable
      onPress={() => onPress(dossier)}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      accessibilityRole="button"
      accessibilityLabel={`${dossier.titreClair}. Thème ${dossier.theme}. ${nbVotes}.${
        dossier.miseAJour ? ` Mis à jour : ${dossier.miseAJour.label}.` : ''
      }`}
    >
      <View style={styles.header}>
        <ThemeAvatar theme={dossier.theme} />
        <StatusBadge statut={dossier.statut} />
        {dossier.miseAJour ? (
          <View style={styles.updateBadge} accessibilityElementsHidden>
            <Text style={styles.updateText}>🔄 Mis à jour</Text>
          </View>
        ) : null}
      </View>

      {/* Nature du texte (projet / proposition de loi…) si le titre la porte —
          l'utilisateur sait d'un coup d'œil ce qu'est le dossier. */}
      {natureTexte(dossier.titreClair) ? (
        <Text style={styles.nature}>{natureTexte(dossier.titreClair)}</Text>
      ) : null}
      <Text style={[typography.cardTitle, styles.title]}>{dossier.titreClair}</Text>

      <Text style={typography.bodySecondary} numberOfLines={2}>
        {dossier.accroche}
      </Text>

      {dossier.resultatDernierScrutin ? (
        <View style={styles.result}>
          <MiniResultat resultat={dossier.resultatDernierScrutin} />
        </View>
      ) : null}

      <Text style={[typography.meta, styles.meta]}>
        {formatDateRelative(dossier.date)} · {nbVotes} ·{' '}
        {formatTempsLecture(dossier.tempsLectureSec)}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    padding: spacing.xl,
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  pressed: {
    opacity: 0.85,
    transform: [{ scale: 0.995 }],
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  updateBadge: {
    marginLeft: 'auto',
    backgroundColor: colors.brandSoft,
    borderRadius: radius.pill,
    paddingVertical: 4,
    paddingHorizontal: spacing.md,
  },
  updateText: {
    ...typography.badge,
    color: colors.brand,
  },
  nature: {
    ...typography.overline,
    color: colors.textTertiary,
    marginTop: spacing.xs,
    marginBottom: -spacing.xs,
  },
  result: {
    marginTop: spacing.xs,
  },
  title: {
    marginTop: spacing.xs,
    fontSize: 19,
    lineHeight: 25,
  },
  meta: {
    marginTop: spacing.xs,
  },
});
