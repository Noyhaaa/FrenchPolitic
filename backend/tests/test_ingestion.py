"""Tests d'ingestion open data (parsing pur, sans réseau ni base)."""
from __future__ import annotations

from app.domain.enums import PositionVote, StatutScrutin
from app.ingestion.assemblee import parse_scrutin
from app.ingestion.normalize import (
    auteur_amendement,
    est_amendement,
    est_sous_amendement,
    guess_theme,
    map_position,
    map_statut,
    numero_amendement,
    numero_amendement_parent,
    texte_de_rattachement,
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
    assert rn.noms_contre == ["Jeanne Martin"]  # votant unique sérialisé en objet
    assert rn.noms_pour is None  # bloc absent → masqué, pas inventé (§2.5)
    # Acteur absent de l'annuaire → on garde sa référence (factuel).
    assert lfi.noms_pour == ["Paul Durand", "PA_INCONNU"]
    assert lfi.noms_abstention == ["Luc Bernard"]


def test_parse_sans_annuaire_pas_de_noms():
    resolver = build_resolver_from_organes(ORGANES)
    s = parse_scrutin(SCRUTIN, resolver).scrutin
    assert all(
        g.noms_pour is None and g.noms_contre is None for g in s.positions_groupes
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
    """Un vote autonome (motion de censure…) reste son propre dossier."""
    resolver = build_resolver_from_organes(ORGANES)
    p = parse_scrutin(
        _sans_dossier_ref("la motion de censure déposée par 185 députés"),
        resolver,
    )
    assert p.dossier_id == "VTANR5L17V999"  # l'uid du scrutin


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


def test_resume_vide_non_comble():
    """Sans génération IA, le résumé du dossier reste vide + confiance faible (§2.5)."""
    resolver = build_resolver_from_organes(ORGANES)
    dossier = build_dossier([_vote_texte(resolver, "VT1", "2026-07-02")])
    assert dossier.resume.resume == []
    assert dossier.resume.confiance.value == "faible"
    assert "resume" in dossier.resume.champs_non_documentes


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
