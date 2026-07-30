"""Tests d'ingestion open data (parsing pur, sans réseau ni base)."""
from __future__ import annotations

from app.domain.enums import PositionVote, StatutScrutin
from app.ingestion.assemblee import parse_scrutin
from app.ingestion.normalize import (
    auteur_amendement,
    deposant,
    est_amendement,
    est_sous_amendement,
    guess_theme,
    map_position,
    map_statut,
    numero_amendement,
    numero_amendement_parent,
    texte_de_rattachement,
    titre_court,
    truncate_mots,
)
from app.ingestion.organes import build_acteurs_from_amo, build_resolver_from_organes
from app.schemas import ScrutinResume, SourceOfficielle
from app.ingestion.sync import (
    _merge_avec_existant,
    build_dossier,
    controles_coherence,
)

ORGANES = [
    {"organe": {"uid": "PO845401", "codeType": "GP", "libelle": "Rassemblement National", "libelleAbrev": "RN", "viMoDe": {"dateFin": None}}},
    {"organe": {"uid": "PO845413", "codeType": "GP", "libelle": "La France insoumise - NFP", "libelleAbrev": "LFI-NFP", "viMoDe": {"dateFin": None}}},
    {"organe": {"uid": "PO000000", "codeType": "GP", "libelle": "Groupe dissous", "libelleAbrev": "OLD", "viMoDe": {"dateFin": "2024-01-01"}}},
    {"organe": {"uid": "PO111111", "codeType": "COMPER", "libelle": "Une commission"}},
]

ACTEURS = [
    {"acteur": {"uid": {"#text": "PA100"}, "etatCivil": {"ident": {"civ": "Mme", "prenom": "Jeanne", "nom": "Martin"}}}},
    {"acteur": {"uid": {"#text": "PA200"}, "etatCivil": {"ident": {"civ": "M.", "prenom": "Paul", "nom": "Durand"}}}},
    {"acteur": {"uid": "PA300", "etatCivil": {"ident": {"prenom": "Luc", "nom": "Bernard"}}}},
]

SCRUTIN = {
    "scrutin": {
        "uid": "VTANR5L17V999",
        "numero": "999",
        "legislature": "17",
        "dateScrutin": "2026-07-02",
        "sort": {"code": "rejeté"},
        "titre": "l'amendement n° 80 de Mme X",
        "objet": {
            "libelle": "l'amendement n° 80 de Mme X",
            "dossierLegislatif": {
                "libelle": "Projet de loi sur le logement social",
                "dossierRef": "DLR5L17N53940",
            },
        },
        "syntheseVote": {
            "decompte": {"nonVotants": "1", "pour": "21", "contre": "39", "abstentions": "4"}
        },
        "ventilationVotes": {
            "organe": {
                "organeRef": "PO838901",
                "groupes": {
                    "groupe": [
                        {
                            "organeRef": "PO845401",
                            "vote": {
                                "positionMajoritaire": "contre",
                                "decompteVoix": {"pour": "0", "contre": "10", "abstentions": "0"},
                                "decompteNominatif": {
                                    "pours": None,
                                    # 1 votant → objet (pas liste) : cas réel de l'open data.
                                    "contres": {"votant": {"acteurRef": "PA100"}},
                                    "abstentions": None,
                                },
                            },
                        },
                        {
                            "organeRef": "PO845413",
                            "vote": {
                                "positionMajoritaire": "pour",
                                "decompteVoix": {"pour": "21", "contre": "29", "abstentions": "4"},
                                "decompteNominatif": {
                                    "pours": {"votant": [{"acteurRef": "PA200"}, {"acteurRef": "PA_INCONNU"}]},
                                    "contres": None,
                                    "abstentions": {"votant": [{"acteurRef": "PA300"}]},
                                },
                            },
                        },
                    ]
                },
            }
        },
    }
}


def test_resolver_noms_et_couleurs():
    resolver = build_resolver_from_organes(ORGANES)
    assert len(resolver) == 2  # dissous et non-GP exclus
    rn = resolver.resolve("PO845401")
    assert rn.nom == "Rassemblement National"
    assert rn.couleur == "#1B3A5C"


def test_resolver_ref_inconnue_ne_fabrique_pas_de_nom():
    resolver = build_resolver_from_organes(ORGANES)
    inconnu = resolver.resolve("PO_INEXISTANT")
    assert inconnu.nom == "PO_INEXISTANT"


def test_annuaire_acteurs():
    acteurs = build_acteurs_from_amo(ACTEURS)
    assert acteurs["PA100"] == "Jeanne Martin"
    assert acteurs["PA300"] == "Luc Bernard"  # uid en chaîne simple aussi accepté


def test_parse_nominatif_avec_annuaire():
    resolver = build_resolver_from_organes(ORGANES)
    acteurs = build_acteurs_from_amo(ACTEURS)
    s = parse_scrutin(SCRUTIN, resolver, acteurs).scrutin

    rn, lfi = s.positions_groupes
    # Votant unique sérialisé en objet (cas réel de l'open data).
    assert [v.nom for v in rn.votants_contre] == ["Jeanne Martin"]
    assert rn.votants_pour is None  # bloc absent → masqué, pas inventé (§2.5)
    # Acteur absent de l'annuaire → RETIRÉ : sa référence machine (« PA_INCONNU »)
    # n'est pas un nom, l'afficher tromperait le lecteur (§2.5, §8).
    assert [v.nom for v in lfi.votants_pour] == ["Paul Durand"]
    assert [v.nom for v in lfi.votants_abstention] == ["Luc Bernard"]


def test_parse_nominatif_identifiant_reserve_aux_deputes_en_exercice():
    # `depute_id` autorise l'app à ouvrir la fiche : il n'est posé que pour les
    # acteurs du référentiel servi par l'API, jamais pour un ancien député —
    # sinon le lien mènerait à un 404.
    resolver = build_resolver_from_organes(ORGANES)
    acteurs = build_acteurs_from_amo(ACTEURS)
    s = parse_scrutin(
        SCRUTIN, resolver, acteurs, deputes_connus=frozenset({"PA200"})
    ).scrutin

    rn, lfi = s.positions_groupes
    assert lfi.votants_pour[0].depute_id == "PA200"  # siège aujourd'hui
    assert rn.votants_contre[0].nom == "Jeanne Martin"
    assert rn.votants_contre[0].depute_id is None  # nommée, mais plus en exercice


def test_parse_nominatif_sans_referentiel_aucun_identifiant():
    resolver = build_resolver_from_organes(ORGANES)
    acteurs = build_acteurs_from_amo(ACTEURS)
    s = parse_scrutin(SCRUTIN, resolver, acteurs).scrutin
    assert all(
        v.depute_id is None
        for g in s.positions_groupes
        for v in (g.votants_pour or []) + (g.votants_contre or [])
    )


