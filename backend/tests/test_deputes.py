"""Tests de la fonctionnalité « Députés » (§5.2).

Deux niveaux : les fonctions **pures** d'ingestion (aucun réseau, aucune base)
et les routes servies depuis le seed (backend « memory », cf. conftest).
"""
from __future__ import annotations

import pytest

from app.domain.enums import PositionVote
from app.ingestion import deputes as deputes_module
from app.ingestion.deputes import (
    attacher_portraits,
    build_deputes_from_amo,
    circonscription,
    url_portrait,
    votes_du_scrutin,
)
from app.ingestion.organes import build_resolver_from_organes
from app.schemas import Depute

ORGANES = [
    {
        "organe": {
            "uid": "PO845401",
            "codeType": "GP",
            "libelle": "Rassemblement National",
            "libelleAbrev": "RN",
            "viMoDe": {"dateFin": None},
        }
    },
    {
        "organe": {
            "uid": "PO845413",
            "codeType": "GP",
            "libelle": "La France insoumise - NFP",
            "libelleAbrev": "LFI-NFP",
            "viMoDe": {"dateFin": None},
        }
    },
]

RESOLVER = build_resolver_from_organes(ORGANES)

# Wrapper acteur minimal, au format réel de l'archive AMO : `uid` sérialisé en
# objet, `mandats.mandat` en liste.
ACTEUR = {
    "acteur": {
        "uid": {"#text": "PA841605"},
        "etatCivil": {"ident": {"civ": "Mme", "prenom": "Jeanne", "nom": "Martin"}},
        "mandats": {
            "mandat": [
                {
                    "typeOrgane": "ASSEMBLEE",
                    "dateDebut": "2024-07-18",
                    "dateFin": None,
                    "organes": {"organeRef": "PO717460"},
                    "election": {
                        "lieu": {
                            "region": "Hauts-de-France",
                            "departement": "Pas-de-Calais",
                            "numCirco": "5",
                        }
                    },
                },
                {
                    "typeOrgane": "GP",
                    "dateDebut": "2024-07-19",
                    "dateFin": None,
                    "organes": {"organeRef": "PO845401"},
                },
                {
                    "typeOrgane": "COMPER",
                    "dateDebut": "2024-07-20",
                    "organes": {"organeRef": "PO111111"},
                },
            ]
        },
    }
}

# Ancien député : mandat ASSEMBLEE terminé → hors annuaire.
ACTEUR_ANCIEN = {
    "acteur": {
        "uid": {"#text": "PA000001"},
        "etatCivil": {"ident": {"prenom": "Paul", "nom": "Durand"}},
        "mandats": {
            "mandat": {
                "typeOrgane": "ASSEMBLEE",
                "dateDebut": "2022-06-22",
                "dateFin": "2024-06-09",
                "organes": {"organeRef": "PO717460"},
            }
        },
    }
}

# Mandat unique (objet, pas liste) et lieu d'élection absent.
ACTEUR_SANS_LIEU = {
    "acteur": {
        "uid": {"#text": "PA000002"},
        "etatCivil": {"ident": {"prenom": "Luc", "nom": "Bernard"}},
        "mandats": {
            "mandat": {
                "typeOrgane": "ASSEMBLEE",
                "dateDebut": "2024-07-18",
                "organes": {"organeRef": "PO717460"},
            }
        },
    }
}

SCRUTIN = {
    "scrutin": {
        "uid": "VTANR5L17V999",
        "dateScrutin": "2026-07-02",
        "ventilationVotes": {
            "organe": {
                "groupes": {
                    "groupe": [
                        {
                            "organeRef": "PO845401",
                            "vote": {
                                "positionMajoritaire": "pour",
                                "decompteNominatif": {
                                    "pours": {
                                        "votant": [
                                            {"acteurRef": "PA841605"},
                                            {"acteurRef": "PA841606"},
                                        ]
                                    },
                                    # Vote divergent de la majorité du groupe.
                                    "contres": {"votant": {"acteurRef": "PA841607"}},
                                    "nonVotants": {"votant": {"acteurRef": "PA841608"}},
                                },
                            },
                        },
                        {
                            "organeRef": "PO845413",
                            "vote": {
                                # Groupe sans position majoritaire exploitable :
                                # aucune divergence n'est qualifiée (§2.5).
                                "positionMajoritaire": "nonVotant",
                                "decompteNominatif": {
                                    "abstentions": {"votant": {"acteurRef": "PA900001"}}
                                },
                            },
                        },
                    ]
                }
            }
        },
    }
}


# --- Fonctions pures d'ingestion ------------------------------------------


