import { colors } from '@/theme';
import type { Amendement } from '@/types';

/**
 * Sort d'un (sous-)amendement → libellé **et** couleur.
 *
 * Le libellé accompagne toujours la couleur : un statut n'est jamais porté par
 * la couleur seule (RGAA, §8). `fond` sert aux pastilles pleines (la ligne
 * d'amendement) ; les usages en texte simple n'en prennent que `label` et
 * `color`.
 *
 * Source unique : la même table vivait dans `AmendementRow` et dans
 * `ScrutinDetailScreen`, avec les mêmes clés et les mêmes libellés — deux
 * endroits pour dire « Adopté », donc deux endroits à corriger le jour où le
 * mot change.
 */
export const SORT_UI: Record<
  Amendement['sort'],
  { label: string; color: string; fond: string }
> = {
  adopte: { label: 'Adopté', color: colors.adopte, fond: colors.adopteSoft },
  rejete: { label: 'Rejeté', color: colors.contre, fond: colors.rejeteSoft },
  retire: {
    label: 'Retiré',
    color: colors.textTertiary,
    fond: colors.surfaceMuted,
  },
};