def test_parse_sans_annuaire_pas_de_noms():
    resolver = build_resolver_from_organes(ORGANES)
    s = parse_scrutin(SCRUTIN, resolver).scrutin
    assert all(
        g.votants_pour is None and g.votants_contre is None
        for g in s.positions_groupes
    )


def test_parse_scrutin_complet():
    resolver = build_resolver_from_organes(ORGANES)
    parse = parse_scrutin(SCRUTIN, resolver)
    s = parse.scrutin

    assert s.id == "VTANR5L17V999"
    assert s.dossier_id == "DLR5L17N53940"
    assert s.statut == StatutScrutin.rejete
    assert s.date == "2026-07-02"
    # Objet = ce sur quoi on a voté (le scrutin lui-même).
    assert s.objet == "l'amendement n° 80 de Mme X"
    # Le titre du dossier (plus lisible) est porté par le ScrutinParse.
    assert parse.dossier_titre == "Projet de loi sur le logement social"
    assert parse.theme == "Logement"  # deviné par mot-clé
    assert s.resultat.pour == 21 and s.resultat.contre == 39
    assert s.resultat.abstention == 4 and s.resultat.non_votants == 1
    assert len(s.positions_groupes) == 2
    assert s.positions_groupes[0].groupe_nom == "Rassemblement National"
    assert s.scrutin_public is True


def _sans_dossier_ref(objet: str) -> dict:
    """Une variante de SCRUTIN sans dossierRef, à objet choisi."""
    import copy

    brut = copy.deepcopy(SCRUTIN)
    brut["scrutin"]["titre"] = objet
    brut["scrutin"]["objet"]["libelle"] = objet
    del brut["scrutin"]["objet"]["dossierLegislatif"]
    return brut


def test_texte_de_rattachement():
    assert texte_de_rattachement(
        "l'amendement n° 39 de M. Mattei à l'article 2 de la proposition de loi "
        "visant à lutter contre la fraude."
    ) == "Proposition de loi visant à lutter contre la fraude"
    # La mention de lecture est retirée : même texte → même dossier.
    assert texte_de_rattachement(
        "l'ensemble du projet de loi de finances pour 2026 (première lecture)"
    ) == "Projet de loi de finances pour 2026"
    # Aucun texte cité → None (motion de censure, déclaration…).
    assert texte_de_rattachement(
        "la motion de censure déposée en application de l'article 49, alinéa 2"
    ) is None


def test_texte_de_rattachement_retire_les_mentions_enchainees():
    """La source enchaîne parfois DEUX mentions de procédure.

    Cas réel : n'en retirer qu'une laissait « (seconde délibération) » dans le
    titre, sa signature ne correspondait plus au titre officiel, et le texte se
    dédoublait en un `TXT-…` vide à côté de son vrai dossier (vécu sur l'aide à
    mourir, le PLF 2026 et Mayotte).
    """
    assert texte_de_rattachement(
        "l'article 4 de la proposition de loi relative au droit à l'aide à "
        "mourir (seconde délibération) (deuxième lecture)."
    ) == "Proposition de loi relative au droit à l'aide à mourir"


def test_texte_de_rattachement_garde_une_parenthese_interne():
    """Seule la FIN est de la procédure : une parenthèse au milieu du titre fait
    partie de ce que la source désigne et doit survivre."""
    attendu = "Proposition de loi visant à abroger l'article 24 (supprimé) du code pénal"
    assert texte_de_rattachement(
        "l'ensemble de la proposition de loi visant à abroger l'article 24 "
        "(supprimé) du code pénal."
    ) == attendu
    # Et elle survit même quand une mention de procédure la suit.
    assert texte_de_rattachement(
        "l'ensemble de la proposition de loi visant à abroger l'article 24 "
        "(supprimé) du code pénal (deuxième lecture)."
    ) == attendu


def test_sans_dossier_ref_regroupe_par_texte_cite():
    """Sans dossierRef, les votes citant le même texte partagent un dossier
    reconstitué — le fil montre le texte, pas chaque amendement (pas de
    pollution en singletons)."""
    resolver = build_resolver_from_organes(ORGANES)
    a = parse_scrutin(
        _sans_dossier_ref(
            "l'amendement n° 4 de M. Y à l'article 2 de la proposition de loi "
            "visant à protéger la ressource en eau"
        ),
        resolver,
    )
    b = parse_scrutin(
        _sans_dossier_ref(
            "l'ensemble de la proposition de loi visant à protéger la ressource "
            "en eau (première lecture)"
        ),
        resolver,
    )
    assert a.dossier_id.startswith("TXT-")
    assert a.dossier_id == b.dossier_id  # même texte → même dossier
    assert (
        a.dossier_titre
        == "Proposition de loi visant à protéger la ressource en eau"
    )
    assert a.dossier_ref is None  # pas de page de dossier inventée (§2.5)


def test_sans_dossier_ref_ni_texte_reste_singleton():
    """Un vote autonome (motion de censure…) reste son propre dossier, et se
    déclare comme tel : il n'a pas d'articles, donc pas de « qu'est-ce que ça
    change ? » à afficher (§2.5, l'app masque au lieu d'annoncer un manque)."""
    resolver = build_resolver_from_organes(ORGANES)
    p = parse_scrutin(
        _sans_dossier_ref("la motion de censure déposée par 185 députés"),
        resolver,
    )
    assert p.dossier_id == "VTANR5L17V999"  # l'uid du scrutin
    assert p.est_evenement_autonome


def test_vote_sur_un_texte_n_est_pas_un_evenement_autonome():
    """Le drapeau ne doit pas déborder : un vote citant un texte porte sur un
    texte, même sans `dossierRef`."""
    resolver = build_resolver_from_organes(ORGANES)
    p = parse_scrutin(
        _sans_dossier_ref(
            "l'ensemble de la proposition de loi visant à protéger la ressource en eau"
        ),
        resolver,
    )
    assert not p.est_evenement_autonome


# Documents « dossiers législatifs » factices pour la réconciliation.
_DOCS = [
    {
        "document": {
            "dossierRef": "DLR5L17N9001",
            "denominationStructurelle": "Proposition de loi",
            "titres": {
                "titrePrincipal": "Proposition de loi visant à protéger la ressource en eau"
            },
        }
    },
    {
        "document": {  # rapport : même thème mais ignoré (pas un texte de loi)
            "dossierRef": "DLR5L17N9001",
            "denominationStructurelle": "Rapport",
            "titres": {"titrePrincipal": "Rapport sur la ressource en eau"},
        }
    },
    {
        "document": {  # autre législature : ne doit jamais matcher la 17e
            "dossierRef": "DLR5L16N1234",
            "denominationStructurelle": "Proposition de loi",
            "titres": {"titrePrincipal": "Proposition de loi d'une autre législature"},
        }
    },
]


