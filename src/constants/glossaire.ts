import type { SectionGlossaire, TermeGlossaire } from '@/types/glossaire';
import { plier } from '@/utils/format';

/**
 * Le glossaire — **source unique**, pour ses deux surfaces (§8 : pas de jargon
 * non expliqué).
 *
 * 1. Les **écrans** `GlossaireScreen` (l'index) et `GlossaireTermeScreen` (la
 *    fiche) : on vient y chercher un mot.
 * 2. L'**aide en ligne** là où le mot s'affiche sans être expliqué — une étape
 *    de la frise `TrajectoireNavette`, le titre d'une fiche vote : le lecteur
 *    n'a rien demandé, c'est le produit qui doit tendre la définition. C'est le
 *    rôle de `termeGlossaire()` et de la table `MOTIFS`.
 *
 * Un seul fichier pour les deux, sinon les deux versions divergent et la même
 * app explique un mot de deux façons.
 *
 * Chaque définition est un **fait de procédure** (Constitution, Règlement des
 * assemblées) tenant en une phrase, jamais une appréciation sur le texte
 * concerné ni sur ceux qui l'ont voté (§4.3, §7.4).
 *
 * Le contenu est local pour l'instant. Le jour où le backend sert
 * `GET /glossaire`, seul ce fichier change : les écrans ne dépendent que des
 * types de `@/types/glossaire`. (Il vit dans `constants/` avec `themes.ts`, et
 * non dans un `src/data/` — ce dossier a été supprimé avec les mocks, et ceci
 * est du contenu éditorial, pas une donnée de substitution.)
 */
