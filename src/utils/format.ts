import { StatutScrutin, PositionVote } from '@/types';

/** Libellé texte du statut (jamais la couleur seule — RGAA §8). */
export function statutLabel(statut: StatutScrutin): string {
  switch (statut) {
    case 'adopte':
      return 'Adopté';
    case 'rejete':
      return 'Rejeté';
    case 'en_cours':
      return 'En discussion';
  }
}

export function positionLabel(position: PositionVote): string {
  switch (position) {
    case 'pour':
      return 'Pour';
    case 'contre':
      return 'Contre';
    case 'abstention':
      return 'Abstention';
    case 'non_votant':
      return 'Non-votant';
  }
}

/** Date relative simple et lisible (« Aujourd'hui », « Hier », « 6 juil. »). */
export function formatDateRelative(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const startOf = (x: Date) =>
    new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.round((startOf(now) - startOf(d)) / 86_400_000);

  if (diffDays <= 0) return "Aujourd'hui";
  if (diffDays === 1) return 'Hier';
  if (diffDays < 7) return `Il y a ${diffDays} jours`;

  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}

/** « 8 juil. 2026 » (sous-titre de la fiche). */
export function formatDateLong(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

/** « ~30 s de lecture ». */
export function formatTempsLecture(sec: number): string {
  if (sec < 60) return `~${sec} s de lecture`;
  const min = Math.round(sec / 60);
  return `~${min} min de lecture`;
}

/** « 312 pour · 220 contre » (micro-résultat des cartes, §3.1). */
export function formatMicroResultat(pour: number, contre: number): string {
  return `${pour} pour · ${contre} contre`;
}
