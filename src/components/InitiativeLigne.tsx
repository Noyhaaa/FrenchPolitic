import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import type { Initiative } from '@/types';
import { Avatar } from './Avatar';

interface Props {
  initiative?: Initiative | null;
  /** Ouvre la fiche du parlementaire — appelé seulement si `deputeId` existe. */
  onOuvrirDepute: (deputeId: string) => void;
}

/** Ce qu'on affiche : un intitulé principal et sa précision, jamais autre chose. */
interface Contenu {
  principal: string;
  secondaire?: string;
}

/**
 * Libellés des trois origines. Les deux formes institutionnelles portent une
 * précision **vraie par construction** : `gouvernement` n'est posé que sur un
 * projet de loi (art. 39), `senat` que sur un dépôt classé « en navette » —
 * ce ne sont donc pas des ajouts, mais la règle qui a produit l'origine.
 */
function contenu(initiative: Initiative): Contenu | null {
  switch (initiative.origine) {
    case 'gouvernement':
      return { principal: 'Gouvernement', secondaire: 'Projet de loi' };
    case 'senat':
      return { principal: 'Sénat', secondaire: "Texte transmis à l'Assemblée" };
    case 'parlementaire':
      // Origine sans personne nommable (plusieurs auteurs, ou auteur qui ne
      // siège plus) : « un parlementaire » n'apprendrait rien au lecteur, on
      // masque plutôt que d'afficher un contenant vide (§2.5).
      return initiative.nom
        ? {
            principal: initiative.nom,
            secondaire: initiative.groupeNom ?? undefined,
          }
        : null;
  }
}

/**
 * Qui porte le texte (§5.1) — la première question qu'on se pose devant un vote.
 *
 * Trois origines, et rien d'autre : le **Gouvernement** (tout projet de loi,
 * art. 39 — jamais le ministre déposant, dont la fonction n'est documentée dans
 * aucune de nos sources), un **parlementaire nommé**, ou le **Sénat** quand le
 * texte y a été déposé puis transmis à l'Assemblée.
 *
 * **Même gabarit dans les trois cas** (§7.4) : un médaillon, un intitulé, une
 * précision. Le médaillon d'une institution est le même composant `Avatar` que
 * celui d'une personne — réduit à son initiale —, pour qu'aucune origine ne
 * reçoive un traitement visuel plus flatteur qu'une autre.
 *
 * ⚠️ Volontairement **sans le liseré d'accent** d'`ExposeMotifsCard` : là-bas il
 * signale un contenu non neutre (« point de vue de l'auteur »). L'initiative est
 * un **fait** ; reprendre le même signe visuel — a fortiori teinté de la couleur
 * du groupe — laisserait croire que la carte porte l'opinion de ce groupe.
 *
 * Le nom n'ouvre une fiche que s'il porte un `deputeId` (§5.2) : sinon la carte
 * n'est pas pressable et n'affiche pas de chevron — jamais d'affordance qui ne
 * mène nulle part, jamais de lien vers un 404. L'appartenance de groupe est
 * portée par la pastille **et** par son libellé écrit (§8/RGAA).
 */
export function InitiativeLigne({ initiative, onOuvrirDepute }: Props) {
  if (!initiative) return null;
  const texte = contenu(initiative);
  if (!texte) return null;

  const deputeId = initiative.deputeId;

  const corps = (
    <>
      <Avatar
        nom={texte.principal}
        // Photo officielle du parlementaire quand le référentiel en porte une ;
        // sinon ses initiales (l'`Avatar` retombe seul dessus, y compris si
        // l'image devient injoignable). Une institution n'en a jamais.
        portraitUrl={initiative.portraitUrl ?? undefined}
        groupeCouleur={initiative.groupeCouleur ?? undefined}
        taille={40}
      />
      <View style={styles.textes}>
        <Text style={styles.principal} numberOfLines={2}>
          {texte.principal}
        </Text>
        {texte.secondaire ? (
          <Text style={typography.meta} numberOfLines={1}>
            {texte.secondaire}
          </Text>
        ) : null}
      </View>
      {deputeId ? (
        <Text style={styles.chevron} importantForAccessibility="no">
          ›
        </Text>
      ) : null}
    </>
  );

  return (
    <View style={styles.card}>
      <Text style={[typography.overline, styles.titre]}>À l'origine du texte</Text>
      {deputeId ? (
        <Pressable
          onPress={() => onOuvrirDepute(deputeId)}
          style={({ pressed }) => [styles.ligne, pressed && styles.pressee]}
          accessibilityRole="link"
          accessibilityLabel={`${texte.principal}${
            texte.secondaire ? `, ${texte.secondaire}` : ''
          }. Voir sa fiche.`}
        >
          {corps}
        </Pressable>
      ) : (
        <View style={styles.ligne}>{corps}</View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    // Pas de marge propre : l'écran qui l'accueille espace déjà ses blocs
    // (`gap` du conteneur de défilement).
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  titre: {
    marginBottom: spacing.sm,
  },
  ligne: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
  },
  pressee: {
    opacity: 0.7,
  },
  textes: {
    flex: 1,
    gap: 3,
  },
  principal: {
    ...typography.readingBody,
    fontSize: 17,
    lineHeight: 22,
  },
  chevron: {
    color: colors.textTertiary,
    fontSize: 22,
    fontWeight: '600',
  },
});
