import type { DossierListItem } from '@/types';

/** Un groupe de la chronologie : « Cette semaine », « Plus tôt en juillet »… */
export interface PeriodeDossiers {
  cle: string;
  label: string;
  data: DossierListItem[];
}

function debutDeJour(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function capitale(texte: string) {
  return texte.charAt(0).toUpperCase() + texte.slice(1);
}

/**
 * Groupe les dossiers par période, du plus récent au plus ancien — la forme
 * attendue par la `SectionList` de l'écran Dossiers.
 *
 * Le tri est fait ICI, une seule fois, à partir de `dossier.date` : les
 * libellés de groupe et l'ordre des lignes ne peuvent donc pas se contredire.
 * Un dossier de moins de 7 jours va dans « Cette semaine » ; les autres sont
 * regroupés par mois (l'année n'apparaît que si ce n'est pas l'année en cours).
 */
export function grouperParPeriode(
  dossiers: DossierListItem[],
  now: Date = new Date(),
): PeriodeDossiers[] {
  const aujourdhui = debutDeJour(now);
  const groupes = new Map<string, PeriodeDossiers>();

  const tries = [...dossiers].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
  );

  for (const dossier of tries) {
    const d = new Date(dossier.date);
    const jours = Math.round((aujourdhui - debutDeJour(d)) / 86_400_000);

    let cle: string;
    let label: string;
    if (jours < 7) {
      cle = 'semaine';
      label = 'Cette semaine';
    } else {
      cle = d.getFullYear() + '-' + d.getMonth();
      const mois = d.toLocaleDateString('fr-FR', { month: 'long' });
      label =
        d.getFullYear() === now.getFullYear()
          ? d.getMonth() === now.getMonth()
            ? 'Plus tôt en ' + mois
            : capitale(mois)
          : capitale(mois) + ' ' + d.getFullYear();
    }

    const groupe = groupes.get(cle);
    if (groupe) groupe.data.push(dossier);
    else groupes.set(cle, { cle, label, data: [dossier] });
  }

  return [...groupes.values()];
}