export const GLOSSAIRE: TermeGlossaire[] = [
  {
    id: 'abstention',
    libelle: 'Abstention',
    nature: 'n.f.',
    categorie: 'vote',
    definition: 'Être présent au vote sans se prononcer ni pour ni contre.',
    voisins: ['Non-votant', 'Scrutin public'],
  },
  {
    id: 'amendement',
    libelle: 'Amendement',
    nature: 'n.m.',
    categorie: 'procedure',
    definition: 'Une modification proposée à un texte pendant son examen.',
    etapes: [
      {
        titre: 'Un parlementaire dépose sa modification',
        detail: 'Il vise un article précis et explique ce qu’il veut changer.',
      },
      {
        titre: 'La commission puis la séance en débattent',
        detail: 'Chaque amendement est discuté, puis mis aux voix.',
      },
      {
        titre: 'Adopté, il réécrit le texte',
        detail: 'Rejeté ou retiré, il disparaît — mais reste au compte rendu.',
      },
    ],
    voisins: ['Sous-amendement', 'Dispositif'],
  },
  {
    id: 'article-49-3',
    libelle: 'Article 49.3',
    nature: 'loc.',
    categorie: 'procedure',
    definition:
      'Faire adopter un texte sans vote, en engageant la responsabilité du gouvernement.',
    etapes: [
      {
        titre: 'Le gouvernement engage sa responsabilité',
        detail: 'Le débat sur le texte s’arrête immédiatement.',
      },
      {
        titre: 'Les députés ont 24 heures',
        detail: 'Ils peuvent déposer une motion de censure.',
      },
      {
        titre: 'Sans censure votée, le texte est adopté',
        detail: 'Aucun vote n’a lieu sur le texte lui-même.',
      },
    ],
    voisins: ['Motion de censure', 'Lecture définitive'],
  },
  {
    id: 'article-unique',
    libelle: 'Article unique',
    nature: 'loc.',
    categorie: 'procedure',
    definition:
      'Un texte qui ne compte qu’un seul article : le vote sur cet article vaut vote sur le texte entier.',
    voisins: ['Vote sur l’ensemble'],
  },
  {
    id: 'budget-rectificatif',
    libelle: 'Budget rectificatif',
    nature: 'n.m.',
    categorie: 'budget',
    definition:
      'Corriger le budget en cours d’année quand les prévisions ont bougé.',
    voisins: ['Loi de finances', 'Projet de loi'],
  },
  {
    id: 'commission-mixte-paritaire',
    libelle: 'Commission mixte paritaire',
    nature: 'n.f.',
    precision: 'dite « CMP »',
    categorie: 'procedure',
    definition:
      'Quatorze parlementaires, sept de chaque chambre, cherchent un compromis sur un texte bloqué.',
    etapes: [
      { titre: 'Le désaccord persiste après la navette' },
      {
        titre: 'Sept députés et sept sénateurs se réunissent',
        detail: 'Ils tentent d’écrire une version commune.',
      },
      {
        titre: 'Accord ou échec',
        detail:
          'En cas d’échec, le gouvernement peut demander une lecture définitive.',
      },
    ],
    voisins: ['Navette', 'Lecture définitive', 'Nouvelle lecture'],
    requete: 'commission mixte paritaire',
  },
  {
    id: 'conseil-constitutionnel',
    libelle: 'Conseil constitutionnel',
    nature: 'n.m.',
    categorie: 'institutions',
    definition:
      'Saisi avant la promulgation, il vérifie qu’une loi est conforme à la Constitution et peut en annuler tout ou partie.',
    voisins: ['Promulgation'],
  },
  {
    id: 'deuxieme-lecture',
    libelle: 'Deuxième lecture',
    nature: 'n.f.',
    categorie: 'procedure',
    definition:
      'Le nouvel examen, par une chambre, d’un texte que l’autre a modifié.',
    voisins: ['Navette', 'Première lecture'],
  },
  {
    id: 'groupe-politique',
    libelle: 'Groupe politique',
    nature: 'n.m.',
    categorie: 'institutions',
    definition:
      'Des parlementaires qui siègent ensemble et organisent leur travail en commun.',
    voisins: ['Cohésion', 'Non-inscrit'],
  },
  {
    id: 'lecture-definitive',
    libelle: 'Lecture définitive',
    nature: 'n.f.',
    categorie: 'procedure',
    definition:
      'À la demande du gouvernement, l’Assemblée nationale statue seule et en dernier sur le texte.',
    voisins: ['Navette', 'Commission mixte paritaire'],
  },
  {
    id: 'lecture-unique',
    libelle: 'Lecture unique',
    nature: 'n.f.',
    categorie: 'procedure',
    definition:
      'Un texte examiné une seule fois, sans aller-retour entre les deux chambres.',
    voisins: ['Navette'],
  },
  {
    id: 'motion-ajournement',
    libelle: 'Motion d’ajournement',
    nature: 'n.f.',
    categorie: 'procedure',
    definition:
      'Une proposition de suspendre l’examen du texte et de le reprendre plus tard.',
    voisins: ['Motion de rejet préalable'],
  },
  {
    id: 'motion-de-censure',
    libelle: 'Motion de censure',
    nature: 'n.f.',
    categorie: 'vote',
    definition:
      'Un vote qui, s’il réunit la majorité absolue des députés, fait tomber le gouvernement.',
    etapes: [
      {
        titre: 'Des députés la déposent',
        detail: 'Souvent après un 49.3, dans les 24 heures.',
      },
      {
        titre: 'Seules les voix POUR sont comptées',
        detail:
          'Ne pas voter revient à soutenir le gouvernement : c’est pourquoi ce scrutin n’affiche pas de « contre ».',
      },
      {
        titre: 'La majorité absolue fait tomber le gouvernement',
        detail: 'À défaut, il reste en place et le texte suit son cours.',
      },
    ],
    voisins: ['Article 49.3'],
  },
  {
    id: 'motion-de-rejet-prealable',
    libelle: 'Motion de rejet préalable',
    nature: 'n.f.',
    categorie: 'procedure',
    definition:
      'Une proposition de rejeter le texte sans discuter ses articles.',
    etapes: [
      { titre: 'Un groupe la dépose avant la discussion' },
      {
        titre: 'Adoptée, le texte est rejeté',
        detail:
          'L’examen s’arrête là : sur cette motion, « adopté » veut donc dire que le texte, lui, ne passe pas.',
      },
      {
        titre: 'Rejetée, la discussion se poursuit',
        detail: 'Les articles sont examinés normalement.',
      },
    ],
    voisins: ['Motion d’ajournement', 'Motion référendaire'],
  },
  {
    id: 'motion-referendaire',
    libelle: 'Motion référendaire',
    nature: 'n.f.',
    categorie: 'vote',
    definition:
      'Une proposition de soumettre le texte au référendum au lieu de le faire voter par le Parlement.',
    voisins: ['Motion de rejet préalable'],
  },
  {
    id: 'navette',
    libelle: 'Navette',
    nature: 'n.f.',
    precision: 'dite « navette parlementaire »',
    categorie: 'procedure',
    definition:
      'L’aller-retour d’un texte entre les deux chambres, jusqu’à ce qu’elles tombent d’accord sur la même version.',
    etapes: [
      {
        titre: 'La première chambre vote le texte',
        detail: 'Elle l’amende, puis l’envoie à l’autre.',
      },
      {
        titre: 'La seconde le modifie à son tour',
        detail: 'Le texte repart d’où il venait. C’est la navette.',
      },
      {
        titre: 'Accord — ou commission mixte',
        detail:
          'Si le désaccord persiste, quatorze parlementaires cherchent un compromis.',
      },
    ],
    voisins: ['Commission mixte paritaire', 'Lecture définitive'],
  },
  {
    id: 'nouvelle-lecture',
    libelle: 'Nouvelle lecture',
    nature: 'n.f.',
    categorie: 'procedure',
    definition:
      'L’examen qui suit une commission mixte paritaire sans accord, ou dont la version proposée a été rejetée.',
    voisins: ['Commission mixte paritaire', 'Lecture définitive'],
  },
  {
    id: 'ordonnance',
    libelle: 'Ordonnance',
    nature: 'n.f.',
    categorie: 'institutions',
    definition:
      'Une mesure prise par le gouvernement dans un domaine que le Parlement lui a ouvert pour un temps limité.',
    voisins: ['Décret', 'Loi d’habilitation'],
  },
  {
    id: 'premiere-lecture',
    libelle: 'Première lecture',
    nature: 'n.f.',
    categorie: 'procedure',
    definition: 'Le premier examen d’un texte par une chambre.',
    etapes: [
      {
        titre: 'Une chambre se saisit du texte la première',
        detail:
          'C’est ce que dit la mention « 1ʳᵉ assemblée saisie » sur la frise d’un dossier.',
      },
      {
        titre: 'Elle l’amende, puis le vote',
        detail: 'Le texte part ensuite devant l’autre chambre.',
      },
      {
        titre: 'L’autre chambre l’examine à son tour',
        detail: 'C’est sa « 1ʳᵉ lecture » à elle, comme deuxième assemblée saisie.',
      },
    ],
    voisins: ['Navette', 'Deuxième lecture'],
  },
  {
    id: 'projet-de-loi',
    libelle: 'Projet de loi',
    nature: 'n.m.',
    categorie: 'procedure',
    definition: 'Un texte déposé par le gouvernement.',
    voisins: ['Proposition de loi'],
  },
  {
    id: 'promulgation',
    libelle: 'Promulgation',
    nature: 'n.f.',
    categorie: 'institutions',
    definition:
      'La signature de la loi par le président de la République, qui la rend applicable.',
    voisins: ['Conseil constitutionnel'],
  },
  {
    id: 'proposition-de-loi',
    libelle: 'Proposition de loi',
    nature: 'n.f.',
    categorie: 'procedure',
    definition: 'Un texte déposé par un ou plusieurs parlementaires.',
    voisins: ['Projet de loi'],
  },
  {
    id: 'resolution',
    libelle: 'Résolution',
    nature: 'n.f.',
    categorie: 'procedure',
    definition:
      'Un texte par lequel une chambre exprime une position, sans créer de règle de droit.',
    etapes: [
      {
        titre: 'Une seule lecture',
        detail:
          'La chambre l’examine et la vote en lecture unique. Elle n’est pas transmise à l’autre chambre.',
      },
      {
        titre: 'Le parcours s’arrête au vote',
        detail:
          'Une résolution n’est ni promulguée ni publiée comme une loi : elle n’oblige personne.',
      },
    ],
    voisins: ['Lecture unique', 'Promulgation'],
  },
  {
    id: 'scrutin-public',
    libelle: 'Scrutin public',
    nature: 'n.m.',
    categorie: 'vote',
    definition:
      'Un vote où la position de chaque parlementaire est publiée nommément.',
    etapes: [
      { titre: 'Le vote est demandé par un groupe ou le gouvernement' },
      {
        titre: 'Chacun vote depuis son pupitre',
        detail: 'Le résultat nominatif est publié.',
      },
    ],
    voisins: ['Vote à main levée', 'Abstention'],
  },
  {
    id: 'seance-publique',
    libelle: 'Séance publique',
    nature: 'n.f.',
    categorie: 'institutions',
    definition:
      'Le moment où l’hémicycle siège au complet, débat et vote, devant le public.',
    voisins: ['Commission'],
  },
  {
    id: 'vote-sur-l-ensemble',
    libelle: 'Vote sur l’ensemble',
    nature: 'loc.',
    categorie: 'vote',
    definition:
      'Le vote final sur le texte entier, une fois les articles et les amendements examinés.',
    voisins: ['Article unique', 'Scrutin public'],
  },
];