def test_circonscription_formatee():
    assert circonscription(
        {"election": {"lieu": {"departement": "Pas-de-Calais", "numCirco": "5"}}}
    ) == "Pas-de-Calais, 5ᵉ circ."
    assert circonscription(
        {"election": {"lieu": {"departement": "Cantal", "numCirco": "1"}}}
    ) == "Cantal, 1re circ."


def test_circonscription_absente_non_devinee():
    # Donnée manquante → chaîne vide, jamais une circonscription supposée (§2.5).
    assert circonscription(None) == ""
    assert circonscription({"election": {"lieu": {}}}) == ""


def test_url_portrait_derivee_de_l_acteur_ref():
    # Le référentiel AMO ne porte pas la photo : l'URL se dérive du numéro
    # d'acteur (préfixe « PA » retiré) et de la législature.
    assert url_portrait("PA841605", 17) == (
        "https://www.assemblee-nationale.fr/dyn/static/tribun/17/photos/carre/841605.jpg"
    )


async def test_portrait_attache_seulement_si_verifie(monkeypatch):
    """Une URL devinée n'atteint l'app qu'après avoir répondu une image (§2.5)."""
    connus = {"PA1"}

    class _Reponse:
        def __init__(self, ok: bool) -> None:
            self.status_code = 200 if ok else 404
            self.headers = {"content-type": "image/jpeg" if ok else "text/html"}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def head(self, url, **_):
            return _Reponse(any(f"/{ref[2:]}." in url for ref in connus))

    monkeypatch.setattr(deputes_module.httpx, "AsyncClient", lambda **_: _Client())

    avec = Depute(
        id="PA1", nom="A", groupe_id="PO1", groupe_nom="G", groupe_couleur="#000",
        circonscription="",
    )
    sans = Depute(
        id="PA2", nom="B", groupe_id="PO1", groupe_nom="G", groupe_couleur="#000",
        circonscription="",
    )
    assert await attacher_portraits([avec, sans], 17) == 1
    assert avec.portrait_url and avec.portrait_url.endswith("/1.jpg")
    # Photo introuvable → pas d'URL : l'app affiche les initiales, jamais une
    # image cassée.
    assert sans.portrait_url is None


def test_build_depute_depuis_wrapper_acteur():
    deputes = build_deputes_from_amo([ACTEUR], RESOLVER)
    assert len(deputes) == 1
    d = deputes[0]
    assert d.id == "PA841605"  # uid sérialisé en objet
    assert d.nom == "Jeanne Martin"
    assert d.groupe_id == "PO845401"
    assert d.groupe_nom == "Rassemblement National"
    assert d.groupe_couleur.startswith("#")
    assert d.circonscription == "Pas-de-Calais, 5ᵉ circ."
    assert d.depuis == "2024-07-19"  # début du mandat de groupe
    # L'open data ne fournit pas de photo : on n'en invente pas (§2.5).
    assert d.portrait_url is None


def test_build_deputes_exclut_les_mandats_termines():
    deputes = build_deputes_from_amo([ACTEUR, ACTEUR_ANCIEN], RESOLVER)
    assert [d.id for d in deputes] == ["PA841605"]


def test_build_deputes_mandat_unique_et_lieu_absent():
    deputes = build_deputes_from_amo([ACTEUR_SANS_LIEU], RESOLVER)
    assert len(deputes) == 1
    assert deputes[0].circonscription == ""
    assert deputes[0].depuis is None  # aucun mandat de groupe documenté


def test_votes_du_scrutin():
    votes = {v.acteur_ref: v for v in votes_du_scrutin(SCRUTIN)}
    assert set(votes) == {"PA841605", "PA841606", "PA841607", "PA841608", "PA900001"}
    assert votes["PA841605"].position is PositionVote.pour
    assert votes["PA841605"].contre_son_groupe is False


def test_vote_contre_son_groupe():
    votes = {v.acteur_ref: v for v in votes_du_scrutin(SCRUTIN)}
    divergent = votes["PA841607"]
    assert divergent.position is PositionVote.contre
    assert divergent.contre_son_groupe is True


def test_non_votant_sans_qualification():
    votes = {v.acteur_ref: v for v in votes_du_scrutin(SCRUTIN)}
    absent = votes["PA841608"]
    assert absent.position is PositionVote.non_votant
    # Une non-participation ne peut pas être « contre son groupe » (§2.5).
    assert absent.contre_son_groupe is None


def test_groupe_sans_position_majoritaire():
    votes = {v.acteur_ref: v for v in votes_du_scrutin(SCRUTIN)}
    assert votes["PA900001"].position is PositionVote.abstention
    assert votes["PA900001"].contre_son_groupe is None


