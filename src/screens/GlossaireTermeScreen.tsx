import { useCallback } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, mono, radius, serifDisplay, serifDisplaySemi, spacing, typography } from '@/theme';
import { DossierCard, EmptyView, IconLigne } from '@/components';
import { GLOSSAIRE_PAR_ID, trouveParLibelle } from '@/constants/glossaire';
import { LIBELLES_CATEGORIE } from '@/types/glossaire';
import { useRecherche } from '@/hooks';
import type { DossierListItem } from '@/types';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;
type Route = RouteProp<RootStackParamList, 'GlossaireTerme'>;

/**
 * Glossaire — la fiche d'un terme (§3.3).
 *
 * Une définition ne doit pas être un cul-de-sac : après le sens (une phrase),
 * le déroulé (« Concrètement ») et les faux amis, la fiche renvoie vers les
 * **dossiers où le mot apparaît vraiment** — on repart lire un texte, pas
 * seulement une définition. Ces dossiers viennent de la recherche existante :
 * aucun contenu inventé, et le bloc disparaît s'il n'y a rien (§2.5).
 */
export function GlossaireTermeScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const { params } = useRoute<Route>();
  const terme = GLOSSAIRE_PAR_ID[params.termeId];

  const { dossiers, loading } = useRecherche(
    terme ? (terme.requete ?? terme.libelle) : '',
  );

  const onPressDossier = useCallback(
    (dossier: DossierListItem) =>
      navigation.navigate('DossierDetail', { dossierId: dossier.id }),
    [navigation],
  );

  if (!terme) {
    return (
      <View style={[styles.container, { paddingTop: insets.top + spacing.xxl }]}>
        <EmptyView
          title="Terme introuvable"
          subtitle="Ce mot n’est pas (encore) au glossaire."
        />
      </View>
    );
  }

  const voisins = (terme.voisins ?? []).map((libelle) => ({
    libelle,
    cible: trouveParLibelle(libelle),
  }));

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <ScrollView
        contentContainerStyle={[
          styles.contenu,
          { paddingBottom: insets.bottom + spacing.xxxl },
        ]}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.barre}>
          <Pressable
            onPress={navigation.goBack}
            style={styles.retour}
            accessibilityRole="button"
            accessibilityLabel="Revenir à l’écran précédent"
            hitSlop={8}
          >
            <IconLigne
              name="chevronGauche"
              color={colors.textSecondary}
              size={20}
              strokeWidth={2}
            />
            {/* « Retour » et non « Glossaire » : on arrive aussi ici depuis la
                frise d'un dossier ou le titre d'une fiche vote (aide en ligne),
                et nommer un écran qu'on ne quitte pas serait faux. */}
            <Text style={styles.retourTexte}>Retour</Text>
          </Pressable>
        </View>

        <Text style={styles.eyebrow}>
          {LIBELLES_CATEGORIE[terme.categorie]} ·{' '}
          {terme.libelle[0].toUpperCase()}
        </Text>
        <Text style={styles.titre}>{terme.libelle}</Text>
        {terme.nature || terme.precision ? (
          <Text style={styles.nature}>
            {[terme.nature, terme.precision].filter(Boolean).join(' · ')}
          </Text>
        ) : null}

        <LinearGradient
          colors={['rgba(139,156,244,0.17)', 'rgba(139,156,244,0.03)']}
          start={{ x: 0, y: 0 }}
          end={{ x: 0.9, y: 1 }}
          style={styles.definitionCarte}
        >
          <Text style={styles.definitionLabel}>En une phrase</Text>
          <Text style={styles.definition}>{terme.definition}</Text>
        </LinearGradient>

        {terme.etapes && terme.etapes.length > 0 ? (
          <>
            <Text style={[typography.overline, styles.sectionTitre]}>
              Concrètement
            </Text>
            <View style={styles.carte}>
              {terme.etapes.map((etape, index) => {
                const dernier = index === terme.etapes!.length - 1;
                return (
                  <View key={etape.titre} style={styles.etape}>
                    <View style={styles.frise}>
                      <View style={[styles.pastille, dernier && styles.pastillePleine]} />
                      {dernier ? null : <View style={styles.trait} />}
                    </View>
                    <View style={[styles.etapeTexte, dernier && styles.etapeDerniere]}>
                      <Text style={styles.etapeTitre}>{etape.titre}</Text>
                      {etape.detail ? (
                        <Text style={styles.etapeDetail}>{etape.detail}</Text>
                      ) : null}
                    </View>
                  </View>
                );
              })}
            </View>
          </>
        ) : null}

        {voisins.length > 0 ? (
          <View style={styles.voisinsCarte}>
            <Text style={styles.voisinsLabel}>À ne pas confondre</Text>
            <View style={styles.voisins}>
              {/* Un terme voisin sans fiche reste affiché — c'est une
                  information utile —, mais il ne doit pas ressembler à un lien
                  qu'on peut suivre : pastille atténuée et rôle « texte ». */}
              {voisins.map(({ libelle, cible }) => (
                <Pressable
                  key={libelle}
                  disabled={!cible}
                  onPress={() =>
                    cible
                      ? navigation.push('GlossaireTerme', { termeId: cible.id })
                      : undefined
                  }
                  style={[styles.voisin, !cible && styles.voisinInerte]}
                  accessibilityRole={cible ? 'button' : 'text'}
                  accessibilityLabel={
                    cible ? `Ouvrir la fiche « ${libelle} »` : libelle
                  }
                >
                  <Text
                    style={[styles.voisinTexte, !cible && styles.voisinTexteInerte]}
                  >
                    {libelle}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
        ) : null}

        {dossiers.length > 0 ? (
          <>
            <View style={styles.sectionEntete}>
              <Text style={typography.overline}>Où ce mot apparaît</Text>
              <Text style={styles.compte}>
                {dossiers.length} DOSSIER{dossiers.length > 1 ? 'S' : ''}
              </Text>
            </View>
            <View style={styles.dossiers}>
              {dossiers.slice(0, 3).map((dossier) => (
                <DossierCard
                  key={dossier.id}
                  dossier={dossier}
                  onPress={onPressDossier}
                />
              ))}
            </View>
          </>
        ) : loading ? null : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  contenu: { paddingHorizontal: spacing.xl },
  barre: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: spacing.md,
    paddingBottom: spacing.xl,
  },
  retour: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm + 2 },
  retourTexte: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  eyebrow: {
    fontFamily: mono,
    fontSize: 10.5,
    fontWeight: '700',
    letterSpacing: 1.7,
    textTransform: 'uppercase',
    color: colors.brand,
  },
  titre: {
    fontFamily: serifDisplay,
    fontSize: 36,
    lineHeight: 41,
    letterSpacing: -0.7,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  nature: {
    fontFamily: mono,
    fontSize: 11,
    fontWeight: '500',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    color: colors.textTertiary,
    marginTop: spacing.sm - 1,
  },
  definitionCarte: {
    marginTop: spacing.xl,
    padding: spacing.lg + 1,
    borderRadius: radius.xl - 2,
    borderWidth: 1,
    borderColor: 'rgba(139,156,244,0.26)',
  },
  definitionLabel: {
    fontFamily: mono,
    fontSize: 9.5,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    color: colors.splashLigneSoft,
    marginBottom: spacing.sm + 2,
  },
  definition: {
    fontFamily: serifDisplaySemi,
    fontSize: 19,
    lineHeight: 27,
    letterSpacing: -0.2,
    color: colors.textPrimary,
  },
  sectionTitre: { marginTop: spacing.xxl, marginBottom: spacing.md - 1 },
  carte: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.xl - 2,
    padding: spacing.lg + 1,
  },
  etape: { flexDirection: 'row', gap: spacing.md + 1 },
  frise: { alignItems: 'center', paddingTop: 3 },
  pastille: {
    width: 9,
    height: 9,
    borderRadius: radius.pill,
    borderWidth: 2,
    borderColor: colors.brand,
  },
  pastillePleine: { backgroundColor: colors.brand },
  trait: {
    flex: 1,
    width: 2,
    backgroundColor: 'rgba(139,156,244,0.28)',
    marginVertical: 3,
  },
  etapeTexte: { flex: 1, paddingBottom: spacing.lg - 1 },
  etapeDerniere: { paddingBottom: 0 },
  etapeTitre: {
    fontSize: 14,
    lineHeight: 19,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  etapeDetail: {
    ...typography.bodySecondary,
    fontSize: 12.5,
    lineHeight: 18,
    marginTop: 3,
  },
  voisinsCarte: {
    marginTop: spacing.xl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  voisinsLabel: {
    fontFamily: mono,
    fontSize: 9.5,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    color: colors.miniLabel,
    marginBottom: spacing.sm + 1,
  },
  voisins: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  voisin: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.pill,
    paddingVertical: spacing.sm - 1,
    paddingHorizontal: spacing.md + 1,
  },
  voisinTexte: {
    fontSize: 12.5,
    fontWeight: '500',
    color: 'rgba(255,255,255,0.72)',
  },
  voisinInerte: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: colors.border,
  },
  voisinTexteInerte: { color: colors.textTertiary },
  sectionEntete: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.xxl,
    marginBottom: spacing.md - 1,
  },
  compte: {
    fontFamily: mono,
    fontSize: 10.5,
    fontWeight: '500',
    letterSpacing: 0.5,
    color: colors.textTertiary,
  },
  dossiers: { gap: spacing.md },
});