/** Index par identifiant — utilisé par la fiche terme. */
export const GLOSSAIRE_PAR_ID: Record<string, TermeGlossaire> =
  Object.fromEntries(GLOSSAIRE.map((t) => [t.id, t]));

/** Retrouve un terme par son libellé (liens « À ne pas confondre »). */
export function trouveParLibelle(libelle: string): TermeGlossaire | undefined {
  const cible = plier(libelle).trim();
  return GLOSSAIRE.find((t) => plier(t.libelle) === cible);
}

// --- Aide en ligne : reconnaître un terme dans un libellé affiché -----------
//
// Les libellés que l'app affiche ne sont pas les entrées du glossaire : ce sont
// ceux de la source officielle (« 1ère lecture (2ème assemblée saisie) ») ou du
// formatage maison (`libelleScrutin` : « Motion de rejet préalable »). Cette
// table fait le pont.
//
// ⚠️ L'ordre est significatif : le PREMIER motif contenu dans le libellé gagne,
// donc les cas particuliers passent avant les cas généraux (« lecture définitive »
// avant « première lecture »). Les motifs sont pliés d'avance — la source mélange
// les casses : « Commission Mixte Paritaire » et « Commission mixte paritaire »,
// « Nouvelle Lecture » et « deuxième lecture » cohabitent en base.
//
// Volontairement limitée aux termes de PROCÉDURE, tous vérifiés contre les
// libellés réellement présents en base. On n'y met pas « amendement » : il
// apparaîtrait sur « Sous-amendement n° 12 », qui est autre chose, et la fiche
// d'un vote d'amendement porte déjà sa propre carte d'explication.
const MOTIFS: readonly { motif: string; id: string }[] = [
  { motif: 'lecture definitive', id: 'lecture-definitive' },
  { motif: 'lecture unique', id: 'lecture-unique' },
  { motif: 'nouvelle lecture', id: 'nouvelle-lecture' },
  { motif: 'deuxieme lecture', id: 'deuxieme-lecture' },
  { motif: 'premiere lecture', id: 'premiere-lecture' },
  { motif: '1ere lecture', id: 'premiere-lecture' },
  { motif: 'commission mixte paritaire', id: 'commission-mixte-paritaire' },
  { motif: 'conseil constitutionnel', id: 'conseil-constitutionnel' },
  { motif: 'promulgation', id: 'promulgation' },
  { motif: 'resolution', id: 'resolution' },
  { motif: 'motion de rejet prealable', id: 'motion-de-rejet-prealable' },
  { motif: 'motion de censure', id: 'motion-de-censure' },
  { motif: 'motion referendaire', id: 'motion-referendaire' },
  { motif: "motion d'ajournement", id: 'motion-ajournement' },
  { motif: "vote sur l'ensemble", id: 'vote-sur-l-ensemble' },
  { motif: 'article unique', id: 'article-unique' },
];

