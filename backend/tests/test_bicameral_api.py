"""Contrat d'API du bicaméralisme, bout en bout (sur le seed).

Ce que ces tests protègent : **un texte, un dossier**, même quand les deux
chambres l'ont voté ; et le fait que rien à l'écran ne puisse laisser croire
qu'un vote sénatorial est un vote de l'Assemblée (§2.5).
"""
from __future__ import annotations

# Dossier du seed voté à l'Assemblée PUIS au Sénat.
DOSSIER_MIXTE = "dos-energie-2026"
SCRUTIN_SENAT = "SEN-2026-118"
SENATEUR = "sen-seed-01"


def test_un_texte_vote_dans_les_deux_chambres_reste_un_seul_dossier(client):
    dossier = client.get(f"/dossiers/{DOSSIER_MIXTE}").json()
    chambres = [s["chambre"] for s in dossier["scrutins"]]
    assert set(chambres) == {"assemblee", "senat"}
    # Les votes restent dans la liste du dossier, du plus récent au plus ancien.
    assert chambres[0] == "senat"


def test_chaque_vote_porte_sa_chambre(client):
    scrutin = client.get(f"/scrutins/{SCRUTIN_SENAT}").json()
    assert scrutin["chambre"] == "senat"
    assert scrutin["dossierId"] == DOSSIER_MIXTE
    # Un vote de l'Assemblée reste explicitement « assemblee », jamais implicite.
    autre = client.get("/scrutins/scr-2026-0410").json()
    assert autre["chambre"] == "assemblee"


def test_aucune_cohesion_sur_un_vote_du_senat(client):
    """La délégation de vote par groupe vide la cohésion de son sens (§7.4)."""
    scrutin = client.get(f"/scrutins/{SCRUTIN_SENAT}").json()
    assert scrutin["positionsGroupes"]
    assert all(g["cohesion"] is None for g in scrutin["positionsGroupes"])


def test_trajectoire_bicamerale_servie_par_l_api(client):
    """La frise vient du backend : l'app ne peut pas la déduire des scrutins,
    qui ne documentent que ce que chaque chambre a voté."""
    dossier = client.get(f"/dossiers/{DOSSIER_MIXTE}").json()
    trajectoire = dossier["trajectoire"]
    assert [p["chambre"] for p in trajectoire] == ["assemblee", "senat", None]
    # Une étape peut être documentée sans être conclue (§2.5).
    assert trajectoire[-1]["statut"] is None
    assert trajectoire[-1]["date"]


def test_le_fil_dit_de_quelle_chambre_vient_le_vote(client):
    """Sans `chambres`, une carte du fil se lirait comme un vote de l'Assemblée."""
    accueil = client.get("/accueil").json()
    cartes = [
        c
        for section in accueil["sections"]
        for c in section["dossiers"]
        if c["id"] == DOSSIER_MIXTE
    ]
    assert cartes, "le dossier mixte devrait être dans une rangée de l'accueil"
    assert cartes[0]["chambres"] == ["assemblee", "senat"]


def test_annuaire_filtrable_par_chambre(client):
    tous = client.get("/deputes").json()
    senateurs = client.get("/deputes", params={"chambre": "senat"}).json()
    deputes = client.get("/deputes", params={"chambre": "assemblee"}).json()

    assert senateurs and deputes
    assert {p["chambre"] for p in senateurs} == {"senat"}
    assert {p["chambre"] for p in deputes} == {"assemblee"}
    assert len(senateurs) + len(deputes) == len(tous)


def test_fiche_senateur_sans_cohesion_ni_dissidence(client):
    """Le portrait d'un sénateur ne porte NI cohésion NI « contre son groupe » :
    ce sont des faits que la source ne soutient pas (§7.4)."""
    senateur = client.get(f"/deputes/{SENATEUR}").json()
    assert senateur["chambre"] == "senat"
    assert senateur["portrait"]["cohesionGroupe"] is None
    # Il a bien voté : l'absence de cohésion n'est pas un manque de données.
    assert senateur["portrait"]["votes"] >= 1
    assert senateur["historique"]
    assert all(v["contreSonGroupe"] is None for v in senateur["historique"])


def test_un_depute_garde_son_fait_contre_son_groupe(client):
    """Contrôle miroir : la règle du Sénat ne doit pas déteindre sur l'Assemblée.

    « Contre son groupe » reste un fait déduit, et déduit, côté Assemblée.
    """
    historique = client.get("/deputes/dep-seed-01/votes", params={"limit": 100}).json()
    assert any(v["contreSonGroupe"] is True for v in historique)