def test_reconciliation_retrouve_le_vrai_dossier():
    """Un scrutin sans dossierRef dont l'objet cite un texte connu récupère son
    vrai dossierRef (et donc son lien officiel), au lieu d'un TXT-…"""
    from app.ingestion.dossiers_legislatifs import construire_reconciliation

    resolver = build_resolver_from_organes(ORGANES)
    reco = construire_reconciliation(_DOCS, legislatures=(17,))
    p = parse_scrutin(
        _sans_dossier_ref(
            "l'amendement n° 4 à l'article 2 de la proposition de loi visant à "
            "protéger la ressource en eau"
        ),
        resolver,
        reconciliation=reco,
    )
    assert p.dossier_id == "DLR5L17N9001"
    assert p.dossier_ref == "DLR5L17N9001"
    # Titre canonique de l'archive adopté.
    assert p.dossier_titre == "Proposition de loi visant à protéger la ressource en eau"


def test_reconciliation_sans_correspondance_reste_txt():
    """Titre inconnu de l'archive → dossier reconstitué (pas d'invention)."""
    from app.ingestion.dossiers_legislatifs import construire_reconciliation

    resolver = build_resolver_from_organes(ORGANES)
    reco = construire_reconciliation(_DOCS, legislatures=(17,))
    p = parse_scrutin(
        _sans_dossier_ref(
            "l'ensemble de la proposition de loi sur un tout autre sujet"
        ),
        resolver,
        reconciliation=reco,
    )
    assert p.dossier_id.startswith("TXT-")
    assert p.dossier_ref is None


# Archive « sale » : espace manquant (« ressourceen »), apostrophe courbe.
_DOCS_SALES = [
    {
        "document": {
            "dossierRef": "DLR5L17N9100",
            "denominationStructurelle": "Proposition de loi",
            "titres": {  # faute de frappe de l'archive : « à protégerla ressource »
                "titrePrincipal": "proposition de loi visant à protégerla ressource en eau"
            },
        }
    },
    {
        "document": {  # variante organique : même sujet, dossier DISTINCT
            "dossierRef": "DLR5L17N9101",
            "denominationStructurelle": "Proposition de loi",
            "titres": {
                "titrePrincipal": "proposition de loi organique visant à protéger la ressource en eau"
            },
        }
    },
]


def test_reconciliation_signature_rattrape_la_saleté_de_l_archive():
    """Une faute de frappe de l'archive (espace manquant) n'empêche plus la
    correspondance : la signature (sans espaces/ponctuation) rattrape."""
    from app.ingestion.dossiers_legislatifs import construire_reconciliation

    resolver = build_resolver_from_organes(ORGANES)
    reco = construire_reconciliation(_DOCS_SALES, legislatures=(17,))
    p = parse_scrutin(
        _sans_dossier_ref(
            "l'article 2 de la proposition de loi visant à protéger la ressource en eau"
        ),
        resolver,
        reconciliation=reco,
    )
    # Rattaché à la version ordinaire (N9100), PAS à l'organique (N9101) :
    # la nature « organique » est conservée dans la signature.
    assert p.dossier_ref == "DLR5L17N9100"


def test_reconciliation_signature_preserve_la_distinction_organique():
    """Le vote sur le texte organique va bien à l'organique, pas à l'ordinaire."""
    from app.ingestion.dossiers_legislatifs import construire_reconciliation

    resolver = build_resolver_from_organes(ORGANES)
    reco = construire_reconciliation(_DOCS_SALES, legislatures=(17,))
    p = parse_scrutin(
        _sans_dossier_ref(
            "l'ensemble de la proposition de loi organique visant à protéger la "
            "ressource en eau"
        ),
        resolver,
        reconciliation=reco,
    )
    assert p.dossier_ref == "DLR5L17N9101"


def test_reconciliation_retrouve_un_dossier_reporte_de_la_legislature_precedente():
    """Un dossier reporté après une dissolution garde son `dossierRef` d'origine
    (ex. réel : « simplification de la vie économique », ref L16, encore voté en
    L17). Élargir la fenêtre à (17, 16) le retrouve ; s'en tenir à (17,) seul le
    manque toujours (comportement historique préservé, §2.5 : pas de régression
    silencieuse sur les autres tests qui appellent avec `legislatures=(17,)`)."""
    from app.ingestion.dossiers_legislatifs import construire_reconciliation

    resolver = build_resolver_from_organes(ORGANES)
    scrutin = _sans_dossier_ref(
        "l'ensemble de la proposition de loi d'une autre législature"
    )

    reco_large = construire_reconciliation(_DOCS, legislatures=(17, 16))
    p_large = parse_scrutin(scrutin, resolver, reconciliation=reco_large)
    assert p_large.dossier_ref == "DLR5L16N1234"

    reco_etroite = construire_reconciliation(_DOCS, legislatures=(17,))
    p_etroite = parse_scrutin(scrutin, resolver, reconciliation=reco_etroite)
    assert p_etroite.dossier_ref is None
    assert p_etroite.dossier_id.startswith("TXT-")


def test_txt_id_fusionne_les_variantes_d_apostrophe():
    """Un même texte cité avec une apostrophe droite (') sur un scrutin et
    courbe (’) sur un autre doit fusionner en un seul dossier `TXT-…`, pas se
    scinder en deux (vécu en production : « statut de l'élu local » dupliqué).
    L'id est donc dérivé de la signature du titre (fold + sans ponctuation),
    pas du simple fold — même normalisation que la réconciliation d'archive."""
    resolver = build_resolver_from_organes(ORGANES)
    p_droite = parse_scrutin(
        _sans_dossier_ref(
            "l'ensemble de la proposition de loi portant création d'un statut "
            "de l'élu local"
        ),
        resolver,
    )
    p_courbe = parse_scrutin(
        _sans_dossier_ref(
            "l'ensemble de la proposition de loi portant création d’un statut "
            "de l’élu local"
        ),
        resolver,
    )
    assert p_droite.dossier_id.startswith("TXT-")
    assert p_droite.dossier_id == p_courbe.dossier_id


# Titre officiel long ; l'objet du vote le cite tronqué (l'API AN tronque
# parfois l'objet d'un scrutin aux alentours de 90 caractères — vécu en
# production sur plusieurs dossiers `TXT-` réels).
_DOCS_LONG_TITRE = [
    {
        "document": {
            "dossierRef": "DLR5L17N9300",
            "denominationStructurelle": "Proposition de loi",
            "titres": {
                "titrePrincipal": (
                    "Proposition de loi visant à mettre en place un dispositif "
                    "exceptionnel de soutien aux exploitations agricoles sinistrées"
                )
            },
        }
    },
]


