import { useCallback, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  SectionList,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, mono, radius, serifDisplay, spacing } from '@/theme';
import {
  DeputeRow,
  DossierChronoRow,
  EmptyView,
  IconLigne,
} from '@/components';
import { LIMITE_MAX, useRecherche } from '@/hooks';
import { grouperParPeriode } from '@/utils/periodes';
import type { DeputeListItem, DossierListItem } from '@/types';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;
type Route = RouteProp<RootStackParamList, 'Dossiers'>;

type Onglet = 'textes' | 'deputes';

/**
 * Une ligne de la liste. Les deux onglets n'affichent pas le même objet, et la
 * `SectionList` est une seule : sans cette union, TypeScript fige le type sur la
 * première branche et il faut des `as` qui masqueraient une vraie erreur.
 */
type LigneResultat =
  | { type: 'dossier'; dossier: DossierListItem }
  | { type: 'depute'; depute: DeputeListItem };

interface SectionResultats {
  cle: string;
  label: string;
  data: LigneResultat[];
}

/**
 * Écran Dossiers (§3.3) — les résultats d'une recherche.
 *
 * Volontairement DISTINCT d'Explorer : là-bas un grand titre d'affichage et des
 * cartes ; ici une barre d'outils qui porte la requête, des onglets soulignés,
 * un décompte factuel, et une **chronologie** de lignes denses. On sait
 * immédiatement qu'on a quitté la page de découverte.
 *
 * Le tri vit dans `grouperParPeriode` : les groupes et l'ordre des lignes
 * viennent du même calcul, ils ne peuvent pas se contredire.
 */
