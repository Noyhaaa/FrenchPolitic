import { useState } from 'react';
import {
  LayoutAnimation,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  UIManager,
  View,
} from 'react-native';

import { colors, radius, serifItalic, spacing, typography } from '@/theme';
import type { Amendement } from '@/types';
import { detailObjetAmendement } from '@/utils/format';

// Animation de dépliage fluide sur Android.
if (
  Platform.OS === 'android' &&
  UIManager.setLayoutAnimationEnabledExperimental
) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const SORT_UI = {
  adopte: { label: 'Adopté', color: colors.adopte },
  rejete: { label: 'Rejeté', color: colors.contre },
  retire: { label: 'Retiré', color: colors.textTertiary },
} as const;

/**
 * Une phrase courte et FACTUELLE pour la ligne épurée : première phrase du
 * dispositif (extrait officiel), sinon la partie descriptive de l'objet,
 * sinon l'objet complet. On extrait/tronque, on ne reformule jamais (§2.5).
 */
function resumeLigne(a: Amendement): string {
  const base = a.dispositif || detailObjetAmendement(a) || a.objet;
  const premiere = base.split('. ')[0].trim();
  return premiere && premiere.length < base.length ? `${premiere}.` : base;
}

interface Props {
  amendement: Amendement;
  /** Ouvre la fiche vote d'un scrutin (amendement OU sous-amendement). */
  onOpenScrutin?: (scrutinId: string) => void;
}

/**
 * Ligne d'amendement « calme » : une pastille de sort + une phrase factuelle +
 * un repère discret (n° · auteur). Au tap, la ligne se DÉPLIE et révèle le
 * contenu — d'abord le FAIT (dispositif, neutre), puis la VOIX (exposé
 * sommaire, point de vue → ambre, italique, §4.3) — ET, seulement là, ses
 * sous-amendements imbriqués (connecteur ↳, tappables vers leur propre vote).
 * Plus de seconde liste de sous-amendements : la hiérarchie est portée par le
 * dépliage. Tout provient du libellé officiel (§2.5).
 */