def test_scrutin_sans_ventilation():
    assert votes_du_scrutin({"scrutin": {"uid": "X"}}) == []


# --- Routes ----------------------------------------------------------------


def test_annuaire_camel_case(client):
    r = client.get("/deputes")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 2
    assert "groupeNom" in items[0] and "groupeCouleur" in items[0]
    # La photo voyage AVEC l'annuaire : la liste doit être identifiable d'un
    # coup d'œil, sans charger chaque fiche (clé présente même à null).
    assert "portraitUrl" in items[0]
    # Ordre alphabétique.
    assert [i["nom"] for i in items] == sorted(i["nom"] for i in items)


def test_annuaire_filtre_par_groupe(client):
    r = client.get("/deputes", params={"groupe": "RN"})
    assert r.status_code == 200
    items = r.json()
    assert items and all(i["groupeNom"] == "Rass. National" for i in items)


def test_annuaire_recherche(client):
    tous = client.get("/deputes").json()
    cible = tous[0]
    r = client.get("/deputes", params={"q": cible["nom"].split()[-1].lower()})
    assert r.status_code == 200
    assert any(i["id"] == cible["id"] for i in r.json())


def test_fiche_depute(client):
    r = client.get("/deputes/dep-seed-01")
    assert r.status_code == 200
    body = r.json()
    assert body["nom"]
    assert body["circonscription"]
    portrait = body["portrait"]
    assert portrait["votes"] == portrait["pour"] + portrait["contre"] + portrait["abstention"]
    assert 0 <= portrait["cohesionGroupe"] <= 1
    # Pas de taux de participation : un ratio de présence se lirait comme un
    # score d'absentéisme que la source ne soutient pas (§7.4).
    assert "participation" not in portrait
    historique = body["historique"]
    assert historique
    assert [v["date"] for v in historique] == sorted(
        (v["date"] for v in historique), reverse=True
    )
    assert historique[0]["objetType"] in {"dossier", "amendement", "sous_amendement"}


def test_fiche_depute_signale_le_vote_contre_son_groupe(client):
    historique = client.get("/deputes/dep-seed-01").json()["historique"]
    assert any(v.get("contreSonGroupe") is True for v in historique)
    # Le fait n'est posé que quand il est établi : jamais de True par défaut.
    assert any(v.get("contreSonGroupe") is False for v in historique)


def test_fiche_depute_titre_du_dossier_pour_un_vote_sur_le_texte(client):
    historique = client.get("/deputes/dep-seed-01").json()["historique"]
    sur_texte = [v for v in historique if v["objetType"] == "dossier"]
    assert sur_texte and all(v["titre"] and v.get("dossierId") for v in sur_texte)


def test_statistiques_non_comblees_quand_la_donnee_manque(client):
    # Député sans vote enregistré : la cohésion n'est PAS calculable → absente
    # (« information non disponible »), jamais 0 par défaut (§2.5).
    body = client.get("/deputes/dep-seed-06").json()
    assert body["portrait"]["votes"] == 0
    assert body["portrait"].get("cohesionGroupe") is None
    assert body["historique"] == []
    # Champs non documentés par la source : absents, pas devinés.
    assert body["circonscription"] == ""
    assert body.get("depuis") is None
    assert body.get("portraitUrl") is None


def test_fiche_depute_inconnu(client):
    assert client.get("/deputes/inconnu").status_code == 404


def test_pagination_historique(client):
    complet = client.get("/deputes/dep-seed-01/votes", params={"limit": 100}).json()
    assert len(complet) > 2
    page1 = client.get("/deputes/dep-seed-01/votes", params={"limit": 2}).json()
    page2 = client.get(
        "/deputes/dep-seed-01/votes", params={"limit": 2, "offset": 2}
    ).json()
    assert [v["scrutinId"] for v in page1] == [v["scrutinId"] for v in complet[:2]]
    assert [v["scrutinId"] for v in page2] == [v["scrutinId"] for v in complet[2:4]]
    # Une page plus courte que la limite signale la fin de l'historique.
    fin = client.get(
        "/deputes/dep-seed-01/votes", params={"limit": 100, "offset": len(complet)}
    ).json()
    assert fin == []


def test_liste_groupes(client):
    r = client.get("/groupes")
    assert r.status_code == 200
    groupes = r.json()
    assert groupes
    assert {"id", "nom", "abrev", "couleur"} <= set(groupes[0])
    assert [g["nom"] for g in groupes] == sorted(g["nom"] for g in groupes)