def test_reconciliation_par_prefixe_rattrape_un_objet_tronque():
    """Un objet de vote tronqué en plein mot (avant la fin du titre officiel)
    est quand même reconnu, via correspondance par préfixe — non ambiguë ici
    (un seul dossier commence par ce préfixe)."""
    from app.ingestion.dossiers_legislatifs import construire_reconciliation

    resolver = build_resolver_from_organes(ORGANES)
    reco = construire_reconciliation(_DOCS_LONG_TITRE, legislatures=(17,))
    p = parse_scrutin(
        _sans_dossier_ref(
            "l'ensemble de la proposition de loi visant à mettre en place un "
            "dispositif exceptionnel de sou"  # coupé en plein mot, comme l'API AN
        ),
        resolver,
        reconciliation=reco,
    )
    assert p.dossier_ref == "DLR5L17N9300"


def test_reconciliation_par_prefixe_abstient_si_ambigu():
    """Deux dossiers différents partagent le même préfixe (assez long) →
    abstention plutôt que deviner (§2.5)."""
    from app.ingestion.dossiers_legislatifs import construire_reconciliation

    docs = _DOCS_LONG_TITRE + [
        {
            "document": {
                "dossierRef": "DLR5L17N9301",
                "denominationStructurelle": "Proposition de loi",
                "titres": {
                    "titrePrincipal": (
                        "Proposition de loi visant à mettre en place un dispositif "
                        "exceptionnel de soutien aux pêcheurs sinistrés"
                    )
                },
            }
        },
    ]
    resolver = build_resolver_from_organes(ORGANES)
    reco = construire_reconciliation(docs, legislatures=(17,))
    p = parse_scrutin(
        _sans_dossier_ref(
            "l'ensemble de la proposition de loi visant à mettre en place un "
            "dispositif exceptionnel de sou"
        ),
        resolver,
        reconciliation=reco,
    )
    assert p.dossier_ref is None
    assert p.dossier_id.startswith("TXT-")


def _scrutin_derive(resolver, uid, date, objet):
    """Un ScrutinParse dérivé de SCRUTIN (même dossier), à objet/id/date choisis."""
    p = parse_scrutin(SCRUTIN, resolver)
    p.scrutin = p.scrutin.model_copy(update={"id": uid, "date": date, "objet": objet})
    return p


def _vote_texte(resolver, uid, date, objet="l'ensemble du projet de loi"):
    """Un ScrutinParse « vote sur le texte »."""
    return _scrutin_derive(resolver, uid, date, objet)


_OBJET_SOUS = "le sous-amendement n° 5 de M. Zed à l'amendement n° 80 de Mme X"


def test_est_amendement():
    assert est_amendement("l'amendement n° 80 de Mme X")
    assert est_amendement("Sous-amendement n° 3 à l'article 5")
    assert not est_amendement("l'ensemble du projet de loi")
    assert not est_amendement("l'article 2")


def test_est_sous_amendement():
    assert est_sous_amendement(_OBJET_SOUS)
    assert est_amendement(_OBJET_SOUS)  # un sous-amendement reste un amendement
    assert not est_sous_amendement("l'amendement n° 80 de Mme X")


def test_numero_amendement():
    assert numero_amendement("l'amendement n° 80 de Mme X") == "80"
    assert numero_amendement("l'amendement de suppression n° 25") == "25"
    assert numero_amendement(_OBJET_SOUS) == "5"  # numéro du sous-amendement
    assert numero_amendement("l'ensemble du projet de loi") is None


def test_numero_amendement_parent():
    assert numero_amendement_parent(_OBJET_SOUS) == "80"
    # Pas de parent mentionné → rien d'inventé.
    assert numero_amendement_parent("le sous-amendement n° 5 de M. Zed") is None


def test_auteur_amendement():
    assert auteur_amendement("l'amendement n° 674 de M. Léaument") == "M. Léaument"
    # Sous-amendement : l'auteur du parent (« … de Mme X ») est ignoré.
    assert auteur_amendement(_OBJET_SOUS) == "M. Zed"
    # Plusieurs auteurs (amendements identiques) → ambigu → None (§2.5).
    assert (
        auteur_amendement("l'amendement n° 4 de M. Un et l'amendement n° 9 de Mme Deux")
        is None
    )
    assert auteur_amendement("l'ensemble du projet de loi") is None


def test_deposant_lu_dans_l_objet_officiel():
    # Mention explicite (AN puis Sénat), et nature du texte (art. 39).
    assert deposant("l'amendement n° 7 du Gouvernement au projet de loi agricole") == (
        "gouvernement"
    )
    assert deposant(
        "l'amendement n° 441, présenté par le Gouvernement, à l'article 8 du "
        "projet de loi portant simplification"
    ) == "gouvernement"
    assert deposant("l'ensemble du projet de loi de finances") == "gouvernement"
    assert deposant(
        "l'amendement n° 3 de M. Fugit à la proposition de loi visant à informer"
    ) == "parlementaire"
    assert deposant("l'ensemble de la proposition de résolution") == "parlementaire"
    # Sous-amendement : le déposant du parent ne compte pas, comme pour l'auteur.
    assert deposant(
        "le sous-amendement n° 9 du Gouvernement à l'amendement n° 80 de Mme Galzy"
    ) == "gouvernement"


def test_deposant_d_un_amendement_ignore_la_nature_du_texte():
    # Un député amende couramment un PROJET de loi : « … à l'article 3 du projet
    # de loi » désigne le déposant du TEXTE, pas celui de l'amendement. Seule la
    # mention explicite compte ici (sinon le garde-fou accuserait à tort).
    assert deposant(
        "l'amendement n° 12 de M. Dupont à l'article 3 du projet de loi"
    ) == "parlementaire"
    assert deposant(
        "l'amendement n° 900 du Gouvernement à la proposition de loi visant à agir"
    ) == "gouvernement"
    assert deposant(
        "l'amendement n° 5 de la commission des lois à la proposition de loi"
    ) == "commission"
    # Auteur non cité par l'objet → rien de déduit de la nature du texte (§2.5).
    assert deposant(
        "l'amendement n° 500 après l'article 4 du projet de loi de finances"
    ) is None