export function AmendementRow({ amendement: a, onOpenScrutin }: Props) {
  const [ouvert, setOuvert] = useState(false);
  const sort = SORT_UI[a.sort];
  const sous = a.sousAmendements ?? [];

  const toggle = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setOuvert((v) => !v);
  };

  return (
    <View style={[styles.bloc, ouvert && styles.blocOuvert]}>
      <Pressable
        onPress={toggle}
        style={styles.entete}
        accessibilityRole="button"
        accessibilityLabel={`${a.objet}. ${sort.label}. ${
          ouvert ? 'Masquer' : 'Voir'
        } le détail.`}
      >
        <View
          style={[styles.dot, { backgroundColor: sort.color }]}
          importantForAccessibility="no"
        />
        <View style={styles.ligneTexte}>
          <Text style={styles.resume} numberOfLines={ouvert ? undefined : 2}>
            {resumeLigne(a)}
          </Text>
          <Text style={typography.meta}>
            {`n° ${a.numero ?? '—'}`}
            {a.auteur ? ` · ${a.auteur}` : ''}
            {!ouvert && sous.length
              ? ` · ${sous.length} sous-amend.`
              : ''}
          </Text>
        </View>
        <Text
          style={[styles.caret, ouvert && styles.caretOuvert]}
          importantForAccessibility="no"
        >
          {ouvert ? '⌃' : '›'}
        </Text>
      </Pressable>

      {ouvert ? (
        <View style={styles.panneau}>
          {/* Fait + point de vue dans un même flux de lecture : le dispositif
              (neutre), puis l'exposé sommaire précédé du marqueur ambre
              « Selon l'auteur, » qui l'attribue sans le fondre (§4.3). Les deux
              restent des extraits officiels verbatim. */}
          {a.dispositif || a.exposeSommaire ? (
            <Text style={styles.paragraphe}>
              {a.dispositif}
              {a.dispositif && a.exposeSommaire ? ' ' : ''}
              {a.exposeSommaire ? (
                <Text>
                  <Text style={styles.selonAuteur}>Selon l'auteur, </Text>
                  {a.exposeSommaire}
                </Text>
              ) : null}
            </Text>
          ) : null}

          {/* Statut du vote de l'amendement. Le décompte (312 pour · 220
              contre) vit sur `ScrutinDetail` — l'objet `Amendement` ne le porte
              pas ; on n'invente pas de chiffres (§2.5). */}
          <Text style={styles.statut}>{sort.label}</Text>

          {a.scrutinId && onOpenScrutin ? (
            <Pressable
              onPress={() => onOpenScrutin(a.scrutinId!)}
              accessibilityRole="button"
              accessibilityLabel="Voir le vote de cet amendement"
            >
              <Text style={styles.lien}>Voir le vote ›</Text>
            </Pressable>
          ) : null}

          {sous.length ? (
            <View style={styles.sousWrap}>
              <Text style={[typography.overline, styles.sousTitre]}>
                {sous.length} sous-amendement{sous.length > 1 ? 's' : ''}
              </Text>
              {sous.map((sa) => {
                const s = SORT_UI[sa.sort];
                const contenu = (
                  <View style={styles.sousRow}>
                    <Text style={styles.connecteur} importantForAccessibility="no">
                      ↳
                    </Text>
                    <View
                      style={[styles.dotPetit, { backgroundColor: s.color }]}
                      importantForAccessibility="no"
                    />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.sousTexte}>{resumeLigne(sa)}</Text>
                      <Text style={typography.meta}>
                        n° {sa.numero ?? '—'} · {s.label.toLowerCase()}
                      </Text>
                    </View>
                  </View>
                );
                return sa.scrutinId && onOpenScrutin ? (
                  <Pressable
                    key={sa.id}
                    onPress={() => onOpenScrutin(sa.scrutinId!)}
                    style={({ pressed }) => pressed && { opacity: 0.7 }}
                    accessibilityRole="button"
                    accessibilityLabel={`${sa.objet}. ${s.label}. Voir le vote.`}
                  >
                    {contenu}
                  </Pressable>
                ) : (
                  <View key={sa.id}>{contenu}</View>
                );
              })}
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  bloc: {
    marginHorizontal: -spacing.sm,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
  },
  blocOuvert: {
    backgroundColor: 'rgba(255,255,255,0.03)',
  },
  entete: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md + 2,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  ligneTexte: {
    flex: 1,
    gap: spacing.xs,
  },
  resume: {
    ...typography.readingBody,
    fontSize: 16,
    lineHeight: 22,
  },
  caret: {
    color: colors.textTertiary,
    fontSize: 22,
    fontWeight: '600',
  },
  caretOuvert: {
    color: colors.brand,
    fontSize: 15,
  },
  panneau: {
    paddingLeft: spacing.xl,
    paddingBottom: spacing.md,
    gap: spacing.md,
  },
  paragraphe: {
    ...typography.readingBody,
    color: 'rgba(255,255,255,0.82)',
  },
  selonAuteur: {
    fontFamily: serifItalic,
    fontStyle: 'italic',
    color: colors.accentWarm,
  },
  statut: {
    ...typography.meta,
    color: colors.textSecondary,
  },
  lien: {
    ...typography.meta,
    color: colors.brand,
    fontWeight: '600',
  },
  sousWrap: {
    marginTop: spacing.xs,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  sousTitre: {
    marginBottom: spacing.sm,
  },
  sousRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    paddingVertical: spacing.sm - 2,
  },
  connecteur: {
    color: colors.textTertiary,
    fontFamily: typography.meta.fontFamily,
    fontSize: 13,
    lineHeight: 22,
  },
  dotPetit: {
    width: 7,
    height: 7,
    borderRadius: 4,
    marginTop: 8,
  },
  sousTexte: {
    ...typography.readingBody,
    fontSize: 15,
    lineHeight: 21,
  },
});
