import { useCallback, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ApiError } from '@/api';
import { BoutonPrincipal, ChampTexte, IconLigne } from '@/components';
import { useProfil } from '@/session/ProfilContext';
import { colors, mono, radius, serifDisplay, spacing, typography } from '@/theme';
import { emailValide } from '@/utils/validation';

/**
 * Connexion à un compte existant — atteinte depuis le parcours d'accueil
 * (« J'ai déjà un compte ») et depuis le profil.
 *
 * Retrouver son compte **remplace** les préférences locales par celles du
 * serveur : c'est précisément ce qu'on vient demander.
 *
 * ⚠️ Pas de « mot de passe oublié » : rien n'envoie de courrier aujourd'hui, et
 * un lien qui ne mène à rien vaut moins que son absence (§2.5).
 */
export function ConnexionScreen() {
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const { seConnecter } = useProfil();

  const [email, setEmail] = useState('');
  const [motDePasse, setMotDePasse] = useState('');
  const [secret, setSecret] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  const complet = emailValide(email) && motDePasse.length > 0;

  const valider = useCallback(async () => {
    if (!complet || envoi) return;
    setEnvoi(true);
    setErreur(null);
    try {
      await seConnecter(email.trim(), motDePasse);
      navigation.goBack();
    } catch (err) {
      setErreur(
        err instanceof ApiError
          ? err.isNetwork
            ? 'Serveur injoignable. Réessayez quand la connexion sera revenue.'
            : err.message
          : 'La connexion a échoué.',
      );
    } finally {
      setEnvoi(false);
    }
  }, [complet, email, envoi, motDePasse, navigation, seConnecter]);

  return (
    <View style={[styles.ecran, { paddingTop: insets.top }]}>
      <View style={styles.entete}>
        <Pressable
          onPress={navigation.goBack}
          style={styles.retour}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel="Revenir à l’écran précédent"
        >
          <IconLigne
            name="chevronGauche"
            color={colors.textSecondary}
            size={20}
            strokeWidth={2}
          />
          <Text style={styles.retourTexte}>Retour</Text>
        </Pressable>
      </View>

      <KeyboardAvoidingView
        style={styles.corps}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={insets.top + 40}
      >
        <ScrollView
          contentContainerStyle={styles.contenu}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <Text style={styles.eyebrow}>Décrypté · Votre compte</Text>
          <Text style={styles.titre}>Se connecter</Text>
          <Text style={styles.chapeau}>
            Vos thèmes et votre département reviendront tels que vous les aviez
            enregistrés.
          </Text>

          <View style={styles.champs}>
            <ChampTexte
              label="Adresse e-mail"
              icone="enveloppe"
              valeur={email}
              onChangeText={setEmail}
              placeholder="alexandra@exemple.fr"
              valide={email.length > 0 ? emailValide(email) : undefined}
              aide="Format invalide"
              keyboardType="email-address"
              textContentType="emailAddress"
            />
            <ChampTexte
              label="Mot de passe"
              icone="cadenas"
              valeur={motDePasse}
              onChangeText={setMotDePasse}
              placeholder="Votre mot de passe"
              secret={secret}
              onBasculerSecret={() => setSecret((s) => !s)}
              textContentType="password"
              returnKeyType="done"
              onSubmitEditing={() => void valider()}
            />
          </View>

          {erreur ? (
            <View style={styles.erreur}>
              <Text style={styles.erreurTexte}>{erreur}</Text>
            </View>
          ) : null}

          <BoutonPrincipal
            label="Se connecter"
            onPress={() => void valider()}
            desactive={!complet}
            enCours={envoi}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  ecran: { flex: 1, backgroundColor: colors.background },
  entete: { paddingHorizontal: spacing.xl, paddingTop: spacing.md },
  retour: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm + 2 },
  retourTexte: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  corps: { flex: 1 },
  contenu: { paddingHorizontal: spacing.xl, paddingTop: spacing.xl, gap: spacing.lg },
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
    fontSize: 32,
    lineHeight: 38,
    letterSpacing: -0.5,
    color: colors.textPrimary,
    marginTop: -spacing.sm,
  },
  chapeau: { ...typography.bodySecondary, marginTop: -spacing.sm, maxWidth: 300 },
  champs: { gap: spacing.lg, marginTop: spacing.sm },
  erreur: {
    backgroundColor: 'rgba(232,105,94,0.10)',
    borderWidth: 1,
    borderColor: 'rgba(232,105,94,0.30)',
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  erreurTexte: { ...typography.bodySecondary, color: colors.invalide },
});
