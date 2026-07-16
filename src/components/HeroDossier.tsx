import { Pressable, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { colors, mono, radius, serif, spacing, typography } from '@/theme';
import { DossierListItem, StatutScrutin } from '@/types';
import { themeEmoji, themeTintDark } from '@/constants/themes';
import { formatDateRelative, natureTexte } from '@/utils/format';
import { statutLabel } from '@/utils/format';
import { MiniResultat } from './MiniResultat';

interface Props {
  dossier: DossierListItem;
  onPress: (dossier: DossierListItem) => void;
  /** Hauteur de la zone superposée (nav) : le contenu du hero s'en écarte. */
  topInset: number;
}

const STATUT_FG: Record<StatutScrutin, string> = {
  adopte: colors.adopte,
  rejete: colors.rejete,
  en_cours: colors.enCours,
};

/**
 * Dossier « à la une », plein écran en tête du fil (le hero du prototype).
 * À défaut de photo (on n'invente pas d'illustration, §2.5) : tuile teintée
 * par thème + emoji en filigrane, fondue dans le fond par un dégradé.
 * Surtitre = statut factuel (pas de « live » : nos données ne le sont pas).
 */
export function HeroDossier({ dossier, onPress, topInset }: Props) {
  const nature = natureTexte(dossier.titreClair);
  const statutFg = STATUT_FG[dossier.statut];

  return (
    <Pressable
      onPress={() => onPress(dossier)}
      style={[
        styles.hero,
        {
          backgroundColor: themeTintDark[dossier.theme] ?? themeTintDark.Autre,
          paddingTop: topInset,
        },
      ]}
      accessibilityRole="button"
      accessibilityLabel={`À la une : ${dossier.titreClair}. ${statutLabel(
        dossier.statut,
      )}. Ouvrir le dossier.`}
    >
      <Text style={styles.watermark} importantForAccessibility="no">
        {themeEmoji[dossier.theme] ?? themeEmoji.Autre}
      </Text>
      <LinearGradient
        colors={['transparent', 'rgba(20,20,20,0.75)', colors.background]}
        locations={[0, 0.55, 1]}
        style={StyleSheet.absoluteFill}
      />

      <View style={styles.content}>
        {/* Surtitre : statut factuel + institution (mono, comme le prototype) */}
        <View style={styles.overlineRow}>
          <View style={[styles.statutDot, { backgroundColor: statutFg }]} />
          <Text style={[styles.overlineStatut, { color: statutFg }]}>
            {statutLabel(dossier.statut)}
          </Text>
          <Text style={styles.overlineRest}>
            · {nature ?? 'Assemblée nationale'}
          </Text>
        </View>

        <Text style={styles.title} numberOfLines={3}>
          {dossier.titreClair}
        </Text>

        <Text style={[typography.bodySecondary, styles.accroche]} numberOfLines={2}>
          {dossier.accroche}
        </Text>

        {dossier.resultatDernierScrutin ? (
          <View style={styles.barWrap}>
            <MiniResultat resultat={dossier.resultatDernierScrutin} height={5} />
          </View>
        ) : null}

        <View style={styles.actions}>
          <View style={styles.cta}>
            <Text style={styles.ctaText}>Lire le dossier</Text>
          </View>
          {dossier.miseAJour ? (
            <View style={styles.updateBadge} accessibilityElementsHidden>
              <Text style={styles.updateText}>🔄 Mis à jour</Text>
            </View>
          ) : null}
          <Text style={[typography.meta, styles.date]}>
            {formatDateRelative(dossier.date)}
          </Text>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  hero: {
    minHeight: 300,
    justifyContent: 'flex-end',
  },
  watermark: {
    position: 'absolute',
    top: spacing.xxxl,
    right: -spacing.md,
    fontSize: 150,
    opacity: 0.16,
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xl,
    paddingTop: spacing.xxxl,
    gap: spacing.md,
  },
  overlineRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  statutDot: {
    width: 7,
    height: 7,
    borderRadius: radius.pill,
  },
  overlineStatut: {
    fontSize: 11,
    fontWeight: '700',
    fontFamily: mono,
    letterSpacing: 1.6,
    textTransform: 'uppercase',
  },
  overlineRest: {
    fontSize: 11,
    fontFamily: mono,
    color: colors.textSecondary,
  },
  title: {
    fontSize: 27,
    lineHeight: 33,
    fontWeight: '900',
    fontFamily: serif,
    color: colors.textPrimary,
  },
  accroche: {
    color: colors.textSecondary,
  },
  barWrap: {
    maxWidth: 250,
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingTop: spacing.xs,
  },
  cta: {
    backgroundColor: colors.textPrimary,
    borderRadius: radius.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  ctaText: {
    ...typography.label,
    color: colors.textOnLight,
    fontWeight: '700',
  },
  updateBadge: {
    backgroundColor: colors.brandSoft,
    borderRadius: radius.pill,
    paddingVertical: 4,
    paddingHorizontal: spacing.md,
  },
  updateText: {
    ...typography.badge,
    color: colors.brand,
  },
  date: {
    marginLeft: 'auto',
  },
});