def test_deposant_none_quand_la_source_est_ambigue():
    # « texte de la commission mixte paritaire » = mention de procédure, pas un
    # déposant : elle ne doit pas rendre l'objet ambigu.
    assert deposant(
        "l'amendement n° 7 du Gouvernement au projet de loi agricole "
        "(texte de la commission mixte paritaire)"
    ) == "gouvernement"
    # Amendements identiques de deux camps → on ne choisit pas.
    assert deposant(
        "les amendements identiques n° 4 du Gouvernement et n° 9 de Mme Deux"
    ) is None
    assert deposant("l'ensemble de la motion de censure") is None


def test_build_dossier_partitionne_texte_et_amendement():
    """Les votes d'amendement vont dans `amendements` (avec lien), pas dans la
    liste des votes sur le texte."""
    resolver = build_resolver_from_organes(ORGANES)
    amend = parse_scrutin(SCRUTIN, resolver)  # objet = « l'amendement n° 80… »
    texte = _vote_texte(resolver, "VT_TEXTE", "2026-07-10")

    dossier = build_dossier([amend, texte])

    assert dossier.id == "DLR5L17N53940"
    assert len(dossier.scrutins) == 1  # seul le vote sur le texte
    assert dossier.scrutins[0].objet == "l'ensemble du projet de loi"
    assert len(dossier.amendements) == 1
    am = dossier.amendements[0]
    assert am.scrutin_id == amend.scrutin.id  # cliquable vers la page du vote
    assert am.sort.value == "rejete"
    # Numéro et auteur extraits de l'objet officiel (affichage compact).
    assert am.numero == "80"
    assert am.auteur == "Mme X"
    # Date / statut du dossier = scrutin le plus récent (le vote texte).
    assert dossier.date_dernier_scrutin == "2026-07-10"
    # Sources : la page du dossier législatif uniquement — la source de chaque
    # vote vit sur sa propre fiche (pas de doublon sur la fiche dossier).
    assert [src.type.value for src in dossier.sources] == ["texte"]
    assert "/dossiers/" in dossier.sources[0].url


def test_build_dossier_enrichit_amendement_depuis_index():
    """Quand l'index des amendements est fourni, le vote d'amendement reçoit son
    contenu (dispositif, exposé sommaire, article visé) — lié par (dossierRef,
    numéro) + date."""
    from datetime import date

    from app.ingestion.amendements import AmendementEnrichi

    resolver = build_resolver_from_organes(ORGANES)
    amend = parse_scrutin(SCRUTIN, resolver)  # DLR5L17N53940, n° 80, 2026-07-02
    index = {
        ("DLR5L17N53940", "80"): [
            AmendementEnrichi(
                dispositif="Supprimer l'alinéa 2.",
                expose_sommaire="Cet amendement clarifie le texte.",
                cible="Article 2",
                date_sort=date(2026, 7, 2),
            )
        ]
    }

    dossier = build_dossier([amend], index)

    am = dossier.amendements[0]
    assert am.cible == "Article 2"
    assert am.dispositif == "Supprimer l'alinéa 2."
    assert am.expose_sommaire == "Cet amendement clarifie le texte."


def test_build_dossier_sans_index_laisse_contenu_vide():
    """Sans index (archive non téléchargée) : pas de contenu, mais l'amendement
    reste présent (§2.5 : rien n'est inventé)."""
    resolver = build_resolver_from_organes(ORGANES)
    amend = parse_scrutin(SCRUTIN, resolver)
    dossier = build_dossier([amend])
    am = dossier.amendements[0]
    assert am.dispositif is None
    assert am.expose_sommaire is None
    assert am.cible is None


def test_build_dossier_rattache_sous_amendements():
    """Un sous-amendement est rattaché à son amendement parent (« … à
    l'amendement n° X ») — il n'apparaît pas au premier niveau du dossier."""
    resolver = build_resolver_from_organes(ORGANES)
    parent = parse_scrutin(SCRUTIN, resolver)  # « l'amendement n° 80 de Mme X »
    sous = _scrutin_derive(resolver, "VT_SOUS", "2026-07-01", _OBJET_SOUS)

    dossier = build_dossier([sous, parent])

    assert len(dossier.amendements) == 1
    am = dossier.amendements[0]
    assert am.id == parent.scrutin.id
    assert [sa.id for sa in am.sous_amendements] == ["VT_SOUS"]
    sa = am.sous_amendements[0]
    assert sa.numero == "5"
    assert sa.scrutin_id == "VT_SOUS"  # cliquable vers son propre vote


def test_sous_amendement_sans_parent_reste_au_niveau_dossier():
    """Parent non identifiable → le sous-amendement reste listé (rien de déduit)."""
    resolver = build_resolver_from_organes(ORGANES)
    sous = _scrutin_derive(
        resolver, "VT_SOUS", "2026-07-01", "le sous-amendement n° 5 de M. Zed"
    )
    dossier = build_dossier([sous])
    assert [a.id for a in dossier.amendements] == ["VT_SOUS"]
    assert dossier.amendements[0].sous_amendements == []


def test_sources_dossier_repli_sur_votes_texte_sans_ref():
    """Sans page de dossier législatif, repli factuel sur les sources des
    votes sur le texte (jamais celles des amendements — déjà sur leur fiche)."""
    resolver = build_resolver_from_organes(ORGANES)
    texte = _vote_texte(resolver, "VT_TEXTE", "2026-07-10")
    texte.dossier_ref = None
    dossier = build_dossier([texte])
    assert [src.type.value for src in dossier.sources] == ["scrutin"]


def test_merge_purge_les_sources_par_vote_heritees():
    """Fusion : dès que la version fraîche porte la page du dossier
    législatif, les sources par-vote héritées (ancien format) sont purgées."""
    resolver = build_resolver_from_organes(ORGANES)
    prev = build_dossier([_vote_texte(resolver, "VT1", "2026-07-02")])
    prev.sources.append(
        SourceOfficielle(
            type="scrutin", libelle="Scrutin", url="https://exemple/scrutins/1"
        )
    )
    incoming = build_dossier([_vote_texte(resolver, "VT1", "2026-07-02")])
    merged = _merge_avec_existant(prev, incoming)
    assert [src.type.value for src in merged.sources] == ["texte"]


