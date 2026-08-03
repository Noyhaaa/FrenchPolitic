"""Comptes utilisateurs — les seules routes d'écriture de l'API.

Tourne sur le repository mémoire, comme le reste de la suite (`conftest.py`
force `REPOSITORY_BACKEND=memory`) : chaque test part donc d'une base de
comptes vide.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

INSCRIPTION = {
    "prenom": "Alexandra",
    "nom": "Müller",
    "email": "alexandra@example.com",
    "motDePasse": "motdepasse1",
}


def _inscrire(client: TestClient, **surcharges) -> dict:
    reponse = client.post("/inscription", json={**INSCRIPTION, **surcharges})
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def test_inscription_ouvre_une_session(client: TestClient) -> None:
    corps = _inscrire(client)

    assert corps["jeton"]
    compte = corps["compte"]
    assert compte["email"] == "alexandra@example.com"
    assert compte["prenom"] == "Alexandra"
    assert compte["preferences"] == {
        "themes": [],
        "departement": None,
        "alertes": False,
    }
    # L'empreinte du mot de passe ne sort jamais de l'API.
    assert "motDePasse" not in compte and "motDePasseHash" not in compte


def test_inscription_conserve_les_preferences_du_parcours(client: TestClient) -> None:
    corps = _inscrire(
        client,
        preferences={
            "themes": ["Santé", "Logement", "Justice"],
            "departement": "Gironde",
            "alertes": True,
        },
    )
    assert corps["compte"]["preferences"]["themes"] == ["Santé", "Logement", "Justice"]
    assert corps["compte"]["preferences"]["departement"] == "Gironde"


def test_email_deja_pris_meme_avec_une_autre_casse(client: TestClient) -> None:
    _inscrire(client)

    reponse = client.post(
        "/inscription", json={**INSCRIPTION, "email": "Alexandra@Example.COM"}
    )
    assert reponse.status_code == 409


def test_mot_de_passe_trop_court_refuse(client: TestClient) -> None:
    reponse = client.post("/inscription", json={**INSCRIPTION, "motDePasse": "court"})
    assert reponse.status_code == 422


def test_adresse_malformee_refusee_a_l_inscription(client: TestClient) -> None:
    for adresse in ("sans-arobase", "deux@@arobases.fr", "pas.de@domaine", "a@b.f"):
        reponse = client.post("/inscription", json={**INSCRIPTION, "email": adresse})
        assert reponse.status_code == 422, adresse


def test_adresse_malformee_a_la_connexion_donne_401_pas_422(client: TestClient) -> None:
    """Une adresse malformée est un identifiant faux, pas une requête invalide.

    Elle doit recevoir exactement la réponse des autres échecs : sinon le code
    HTTP distingue déjà des catégories d'adresses (§ routes/comptes.py).
    """
    _inscrire(client)

    malformee = client.post(
        "/connexion", json={"email": "sans-arobase", "motDePasse": "motdepasse1"}
    )
    reference = client.post(
        "/connexion", json={"email": "inconnu@exemple.fr", "motDePasse": "motdepasse1"}
    )
    assert malformee.status_code == reference.status_code == 401
    assert malformee.json()["detail"] == reference.json()["detail"]


def test_connexion_puis_mauvais_mot_de_passe(client: TestClient) -> None:
    _inscrire(client)

    ok = client.post(
        "/connexion",
        json={"email": "ALEXANDRA@example.com", "motDePasse": "motdepasse1"},
    )
    assert ok.status_code == 200
    assert ok.json()["compte"]["nom"] == "Müller"

    faux = client.post(
        "/connexion",
        json={"email": "alexandra@example.com", "motDePasse": "autre-mot-de-passe"},
    )
    assert faux.status_code == 401

    # Une adresse inconnue reçoit exactement la même réponse : l'API ne dit pas
    # quelles adresses ont un compte.
    inconnue = client.post(
        "/connexion", json={"email": "personne@example.com", "motDePasse": "motdepasse1"}
    )
    assert inconnue.status_code == 401
    assert inconnue.json()["detail"] == faux.json()["detail"]


def test_moi_exige_un_jeton_valide(client: TestClient) -> None:
    jeton = _inscrire(client)["jeton"]

    assert client.get("/moi").status_code == 401
    assert (
        client.get("/moi", headers={"Authorization": "Bearer pas-un-jeton"}).status_code
        == 401
    )

    ok = client.get("/moi", headers={"Authorization": f"Bearer {jeton}"})
    assert ok.status_code == 200
    assert ok.json()["email"] == "alexandra@example.com"


def test_aller_retour_des_preferences(client: TestClient) -> None:
    jeton = _inscrire(client)["jeton"]
    entetes = {"Authorization": f"Bearer {jeton}"}

    ecriture = client.put(
        "/moi/preferences",
        headers=entetes,
        json={"themes": ["Santé", "Transports"], "departement": "Nord", "alertes": True},
    )
    assert ecriture.status_code == 200
    assert ecriture.json()["preferences"]["themes"] == ["Santé", "Transports"]

    relecture = client.get("/moi", headers=entetes)
    assert relecture.json()["preferences"] == {
        "themes": ["Santé", "Transports"],
        "departement": "Nord",
        "alertes": True,
    }


def test_preferences_sans_jeton_refusees(client: TestClient) -> None:
    reponse = client.put("/moi/preferences", json={"themes": [], "alertes": False})
    assert reponse.status_code == 401


def test_le_reste_de_l_api_reste_public(client: TestClient) -> None:
    """Le compte est facultatif : aucune route de lecture ne l'exige (§2.2)."""
    for chemin in ("/accueil", "/dossiers", "/deputes", "/themes"):
        assert client.get(chemin).status_code == 200, chemin