/**
 * Le terme du glossaire correspondant à un libellé affiché, sinon `undefined`
 * — auquel cas l'appelant n'affiche aucune aide (§2.5 : on n'improvise pas une
 * explication à partir d'un mot).
 */
export function termeGlossaire(libelle: string): TermeGlossaire | undefined {
  const plie = plier(libelle);
  const regle = MOTIFS.find((r) => plie.includes(r.motif));
  return regle ? GLOSSAIRE_PAR_ID[regle.id] : undefined;
}

// --- Index alphabétique et mot du jour --------------------------------------

/** Enlève les accents pour trier et grouper (A avec À, E avec É…). */
function sansAccent(valeur: string) {
  return valeur.normalize('NFD').replace(/[̀-ͯ]/g, '');
}

/**
 * Groupe les termes par lettre initiale, triés alphabétiquement — la forme
 * attendue par la `SectionList` de l'index.
 */
export function sectionsGlossaire(termes: TermeGlossaire[]): SectionGlossaire[] {
  const parLettre = new Map<string, TermeGlossaire[]>();
  for (const terme of [...termes].sort((a, b) =>
    sansAccent(a.libelle).localeCompare(sansAccent(b.libelle), 'fr')
  )) {
    const lettre = sansAccent(terme.libelle)[0]?.toUpperCase() ?? '#';
    const liste = parLettre.get(lettre);
    if (liste) liste.push(terme);
    else parLettre.set(lettre, [terme]);
  }
  return [...parLettre.entries()].map(([lettre, data]) => ({ lettre, data }));
}

/**
 * Le mot du jour : déterministe (même mot pour tout le monde le même jour, et
 * il change à minuit) plutôt qu'aléatoire.
 */
export function motDuJour(date = new Date()): TermeGlossaire {
  const jours = Math.floor(date.getTime() / 86_400_000);
  return GLOSSAIRE[jours % GLOSSAIRE.length];
}
