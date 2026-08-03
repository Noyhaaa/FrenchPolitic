import { Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Stop } from 'react-native-svg';

import { colors, mono } from '@/theme';

/**
 * Anneau de **couverture** — la part des dossiers publiés que rassemblent les
 * thèmes suivis par le lecteur.
 *
 * ⚠️ Ce n'est **pas un score du lecteur**. La maquette posait ici un « Civic
 * Score 78/100 » : rien ne peut le calculer (aucun historique de lecture n'est
 * conservé, §7.6) et une note sur la personne n'aurait aucune source. Ce qui est
 * affiché est de l'**arithmétique pure sur les décomptes de `GET /themes`** —
 * même doctrine que l'indice de division de l'accueil (§4.3).
 *
 * Le chiffre n'apparaît jamais nu : l'écran l'accompagne toujours de sa phrase
 * (« Vos thèmes couvrent N dossiers sur M publiés »), faute de quoi un
 * pourcentage se lirait comme une note.
 *
 * Corpus indisponible (`total === 0`, hors-ligne ou `/themes` vide) → rien n'est
 * rendu, plutôt qu'un « 0 % » qui décrirait nos données, pas les siennes (§2.5).
 */

interface Props {
  /** Dossiers rattachés aux thèmes suivis. */
  suivis: number;
  /** Dossiers du corpus, tous thèmes confondus. */
  total: number;
  onPress?: () => void;
  taille?: number;
}

const RAYON = 32;
const EPAISSEUR = 5;
const CIRCONFERENCE = 2 * Math.PI * RAYON;

export function AnneauCouverture({ suivis, total, onPress, taille = 80 }: Props) {
  if (total <= 0) return null;

  const part = suivis / total;
  const pourcent = Math.round(part * 100);
  // Un thème suivi qui pèse moins d'un point ne doit pas s'afficher « 0 % » :
  // le lecteur a bien fait un choix, et le fait est qu'il est petit.
  const centre = suivis === 0 ? '—' : pourcent === 0 ? '<1' : String(pourcent);
  const dash = CIRCONFERENCE * part;

  const etiquette =
    suivis === 0
      ? 'Aucun thème suivi.'
      : `Couverture : vos thèmes rassemblent ${suivis} dossiers sur ${total}, soit ${pourcent} %.`;

  const contenu = (
    <View style={{ width: taille, height: taille }}>
      <Svg width={taille} height={taille} viewBox="0 0 80 80">
        <Defs>
          <LinearGradient id="couverture" x1="0%" y1="0%" x2="100%" y2="100%">
            <Stop offset="0%" stopColor={colors.brandProfond} />
            <Stop offset="100%" stopColor={colors.brand} />
          </LinearGradient>
        </Defs>
        <Circle
          cx={40}
          cy={40}
          r={RAYON}
          fill="none"
          stroke={colors.surfaceMuted}
          strokeWidth={EPAISSEUR}
        />
        {suivis > 0 ? (
          <Circle
            cx={40}
            cy={40}
            r={RAYON}
            fill="none"
            stroke="url(#couverture)"
            strokeWidth={EPAISSEUR}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${CIRCONFERENCE}`}
            originX={40}
            originY={40}
            rotation={-90}
          />
        ) : null}
      </Svg>
      <View style={styles.centre} pointerEvents="none">
        <Text style={styles.valeur}>{centre}</Text>
        {suivis > 0 ? <Text style={styles.unite}>%</Text> : null}
      </View>
    </View>
  );

  return (
    <View style={styles.bloc}>
      {onPress ? (
        <Pressable
          onPress={onPress}
          accessibilityRole="button"
          accessibilityLabel={etiquette}
          accessibilityHint="Ouvre l’onglet Thèmes"
          style={({ pressed }) => (pressed ? styles.pressee : undefined)}
        >
          {contenu}
        </Pressable>
      ) : (
        <View accessibilityLabel={etiquette} accessible>
          {contenu}
        </View>
      )}
      <Text style={styles.legende} importantForAccessibility="no">
        COUVERTURE
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  bloc: { alignItems: 'center', gap: 2 },
  pressee: { opacity: 0.8 },
  centre: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center' },
  valeur: { fontFamily: mono, fontSize: 20, fontWeight: '700', color: colors.textPrimary },
  unite: { fontFamily: mono, fontSize: 9, color: colors.textTertiary },
  legende: {
    fontFamily: mono,
    fontSize: 9,
    letterSpacing: 1.2,
    color: colors.miniLabel,
  },
});