def test_merge_deplace_un_vote_reclasse_hors_des_scrutins():
    """Garde-fou anti-doublon : un vote d'amendement resté (à tort) dans la
    liste des votes sur le texte — cas d'un payload ingéré sous une ancienne
    version — est retiré des `scrutins` dès que le build frais le classe
    amendement. Chaque id vit dans exactement une liste (pas de doublon)."""
    resolver = build_resolver_from_organes(ORGANES)
    amend = parse_scrutin(SCRUTIN, resolver)  # objet « l'amendement n° 80 »

    # Simule l'ancien format : l'amendement est présent DANS les votes texte
    # ET dans les amendements (exactement l'état corrompu observé en base).
    prev = build_dossier([amend])
    prev.scrutins = [ScrutinResume.from_scrutin(amend.scrutin)]
    assert prev.scrutins[0].id in {a.id for a in prev.amendements}  # doublon initial

    incoming = build_dossier([parse_scrutin(SCRUTIN, resolver)])
    merged = _merge_avec_existant(prev, incoming)

    assert amend.scrutin.id not in {s.id for s in merged.scrutins}  # plus dans texte
    assert amend.scrutin.id in {a.id for a in merged.amendements}   # bien en amendement
    assert merged.scrutins == []  # le seul vote du dossier était un amendement
    # Reclassification ≠ nouveau vote : pas de badge « mis à jour » abusif.
    assert merged.mise_a_jour is None


def test_resume_genere_est_ancre_et_non_comble():
    """Le résumé par gabarit est généré à l'ingestion : chaque phrase est
    ancrée sur un fait, et les champs non tirés des scrutins (contexte,
    public concerné…) restent signalés comme non documentés (§2.5)."""
    resolver = build_resolver_from_organes(ORGANES)
    dossier = build_dossier([_vote_texte(resolver, "VT1", "2026-07-02")])
    # Non vide, chaque phrase sourcée.
    assert dossier.resume.resume
    assert all(p.source_id for p in dossier.resume.resume)
    assert dossier.resume.confiance.value == "moyenne"
    # Le contexte éditorial (hors scrutins) n'est pas comblé.
    assert "contexte" in dossier.resume.champs_non_documentes


def test_mise_a_jour_quand_nouveau_vote():
    """Un nouveau vote rattaché à un dossier connu → badge « mis à jour » (§7.7)."""
    resolver = build_resolver_from_organes(ORGANES)
    prev = build_dossier([_vote_texte(resolver, "VT1", "2026-07-02", "l'article 1er")])
    incoming = build_dossier([_vote_texte(resolver, "VT2", "2026-07-05")])

    merged = _merge_avec_existant(prev, incoming)
    assert len(merged.scrutins) == 2
    assert merged.mise_a_jour is not None
    assert merged.mise_a_jour.date == "2026-07-05"
    assert merged.date_dernier_scrutin == "2026-07-05"


def test_mise_a_jour_pour_nouvel_amendement():
    """Un nouveau vote d'amendement déclenche aussi le badge « mis à jour »."""
    resolver = build_resolver_from_organes(ORGANES)
    prev = build_dossier([_vote_texte(resolver, "VT1", "2026-07-01")])
    incoming = build_dossier([parse_scrutin(SCRUTIN, resolver)])  # amendement

    merged = _merge_avec_existant(prev, incoming)
    assert len(merged.scrutins) == 1  # le vote texte connu
    assert len(merged.amendements) == 1  # le nouvel amendement
    assert merged.mise_a_jour is not None


def test_mise_a_jour_pour_nouveau_sous_amendement():
    """Un nouveau sous-amendement sur un amendement connu → badge « mis à jour »,
    et il rejoint son parent dans le dossier fusionné."""
    resolver = build_resolver_from_organes(ORGANES)
    parent = parse_scrutin(SCRUTIN, resolver)
    prev = build_dossier([parent])
    sous = _scrutin_derive(resolver, "VT_SOUS", "2026-07-03", _OBJET_SOUS)
    incoming = build_dossier([parse_scrutin(SCRUTIN, resolver), sous])

    merged = _merge_avec_existant(prev, incoming)
    assert len(merged.amendements) == 1  # toujours un seul amendement parent
    assert [sa.id for sa in merged.amendements[0].sous_amendements] == ["VT_SOUS"]
    assert merged.mise_a_jour is not None


def test_pas_de_mise_a_jour_si_vote_deja_connu():
    resolver = build_resolver_from_organes(ORGANES)
    prev = build_dossier([_vote_texte(resolver, "VT1", "2026-07-02")])
    incoming = build_dossier([_vote_texte(resolver, "VT1", "2026-07-02")])
    merged = _merge_avec_existant(prev, incoming)
    assert len(merged.scrutins) == 1
    assert merged.mise_a_jour is None


def test_coherence_ok_quand_sommes_correspondent():
    resolver = build_resolver_from_organes(ORGANES)
    s = parse_scrutin(SCRUTIN, resolver).scrutin
    # pour: 0+21=21, contre: 10+29=39, abst: 0+4=4 → cohérent avec le global.
    assert controles_coherence(s) == []


def test_coherence_signale_incoherence():
    resolver = build_resolver_from_organes(ORGANES)
    s = parse_scrutin(SCRUTIN, resolver).scrutin
    s.resultat.pour = 999  # casse la cohérence
    anomalies = controles_coherence(s)
    assert any("pour" in a for a in anomalies)


def test_map_statut():
    assert map_statut("adopté") == "adopte"
    assert map_statut("rejeté") == "rejete"


def test_map_position_absent_devient_non_votant():
    assert map_position("absent") == PositionVote.non_votant
    assert map_position("pour") == PositionVote.pour


def test_guess_theme():
    assert guess_theme("Accès aux soins et hôpitaux") == "Santé"
    assert guess_theme("Un sujet sans mot-clé identifiable") == "Autre"
    # Thèmes ajoutés (couverture des « Autre » réels).
    assert guess_theme("Sûreté dans les transports") == "Transports"
    assert guess_theme("Organisation du sport professionnel") == "Sport"
    assert guess_theme("Exercice de la démocratie agricole") == "Agriculture"
    assert guess_theme("Mode d'élection des conseils municipaux") == "Institutions"
    assert guess_theme("Nationalité française à Mayotte") == "Immigration"
    assert guess_theme("Droit à l'aide à mourir") == "Santé"
    # « sport » ⊂ « transport » : un texte transport ne bascule pas en Sport.
    assert guess_theme("Sûreté dans les transports en commun") == "Transports"


def test_guess_theme_procedural_vers_vie_parlementaire():
    # Motions de censure / déclarations de politique générale → thème dédié.
    assert (
        guess_theme("la motion de censure déposée en application de l'article 49")
        == "Vie parlementaire"
    )
    assert (
        guess_theme("la déclaration de politique générale du Gouvernement")
        == "Vie parlementaire"
    )
    # Une « motion de rejet préalable » sur un texte de fond n'est PAS procédurale.
    assert guess_theme("motion de rejet préalable au projet de loi de santé") == "Santé"


