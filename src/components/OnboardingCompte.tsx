import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, mono, radius, serifDisplay, spacing, typography } from '@/theme';
import {
  LIBELLE_FORCE,
  MOT_DE_PASSE_MIN,
  emailValide,
  forceMotDePasse,
  motDePasseValide,
  nomValide,
} from '@/utils/validation';
import { ChampTexte } from './ChampTexte';

/**
 * Étape 2 — le compte.
 *
 * ⚠️ **Facultatif** : cette étape se passe (« Je verrai plus tard »), et l'app
 * fonctionne alors entièrement, préférences comprises — elles restent sur
 * l'appareil. Le compte ne sert qu'à les retrouver ailleurs, et c'est ce que
 * l'écran annonce plutôt qu'un bénéfice vague.
 *
 * ⚠️ **Quatre champs, pas six.** La maquette demandait aussi un téléphone et
 * une date de naissance : rien dans le produit ne les utilise, on ne les
 * collecte donc pas.
 */

export interface SaisieCompte {
  prenom: string;
  nom: string;
  email: string;
  motDePasse: string;
}

export const SAISIE_COMPTE_VIDE: SaisieCompte = {
  prenom: '',
  nom: '',
  email: '',
  motDePasse: '',
};

export function compteComplet(s: SaisieCompte): boolean {
  return (
    nomValide(s.prenom) &&
    nomValide(s.nom) &&
    emailValide(s.email) &&
    motDePasseValide(s.motDePasse)
  );
}

/** Un compte n'est tenté que si l'utilisateur a commencé à le remplir. */
export function compteAmorce(s: SaisieCompte): boolean {
  return (
    s.prenom.length > 0 ||
    s.nom.length > 0 ||
    s.email.length > 0 ||
    s.motDePasse.length > 0
  );
}

const COULEURS_FORCE = [colors.invalide, colors.valide, colors.faible, colors.fort];

interface Props {
  saisie: SaisieCompte;
  onChange: (champ: keyof SaisieCompte, valeur: string) => void;
  /** Message d'échec renvoyé par l'API (adresse déjà prise, réseau…). */
  erreur?: string | null;
  onOuvrirConnexion: () => void;
}

export function OnboardingCompte({ saisie, onChange, erreur, onOuvrirConnexion }: Props) {
  const [secret, setSecret] = useState(true);
  const force = forceMotDePasse(saisie.motDePasse);

  return (
    <ScrollView
      style={styles.flux}
      contentContainerStyle={styles.contenu}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
    >
      <Text style={styles.titre}>Créez votre compte</Text>
      <Text style={styles.chapeau}>
        Il sert à retrouver vos thèmes et votre département sur un autre appareil.
        Rien d’autre n’est enregistré : ni ce que vous lisez, ni ce que vous cherchez.
      </Text>

      <View style={styles.rangee}>
        <ChampTexte
          label="Prénom"
          icone="personne"
          valeur={saisie.prenom}
          onChangeText={(v) => onChange('prenom', v)}
          placeholder="Alexandra"
          valide={saisie.prenom.length > 0 ? nomValide(saisie.prenom) : undefined}
          aide="2 caractères minimum"
          autoCapitalize="words"
          textContentType="givenName"
        />
        <ChampTexte
          label="Nom"
          icone="personne"
          valeur={saisie.nom}
          onChangeText={(v) => onChange('nom', v)}
          placeholder="Müller"
          valide={saisie.nom.length > 0 ? nomValide(saisie.nom) : undefined}
          aide="2 caractères minimum"
          autoCapitalize="words"
          textContentType="familyName"
        />
      </View>

      <ChampTexte
        label="Adresse e-mail"
        icone="enveloppe"
        valeur={saisie.email}
        onChangeText={(v) => onChange('email', v)}
        placeholder="alexandra@exemple.fr"
        valide={saisie.email.length > 0 ? emailValide(saisie.email) : undefined}
        aide="Format invalide"
        keyboardType="email-address"
        textContentType="emailAddress"
      />

      <ChampTexte
        label="Mot de passe"
        icone="cadenas"
        valeur={saisie.motDePasse}
        onChangeText={(v) => onChange('motDePasse', v)}
        placeholder={`${MOT_DE_PASSE_MIN} caractères minimum`}
        valide={
          saisie.motDePasse.length > 0 ? motDePasseValide(saisie.motDePasse) : undefined
        }
        aide={`Au moins ${MOT_DE_PASSE_MIN} caractères`}
        secret={secret}
        onBasculerSecret={() => setSecret((s) => !s)}
        textContentType="newPassword"
        returnKeyType="done"
      />

      {saisie.motDePasse.length > 0 ? (
        <View style={styles.jauge}>
          <View style={styles.jaugeBarres}>
            {[1, 2, 3, 4].map((niveau) => (
              <View
                key={niveau}
                style={[
                  styles.jaugeBarre,
                  {
                    backgroundColor:
                      niveau <= force ? COULEURS_FORCE[force - 1] : colors.surfaceMuted,
                  },
                ]}
              />
            ))}
          </View>
          <Text style={styles.jaugeTexte}>{LIBELLE_FORCE[force]}</Text>
        </View>
      ) : null}

      {erreur ? (
        <View style={styles.erreur}>
          <Text style={styles.erreurTexte}>{erreur}</Text>
        </View>
      ) : null}

      <Pressable
        onPress={onOuvrirConnexion}
        style={styles.lien}
        accessibilityRole="button"
        accessibilityLabel="J’ai déjà un compte, me connecter"
      >
        <Text style={styles.lienTexte}>J’ai déjà un compte</Text>
      </Pressable>

      <Text style={styles.mentions}>
        En créant un compte, vous acceptez que ces informations soient conservées pour
        retrouver vos préférences. Vous pouvez continuer sans compte : le bouton
        « Passer » plus haut vous emmène directement dans l’app.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  flux: { flex: 1 },
  contenu: { paddingHorizontal: spacing.xl, paddingBottom: spacing.xl, gap: spacing.lg },
  titre: {
    fontFamily: serifDisplay,
    fontSize: 30,
    lineHeight: 36,
    letterSpacing: -0.5,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  chapeau: { ...typography.bodySecondary, marginTop: -spacing.sm },
  rangee: { flexDirection: 'row', gap: spacing.md },
  jauge: { marginTop: -spacing.sm, gap: spacing.xs + 2 },
  jaugeBarres: { flexDirection: 'row', gap: spacing.xs },
  jaugeBarre: { flex: 1, height: 4, borderRadius: radius.pill },
  jaugeTexte: {
    fontFamily: mono,
    fontSize: 10.5,
    letterSpacing: 0.6,
    color: colors.textTertiary,
  },
  erreur: {
    backgroundColor: 'rgba(232,105,94,0.10)',
    borderWidth: 1,
    borderColor: 'rgba(232,105,94,0.30)',
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  erreurTexte: { ...typography.bodySecondary, color: colors.invalide },
  lien: { alignSelf: 'flex-start' },
  lienTexte: { ...typography.label, color: colors.brand, textDecorationLine: 'underline' },
  mentions: { ...typography.meta, lineHeight: 16, color: colors.textTertiary },
});
