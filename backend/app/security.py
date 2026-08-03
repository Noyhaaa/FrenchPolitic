"""Mot de passe et jeton de session.

Deux fonctions de hachage (bcrypt) et deux de jeton (JWT HS256) — rien de plus.
L'API n'a qu'un usage d'authentification : reconnaître le porteur d'un compte
sur les quatre routes de `app/api/routes/comptes.py`. Tout le reste du produit
est public et le reste (le compte est facultatif).

Le secret vient de `JWT_SECRET`. S'il manque :
  - en dev, un secret **éphémère** est tiré au démarrage — les jetons émis
    cessent d'être valides au redémarrage suivant, ce qui est visible tout de
    suite et n'a aucune conséquence en local ;
  - ailleurs, l'application refuse de démarrer plutôt que de signer avec une
    valeur devinable.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

logger = logging.getLogger(__name__)

_ALGORITHME = "HS256"

# Secret de repli tiré une fois par processus (dev uniquement, cf. docstring).
_secret_ephemere: str | None = None


class JetonInvalide(Exception):
    """Jeton absent, malformé, expiré ou signé avec un autre secret."""


def _secret() -> str:
    global _secret_ephemere
    if settings.jwt_secret:
        return settings.jwt_secret
    if settings.app_env != "dev":
        raise RuntimeError(
            "JWT_SECRET est obligatoire hors développement : sans lui, les "
            "jetons de session seraient signés avec une valeur devinable."
        )
    if _secret_ephemere is None:
        _secret_ephemere = secrets.token_urlsafe(48)
        logger.warning(
            "JWT_SECRET absent : secret éphémère tiré pour ce processus. "
            "Les sessions ne survivront pas à un redémarrage."
        )
    return _secret_ephemere


# ── Mot de passe ─────────────────────────────────────────────────────────────


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    """Empreinte bcrypt (sel inclus), telle qu'elle est stockée en base."""
    # bcrypt ne lit que les 72 premiers octets ; on tronque explicitement pour
    # que la vérification porte sur exactement ce qui a été haché.
    brut = mot_de_passe.encode("utf-8")[:72]
    return bcrypt.hashpw(brut, bcrypt.gensalt()).decode("utf-8")


def verifier_mot_de_passe(mot_de_passe: str, empreinte: str) -> bool:
    brut = mot_de_passe.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(brut, empreinte.encode("utf-8"))
    except ValueError:
        # Empreinte illisible (donnée corrompue) : on refuse, sans distinguer
        # ce cas d'un mot de passe faux côté appelant.
        return False


# ── Jeton de session ─────────────────────────────────────────────────────────


def creer_jeton(utilisateur_id: str) -> str:
    """Jeton signé portant l'identifiant du compte et sa date d'expiration."""
    maintenant = datetime.now(timezone.utc)
    charge = {
        "sub": utilisateur_id,
        "iat": maintenant,
        "exp": maintenant + timedelta(hours=settings.jwt_ttl_heures),
    }
    return jwt.encode(charge, _secret(), algorithm=_ALGORITHME)


def lire_jeton(jeton: str) -> str:
    """Renvoie l'identifiant du compte, ou lève `JetonInvalide`."""
    try:
        charge = jwt.decode(jeton, _secret(), algorithms=[_ALGORITHME])
    except jwt.PyJWTError as exc:  # expiré, signature fausse, malformé…
        raise JetonInvalide(str(exc)) from exc
    sujet = charge.get("sub")
    if not isinstance(sujet, str) or not sujet:
        raise JetonInvalide("jeton sans sujet")
    return sujet