def test_titre_court_retire_nature_et_connecteur():
    # La nature est affichée en label à part : le titre ne la répète pas.
    assert (
        titre_court("Proposition de loi visant à améliorer la sécurité des trains")
        == "Améliorer la sécurité des trains"
    )
    assert (
        titre_court("Projet de loi relatif au statut de l'élu local")
        == "Statut de l'élu local"
    )
    # Article contracté collé au connecteur (« visant AU »).
    assert (
        titre_court("Proposition de loi visant au rétablissement du délit de fuite")
        == "Rétablissement du délit de fuite"
    )
    # L'article qui suit le connecteur part aussi (titre de presse).
    assert (
        titre_court("Proposition de loi visant à la nationalisation d'ArcelorMittal")
        == "Nationalisation d'ArcelorMittal"
    )


def test_titre_court_variantes_de_la_source():
    # Apostrophe courbe : `fold` ne la normalise pas, l'article part quand même.
    assert (
        titre_court("Proposition de résolution européenne relative à l’adoption du texte")
        == "Adoption du texte"
    )
    # Mention de navette insérée : déjà portée par la trajectoire du dossier.
    assert (
        titre_court("Proposition de loi, adoptée par le Sénat, relative à l'accès aux soins")
        == "Accès aux soins"
    )


def test_titre_court_garde_le_titre_quand_la_nature_fait_partie_du_nom():
    # Pas de connecteur de la liste fermée → on ne touche à rien (§2.5).
    for titre in (
        "Projet de loi de finances pour 2025",
        "Projet de loi de financement de la sécurité sociale pour 2026",
        "Proposition de loi d'abrogation de la retraite à 64 ans",
        "Proposition de résolution pour une stratégie nationale de prévention",
    ):
        assert titre_court(titre) == titre


def test_titre_court_capitalise_un_objet_cite_en_minuscule():
    assert (
        titre_court("la motion de censure déposée en application de l'article 49")
        == "Motion de censure déposée en application de l'article 49"
    )


def test_titre_court_ne_tronque_pas():
    # L'app clampe sur 2 lignes ; on ne coupe plus en plein mot comme avant.
    long = "Proposition de loi visant à " + "réformer le droit de la copropriété " * 4
    assert titre_court(long).endswith("copropriété")
    assert "…" not in titre_court(long)
    # Un titre déjà tronqué par la source garde ses points de suspension.
    assert titre_court("Projet de loi portant diverses mesures d'urg…").endswith("…")


def test_truncate_mots_coupe_sur_un_mot_entier():
    assert truncate_mots("un texte court", 40) == "un texte court"
    assert truncate_mots("abcdef ghijkl mnopqr stuvwx", 20) == "abcdef ghijkl…"
    # Mot à rallonge : on coupe net plutôt que de sacrifier la phrase.
    assert truncate_mots("a " + "z" * 40, 20).endswith("…")


def test_build_dossier_pose_le_titre_court():
    """Le pipeline produit directement le titre d'affichage (plus de troncature
    à 90 caractères en plein mot), et laisse l'accroche vide : elle est posée
    après la génération des questions."""
    import copy

    brut = copy.deepcopy(SCRUTIN)
    brut["scrutin"]["objet"]["dossierLegislatif"]["libelle"] = (
        "Proposition de loi visant à la nationalisation d'ArcelorMittal France"
    )
    resolver = build_resolver_from_organes(ORGANES)
    dossier = build_dossier([parse_scrutin(brut, resolver)])

    assert dossier.titre_clair == "Nationalisation d'ArcelorMittal France"
    assert dossier.titre_officiel.startswith("Proposition de loi")
    assert dossier.accroche is None


def test_les_rapports_survivent_a_un_run_sans_archive():
    """Un rapport déposé ne bouge plus, et son URL a été vérifiée une fois : un
    run qui n'a pas pu lire l'archive ne doit pas le faire disparaître de la
    liste des documents (§7.5), pas plus qu'il n'efface l'état ou l'initiative.
    """
    from app.schemas import SourceOfficielle

    resolver = build_resolver_from_organes(ORGANES)
    prev = build_dossier([_vote_texte(resolver, "VT1", "2026-07-02")])
    prev.rapports_commission = [
        SourceOfficielle(
            type="texte",
            libelle="Rapport de la commission (n° 912)",
            url="https://www.assemblee-nationale.fr/dyn/docs/RAPPANR5L17B0912",
        )
    ]
    incoming = build_dossier([_vote_texte(resolver, "VT2", "2026-07-05")])

    merged = _merge_avec_existant(prev, incoming)
    assert [s.libelle for s in merged.rapports_commission] == [
        "Rapport de la commission (n° 912)"
    ]


def test_le_repli_sur_les_scrutins_n_accumule_pas_les_documents_composes():
    """Un dossier sans page officielle (« TXT-… ») fusionne ses sources avec
    l'existant pour ne pas perdre celles des runs passés. ⚠️ L'union se restreint
    aux sources de scrutins : reprendre une entrée composée d'un run précédent la
    ferait survivre à la disparition de son document, alors que `sources` est
    précisément recomposée à chaque écriture.
    """
    from app.schemas import SourceOfficielle

    resolver = build_resolver_from_organes(ORGANES)
    prev = build_dossier([_vote_texte(resolver, "VT1", "2026-07-02")])
    prev.sources = [
        SourceOfficielle(type="scrutin", libelle="Scrutin", url="https://an.fr/s/1"),
        SourceOfficielle(
            type="texte",
            libelle="Compte rendu de la séance (Assemblée nationale)",
            url="https://an.fr/cr/1",
        ),
    ]
    incoming = build_dossier([_vote_texte(resolver, "VT2", "2026-07-05")])
    incoming.sources = [
        SourceOfficielle(type="scrutin", libelle="Scrutin", url="https://an.fr/s/2")
    ]

    merged = _merge_avec_existant(prev, incoming)
    assert [s.url for s in merged.sources] == ["https://an.fr/s/2", "https://an.fr/s/1"]


# --- Forme du scrutin : « 42 voix contre 0, pourquoi seulement 42 ? » --------


def test_parse_scrutin_lit_la_forme_du_scrutin():
    """`typeVote` et `nbrSuffragesRequis` sont dans l'archive depuis toujours ;
    ils expliquent le nombre de votants, que rien n'expliquait jusqu'ici."""
    import copy

    from app.domain.enums import TypeVote

    resolver = build_resolver_from_organes(ORGANES)
    brut = copy.deepcopy(SCRUTIN)
    brut["scrutin"]["typeVote"] = {"codeTypeVote": "SPS"}
    brut["scrutin"]["syntheseVote"]["nbrSuffragesRequis"] = "33"

    s = parse_scrutin(brut, resolver).scrutin
    assert s.type_vote is TypeVote.solennel
    assert s.suffrages_requis == 33
    # Le résumé embarqué dans la fiche dossier la porte aussi : c'est lui qui
    # alimente le vote décisif et les cartes du fil.
    from app.schemas import ScrutinResume

    assert ScrutinResume.from_scrutin(s).type_vote is TypeVote.solennel


