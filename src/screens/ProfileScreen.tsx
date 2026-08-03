import { useCallback, useEffect, useMemo, useState } from 'react';
import { AccessibilityInfo, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useIsFocused, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import {
  BarreOnglets,
  BoutonPrincipal,
  CarteRangees,
  Chip,
  Interrupteur,
  ProfilEntete,
  RangeeReglage,
  SelecteurDepartement,
} from '@/components';
import { themeEmoji } from '@/constants/themes';
import { useThemes } from '@/hooks';
import { useProfil } from '@/session/ProfilContext';
import { colors, spacing, typography } from '@/theme';
import type { ThemeScrutin } from '@/types';
import type { RootStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;
type Onglet = 'infos' | 'themes' | 'reglages';

const ONGLETS = [
  { cle: 'infos' as const, label: 'Infos' },
  { cle: 'themes' as const, label: 'Thèmes' },
  { cle: 'reglages' as const, label: 'Réglages' },
];

/**
 * Profil — l'état du compte et les préférences, modifiables.
 *
 * ⚠️ Le compte est **facultatif** : cet écran doit être aussi complet sans lui
 * qu'avec. Les préférences vivent sur l'appareil ; le compte ne fait que
 * permettre de les retrouver ailleurs, et c'est ce que l'écran dit — plutôt
 * qu'un bénéfice vague qui pousserait à s'inscrire.
 *
 * ⚠️ Se déconnecter ne vide **pas** les préférences : elles décrivent ce que ce
 * lecteur suit sur cet appareil, pas sa session.
 *
 * ⚠️ Rien ici ne décrit **l'activité du lecteur** — ni textes suivis, ni votes
 * lus, ni « score civique » : aucun historique de lecture n'est conservé, donc
 * aucun de ces chiffres n'aurait de source (§2.5). Le seul chiffre affiché,
 * l'anneau de couverture, décrit le **corpus** (décomptes de `GET /themes`).
 */
export function ProfileScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const focalise = useIsFocused();
  const { compte, preferences, enregistrerPreferences, seDeconnecter } = useProfil();
  const themes = useThemes();

  const [onglet, setOnglet] = useState<Onglet>('infos');
  const [selecteurOuvert, setSelecteurOuvert] = useState(false);
  const [animationsReduites, setAnimationsReduites] = useState(false);

  useEffect(() => {
    let vivant = true;
    void AccessibilityInfo.isReduceMotionEnabled().then((reduit) => {
      if (vivant) setAnimationsReduites(reduit);
    });
    const abonnement = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      setAnimationsReduites,
    );
    return () => {
      vivant = false;
      abonnement.remove();
    };
  }, []);

  const ordonnes = useMemo(() => [...themes].sort((a, b) => b.nombre - a.nombre), [themes]);

  // Couverture : arithmétique pure sur les décomptes servis par l'API.
  const couverture = useMemo(() => {
    const suivisSet = new Set<string>(preferences.themes);
    return {
      total: themes.reduce((somme, t) => somme + t.nombre, 0),
      suivis: themes
        .filter((t) => suivisSet.has(t.nom))
        .reduce((somme, t) => somme + t.nombre, 0),
    };
  }, [themes, preferences.themes]);

  const basculerTheme = useCallback(
    (theme: ThemeScrutin) => {
      const dejaSuivi = preferences.themes.includes(theme);
      void enregistrerPreferences({
        ...preferences,
        themes: dejaSuivi
          ? preferences.themes.filter((t) => t !== theme)
          : [...preferences.themes, theme],
      });
    },
    [enregistrerPreferences, preferences],
  );

  const choisirDepartement = useCallback(
    (departement: string | null) => {
      void enregistrerPreferences({ ...preferences, departement });
      setSelecteurOuvert(false);
    },
    [enregistrerPreferences, preferences],
  );

  const initiales = compte
    ? `${compte.prenom.charAt(0)}${compte.nom.charAt(0)}`.toUpperCase()
    : null;

  return (
    <View style={styles.ecran}>
      <ScrollView
        contentContainerStyle={{ paddingBottom: insets.bottom + spacing.xxxl }}
        showsVerticalScrollIndicator={false}
      >
        <ProfilEntete
          insetTop={insets.top}
          anime={focalise && !animationsReduites}
          initiales={initiales}
          titre={compte ? `${compte.prenom} ${compte.nom}` : 'Vos réglages'}
          departement={preferences.departement}
          sansCompte={!compte}
          couverture={couverture}
          onAnneauPress={() => setOnglet('themes')}
        />

        <View style={styles.corps}>
          {/* Le chiffre de l'anneau ne reste jamais seul : la phrase dit de quoi
              il est la mesure, sans quoi il se lirait comme une note (§2.5). */}
          {couverture.total > 0 ? (
            <Text style={styles.couverture}>
              {couverture.suivis === 0
                ? 'Aucun thème suivi — l’accueil garde l’ordre de la source.'
                : `Vos thèmes couvrent ${couverture.suivis} dossiers sur ${couverture.total} publiés.`}
            </Text>
          ) : null}

          <BarreOnglets
            onglets={ONGLETS}
            actif={onglet}
            onChange={setOnglet}
            contexte="Section du profil"
          />

          {onglet === 'infos' ? (
            <>
              <View style={styles.bloc}>
                <Text style={styles.entete}>COMPTE</Text>
                {compte ? (
                  <>
                    <CarteRangees>
                      <RangeeReglage
                        icone="personne"
                        label="Nom"
                        valeur={`${compte.prenom} ${compte.nom}`}
                      />
                      <RangeeReglage icone="enveloppe" label="E-mail" valeur={compte.email} />
                    </CarteRangees>
                    <Text style={styles.note}>
                      Décrypté ne conserve rien d’autre : ni téléphone, ni date de naissance,
                      ni historique de lecture.
                    </Text>
                  </>
                ) : (
                  <View style={styles.carteTexte}>
                    <Text style={styles.paragraphe}>
                      Décrypté fonctionne sans compte : tout ce qui suit est enregistré sur cet
                      appareil. Un compte sert seulement à retrouver ces réglages ailleurs.
                    </Text>
                    <View style={styles.actionsCompte}>
                      <BoutonPrincipal
                        label="Créer un compte"
                        onPress={() => navigation.navigate('Onboarding')}
                      />
                      <BoutonPrincipal
                        label="Se connecter"
                        variante="contour"
                        onPress={() => navigation.navigate('Connexion')}
                      />
                    </View>
                  </View>
                )}
              </View>

              <View style={styles.bloc}>
                <Text style={styles.entete}>DÉPARTEMENT</Text>
                <CarteRangees>
                  <RangeeReglage
                    icone="epingle"
                    label="Département"
                    valeur={preferences.departement}
                    onPress={() => setSelecteurOuvert(true)}
                    action="Choisir un département"
                  />
                </CarteRangees>
              </View>
            </>
          ) : null}

          {onglet === 'themes' ? (
            <View style={styles.bloc}>
              <Text style={styles.entete}>THÈMES SUIVIS</Text>
              <Text style={styles.paragraphe}>
                {preferences.themes.length === 0
                  ? 'Aucun thème suivi. Les thèmes choisis remontent en tête de l’accueil ; aucune rangée n’est masquée.'
                  : `${preferences.themes.length} thèmes suivis. Ils remontent en tête de l’accueil ; aucune rangée n’est masquée.`}
              </Text>
              {ordonnes.length === 0 ? (
                <Text style={styles.vide}>Les catégories n’ont pas pu être chargées.</Text>
              ) : (
                <View style={styles.grille}>
                  {ordonnes.map((t) => {
                    const theme = t.nom as ThemeScrutin;
                    return (
                      <Chip
                        key={t.nom}
                        large
                        actif={preferences.themes.includes(theme)}
                        label={t.nom}
                        compteur={t.nombre}
                        emoji={themeEmoji[theme] ?? themeEmoji.Autre}
                        action="Suivre le thème"
                        onPress={() => basculerTheme(theme)}
                      />
                    );
                  })}
                </View>
              )}
            </View>
          ) : null}

          {onglet === 'reglages' ? (
            <>
              <View style={styles.bloc}>
                <Text style={styles.entete}>ALERTES</Text>
                <Interrupteur
                  actif={preferences.alertes}
                  onToggle={() =>
                    void enregistrerPreferences({
                      ...preferences,
                      alertes: !preferences.alertes,
                    })
                  }
                  titre={
                    preferences.alertes ? 'Alertes souhaitées' : 'Alertes non souhaitées'
                  }
                  detail="Les alertes n’existent pas encore — ce choix est simplement retenu"
                />
              </View>

              {/* Bloc entier masqué sans compte : il n'y aurait aucune session
                  à quitter, et une carte vide se lirait comme une lacune. */}
              {compte ? (
                <View style={styles.bloc}>
                  <Text style={styles.entete}>SESSION</Text>
                  <CarteRangees>
                    <RangeeReglage
                      icone="sortie"
                      label="Session"
                      valeur="Se déconnecter"
                      detail="Vos préférences resteront sur cet appareil"
                      ton="neutre"
                      onPress={() => void seDeconnecter()}
                      action="Se déconnecter de ce compte"
                    />
                  </CarteRangees>
                </View>
              ) : null}

              <Text style={styles.mentions}>
                Les données de vote proviennent de l’open data de l’Assemblée nationale et du
                Sénat. Décrypté ne conserve ni votre navigation, ni vos recherches.
              </Text>
            </>
          ) : null}
        </View>
      </ScrollView>

      <SelecteurDepartement
        visible={selecteurOuvert}
        selection={preferences.departement}
        onSelect={choisirDepartement}
        onFermer={() => setSelecteurOuvert(false)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  ecran: { flex: 1, backgroundColor: colors.background },
  corps: { paddingHorizontal: spacing.xl, paddingTop: spacing.lg, gap: spacing.xxl },
  couverture: { ...typography.bodySecondary, marginTop: -spacing.sm },
  bloc: { gap: spacing.md },
  entete: { ...typography.overline },
  carteTexte: { gap: spacing.lg },
  paragraphe: { ...typography.bodySecondary },
  actionsCompte: { gap: spacing.sm },
  note: { ...typography.meta, lineHeight: 16 },
  vide: { ...typography.bodySecondary, color: colors.textTertiary },
  grille: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  mentions: { ...typography.meta, lineHeight: 16 },
});
