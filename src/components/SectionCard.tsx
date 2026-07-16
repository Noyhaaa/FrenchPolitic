import { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing, typography } from '@/theme';

interface Props {
  title?: string;
  children: ReactNode;
  /** Retire le fond « carte » pour un bloc transparent. */
  flat?: boolean;
}

/** Conteneur d'une section de la fiche scrutin (§3.2).
 * En-tête mono en capitales, comme les sections du prototype. */
export function SectionCard({ title, children, flat }: Props) {
  return (
    <View style={[styles.card, flat && styles.flat]}>
      {title ? (
        <Text style={[typography.overline, styles.title]}>{title}</Text>
      ) : null}
      {children}
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
  flat: {
    backgroundColor: 'transparent',
    borderWidth: 0,
    paddingHorizontal: 0,
  },
  title: {
    marginBottom: spacing.lg,
  },
});