def test_un_code_de_scrutin_inconnu_ne_produit_pas_de_forme():
    """Table fermée : un code nouveau ne se devine pas (§2.5). Le Sénat, dont la
    page ne nomme pas le type, tombe dans le même cas."""
    import copy

    resolver = build_resolver_from_organes(ORGANES)
    for code in (None, "", "XXX"):
        brut = copy.deepcopy(SCRUTIN)
        brut["scrutin"]["typeVote"] = {"codeTypeVote": code}
        assert parse_scrutin(brut, resolver).scrutin.type_vote is None


def test_la_forme_du_scrutin_remonte_jusqu_a_la_carte_du_fil():
    """Sans elle, une motion de censure se lirait « 267 pour, 0 contre » jusque
    dans le fil, alors que ses opposants ne sont pas recensés (art. 49)."""
    import copy

    from app.domain.enums import TypeVote
    from app.schemas import DossierListItem

    resolver = build_resolver_from_organes(ORGANES)
    brut = copy.deepcopy(SCRUTIN)
    # `titre` prime sur `objet.libelle` dans le parseur : les deux sont posés.
    motion = "la motion de censure déposée en application de l'article 49"
    brut["scrutin"]["titre"] = motion
    brut["scrutin"]["objet"]["libelle"] = motion
    brut["scrutin"]["typeVote"] = {"codeTypeVote": "MOC"}
    brut["scrutin"]["syntheseVote"]["nbrSuffragesRequis"] = "289"

    dossier = build_dossier([parse_scrutin(brut, resolver)])
    item = DossierListItem.from_dossier(dossier)
    assert item.type_vote_dernier_scrutin is TypeVote.motion_censure
    assert item.suffrages_requis_dernier_scrutin == 289


# --- Motions : dire l'inversion de sens (§7.4) -------------------------------


def test_type_motion_classe_les_formes_qui_inversent_le_sens():
    """Une motion inverse la lecture de son résultat : l'adopter rejette,
    suspend ou reporte le texte. Le classement est la condition pour le dire."""
    from app.domain.enums import TypeMotion
    from app.ingestion.normalize import type_motion

    assert (
        type_motion("la motion de rejet préalable, déposée par Mme Panot, du projet")
        is TypeMotion.rejet_prealable
    )
    assert (
        type_motion(
            "la motion n° 278, présentée par Mme Cukierman et les membres du "
            "groupe CRCE, tendant à opposer la question préalable au projet de loi"
        )
        is TypeMotion.question_prealable
    )
    assert (
        type_motion(
            "la motion n° 13, présentée par Mme Vogel, tendant à opposer "
            "l'exception d'irrecevabilité au projet de loi constitutionnelle"
        )
        is TypeMotion.exception_irrecevabilite
    )
    assert (
        type_motion("la motion n° 6, tendant au renvoi en commission de la PPL")
        is TypeMotion.renvoi_en_commission
    )
    # Coquille relevée telle quelle dans la source (« rejet péalable ») : la
    # graphie ne peut désigner que la motion de rejet préalable.
    assert (
        type_motion("la motion de rejet péalable, déposée par M. Hetzel, de la PPL")
        is TypeMotion.rejet_prealable
    )
    assert type_motion("la motion référendaire présentée par M. W") is (
        TypeMotion.referendaire
    )
    # L'apostrophe courbe est courante dans l'open data comme sur senat.fr.
    assert type_motion("la motion d’ajournement présentée par M. Z") is (
        TypeMotion.ajournement
    )


def test_type_motion_ecarte_la_censure_et_les_amendements():
    """Une motion de CENSURE ne rejette pas un texte : elle renverse un
    gouvernement, et elle a son propre traitement (`TypeVote.motion_censure`).
    Un amendement n'est jamais une motion, même si son objet en cite une."""
    from app.ingestion.normalize import type_motion

    assert type_motion("la motion de censure déposée en application de l'art. 49") is None
    assert (
        type_motion("l'amendement n° 12 de M. X tendant à opposer la question préalable")
        is None
    )
    assert type_motion("l'ensemble du projet de loi de finances pour 2026") is None


def test_la_motion_du_senat_est_classee_avant_la_troncature():
    """⚠️ Le nœud du Sénat. L'objet stocké est tronqué à 120 caractères, et la
    clause qui dit ce qu'est la motion arrive au-delà : classer après troncature
    ne verrait jamais rien, et ces votes resteraient sans nom à l'écran."""
    from app.domain.enums import TypeMotion
    from app.ingestion.normalize import truncate, type_motion

    objet = (
        "la motion n° 278, présentée par Mme Cécile Cukierman et les membres du "
        "groupe Communiste Républicain Citoyen et Écologiste - Kanaky, tendant à "
        "opposer la question préalable au projet de loi de finances"
    )
    assert type_motion(objet) is TypeMotion.question_prealable
    # La preuve par l'absurde : sur l'objet tronqué, plus rien n'est reconnaissable.
    assert type_motion(truncate(objet, 120)) is None


def test_la_motion_remonte_du_scrutin_jusqu_a_la_carte_du_fil():
    """8 dossiers annonçaient « Adopté » sur un texte que la motion venait de
    rejeter — dont un dont c'était le seul vote. Le drapeau doit voyager du
    scrutin au dossier ET à sa carte, sinon le fil garde le contresens."""
    import copy

    from app.domain.enums import TypeMotion
    from app.schemas import DossierListItem

    resolver = build_resolver_from_organes(ORGANES)
    brut = copy.deepcopy(SCRUTIN)
    motion = (
        "la motion de rejet préalable, déposée par Mme Panot, du projet de loi "
        "d'approbation des comptes de la sécurité sociale"
    )
    brut["scrutin"]["titre"] = motion
    brut["scrutin"]["objet"]["libelle"] = motion
    brut["scrutin"]["sort"] = {"code": "adopté"}

    parse = parse_scrutin(brut, resolver)
    assert parse.scrutin.type_motion is TypeMotion.rejet_prealable

    dossier = build_dossier([parse])
    # Le vote qui a fixé `statut` est la motion : le badge doit la nommer.
    assert dossier.statut.value == "adopte"
    assert dossier.statut_motion is TypeMotion.rejet_prealable
    assert dossier.scrutins[0].type_motion is TypeMotion.rejet_prealable

    item = DossierListItem.from_dossier(dossier)
    assert item.statut_motion is TypeMotion.rejet_prealable
    assert item.type_motion_dernier_scrutin is TypeMotion.rejet_prealable
