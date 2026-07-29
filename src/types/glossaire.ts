/**
 * Glossaire (écrans « Explorer » et « Glossaire »).
 *
 * Même doctrine que le reste de l'app : un champ absent = « information non
 * disponible » (§2.5), le bloc correspondant est masqué plutôt que comblé.
 */

/** Familles de termes proposées en filtre sur l'index du glossaire. */
export type CategorieTerme = 'procedure' | 'institutions' | 'budget' | 'vote';

export const LIBELLES_CATEGORIE: Record<CategorieTerme, string> = {
  procedure: 'Procédure',
  institutions: 'Institutions',
  budget: 'Budget',
  vote: 'Vote',
};

/** Une étape du déroulé « Concrètement » d'une fiche terme. */
export interface EtapeTerme {
  titre: string;
  detail?: string;
}

/**
 * Un terme du glossaire. `definition` est la règle d'or : UNE phrase, en
 * français clair, sans jargon ni jugement.
 */
export interface TermeGlossaire {
  id: string;
  libelle: string;
  /** Nature grammaticale affichée sous le titre (« n.f. », « loc. »). */
  nature?: string;
  /** Précision accolée à la nature (« dite „navette parlementaire“ »). */
  precision?: string;
  categorie: CategorieTerme;
  /** La définition en une phrase (bloc « En une phrase » de la fiche). */
  definition: string;
  /** Déroulé « Concrètement » — 2 à 4 étapes. Absent = bloc masqué. */
  etapes?: EtapeTerme[];
  /** Termes voisins « À ne pas confondre ». Absent = bloc masqué. */
  voisins?: string[];
  /**
   * Mot-clé envoyé à la recherche pour lister les dossiers où le terme
   * apparaît. Par défaut : le libellé.
   */
  requete?: string;
}

/** Une lettre de l'index alphabétique et ses termes. */
export interface SectionGlossaire {
  lettre: string;
  data: TermeGlossaire[];
}