export function DossiersScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const { params } = useRoute<Route>();

  const [query, setQuery] = useState(params.query ?? '');
  const [onglet, setOnglet] = useState<Onglet>('textes');
  // Plafond haut : cette page annonce des catégories entières (Explorer affiche
  // « Justice · 51 dossiers »), elle ne peut pas en rendre 20 sans se contredire.
  const { dossiers, deputes, loading, error } = useRecherche(
    query,
    params.theme,
    LIMITE_MAX,
  );

  const periodes = useMemo(() => grouperParPeriode(dossiers), [dossiers]);

  const onPressDossier = useCallback(
    (dossier: DossierListItem) =>
      navigation.navigate('DossierDetail', { dossierId: dossier.id }),
    [navigation],
  );
  const onPressDepute = useCallback(
    (depute: DeputeListItem) =>
      navigation.navigate('DeputeDetail', { deputeId: depute.id }),
    [navigation],
  );

  const sections = useMemo<SectionResultats[]>(() => {
    if (onglet === 'textes') {
      return periodes.map((p) => ({
        cle: p.cle,
        label: p.label,
        data: p.data.map((dossier) => ({ type: 'dossier' as const, dossier })),
      }));
    }
    return deputes.length > 0
      ? [
          {
            cle: 'deputes',
            label: 'Parlementaires',
            data: deputes.map((depute) => ({ type: 'depute' as const, depute })),
          },
        ]
      : [];
  }, [onglet, periodes, deputes]);

  const total = onglet === 'textes' ? dossiers.length : deputes.length;
  const libelleTotal =
    onglet === 'textes'
      ? total > 1
        ? total + ' textes'
        : total + ' texte'
      : total > 1
        ? total + ' parlementaires'
        : total + ' parlementaire';
  // Le décompte est celui des résultats REÇUS. Quand l'API a rendu son maximum,
  // il peut en exister d'autres : on le dit, plutôt que de laisser lire un total
  // (§2.5). Les députés sont déjà plafonnés à 5 par `useRecherche` — leur onglet
  // affiche donc « 5 » sans prétendre à autre chose.
  const tronque = onglet === 'textes' && dossiers.length >= LIMITE_MAX;

  return (
    <View style={styles.container}>
      {/* Barre d'outils : c'est elle qui signe la page (surface sur le fond). */}
      <View style={[styles.barre, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.barreHaut}>
          <Pressable
            onPress={navigation.goBack}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityLabel="Revenir à Explorer"
          >
            <IconLigne
              name="chevronGauche"
              color="rgba(255,255,255,0.7)"
              size={22}
              strokeWidth={2}
            />
          </Pressable>

          <View style={styles.champ}>
            <IconLigne
              name="loupe"
              color="rgba(255,255,255,0.45)"
              size={16}
              strokeWidth={1.85}
            />
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Dossier, texte, élu, terme…"
              placeholderTextColor={colors.textTertiary}
              style={styles.input}
              returnKeyType="search"
              autoCorrect={false}
              clearButtonMode="while-editing"
              accessibilityLabel="Affiner la recherche"
            />
            {loading ? (
              <ActivityIndicator size="small" color={colors.textTertiary} />
            ) : null}
          </View>
        </View>

        <View style={styles.onglets}>
          {(
            [
              ['textes', 'Textes', dossiers.length],
              ['deputes', 'Députés', deputes.length],
            ] as const
          ).map(([cle, label, nombre]) => {
            const actif = onglet === cle;
            return (
              <Pressable
                key={cle}
                onPress={() => setOnglet(cle)}
                style={[styles.onglet, actif && styles.ongletActif]}
                accessibilityRole="tab"
                accessibilityState={{ selected: actif }}
              >
                <Text style={[styles.ongletLabel, actif && styles.ongletLabelActif]}>
                  {label}
                </Text>
                <Text style={[styles.ongletNombre, actif && styles.ongletNombreActif]}>
                  {nombre}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      <SectionList
        sections={sections}
        keyExtractor={(item) =>
          item.type === 'dossier' ? item.dossier.id : item.depute.id
        }
        contentContainerStyle={[
          styles.liste,
          { paddingBottom: insets.bottom + spacing.xxxl },
        ]}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        stickySectionHeadersEnabled={false}
        ListHeaderComponent={
          <View>
            <Text style={styles.total}>
              {tronque ? `Les ${LIMITE_MAX} plus récents` : libelleTotal}
            </Text>
            <Text style={styles.tri}>
              {onglet === 'textes'
                ? tronque
                  ? 'Par date de dernier vote · affinez pour aller plus loin'
                  : 'Par date de dernier vote · plus récents d’abord'
                : 'Par pertinence'}
            </Text>
          </View>
        }
        renderSectionHeader={({ section }) => (
          <View style={styles.periode}>
            <Text style={styles.periodeLabel}>{section.label}</Text>
            <View style={styles.periodeFilet} />
          </View>
        )}
        renderItem={({ item, index, section }) =>
          item.type === 'dossier' ? (
            <DossierChronoRow
              dossier={item.dossier}
              premier={index === 0}
              dernier={index === section.data.length - 1}
              onPress={onPressDossier}
            />
          ) : (
            <DeputeRow depute={item.depute} onPress={onPressDepute} />
          )
        }
        ItemSeparatorComponent={
          onglet === 'deputes' ? () => <View style={{ height: spacing.md }} /> : null
        }
        ListEmptyComponent={
          loading ? null : error ? (
            <EmptyView
              title="Recherche indisponible"
              subtitle="Impossible de joindre le serveur. Réessayez."
            />
          ) : (
            <EmptyView
              title="Aucun résultat"
              subtitle="Essayez un autre mot-clé, ou revenez à Explorer."
            />
          )
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  barre: {
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingHorizontal: spacing.lg,
  },
  barreHaut: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm + 2 },
  champ: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm + 1,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md - 1,
    paddingHorizontal: spacing.md,
  },
  input: {
    flex: 1,
    paddingVertical: spacing.sm + 1,
    fontSize: 14.5,
    color: colors.textPrimary,
  },
  onglets: { flexDirection: 'row', gap: spacing.xxl - 2, marginTop: spacing.lg - 2 },
  onglet: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 6,
    paddingBottom: spacing.md - 1,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  ongletActif: { borderBottomColor: colors.brand },
  ongletLabel: { fontSize: 13.5, fontWeight: '600', color: 'rgba(255,255,255,0.42)' },
  ongletLabelActif: { color: colors.textPrimary },
  ongletNombre: {
    fontFamily: mono,
    fontSize: 10.5,
    fontWeight: '600',
    color: colors.textTertiary,
  },
  ongletNombreActif: { color: colors.brand },
  liste: { paddingHorizontal: spacing.xl, flexGrow: 1 },
  total: {
    fontFamily: serifDisplay,
    fontSize: 21,
    letterSpacing: -0.3,
    color: colors.textPrimary,
    marginTop: spacing.lg,
  },
  tri: {
    fontFamily: mono,
    fontSize: 10.5,
    lineHeight: 16,
    fontWeight: '500',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    color: colors.miniLabel,
    marginTop: 3,
  },
  periode: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md - 2,
    paddingTop: spacing.xl,
    paddingBottom: 2,
  },
  periodeLabel: {
    fontFamily: serifDisplay,
    fontSize: 15,
    color: 'rgba(255,255,255,0.85)',
  },
  periodeFilet: { flex: 1, height: 1, backgroundColor: 'rgba(255,255,255,0.09)' },
});
