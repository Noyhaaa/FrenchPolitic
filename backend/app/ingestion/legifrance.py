"""Client API Légifrance via PISTE (§5.1).

Fournit le texte consolidé des lois, le JO et les dossiers. Accès REST avec
OAuth2 (client credentials), gratuit après inscription PISTE.

⚠️ Données non opposables : seuls les PDF signés du JO font foi (§5.2) — à
rappeler dans les mentions légales de l'app.

Stub : flux OAuth et endpoints à brancher en Phase 1 (identifiants dans .env).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass
class TexteConsolide:
    dossier_ref: str
    titre: str
    articles: list[dict]
    url: str


class LegifranceClient:
    OAUTH_TOKEN_URL = "https://sandbox-oauth.piste.gouv.fr/api/oauth/token"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self._client_id = client_id or settings.legifrance_client_id
        self._client_secret = client_secret or settings.legifrance_client_secret

    def _require_credentials(self) -> None:
        if not (self._client_id and self._client_secret):
            raise RuntimeError(
                "Identifiants PISTE Légifrance manquants "
                "(LEGIFRANCE_CLIENT_ID / LEGIFRANCE_CLIENT_SECRET)."
            )

    async def _access_token(self) -> str:
        """Obtient un jeton OAuth2 (client credentials).

        TODO(Phase 1) : POST OAUTH_TOKEN_URL avec grant_type=client_credentials,
        scope=openid, puis mise en cache jusqu'à expiration.
        """
        self._require_credentials()
        raise NotImplementedError("Flux OAuth2 PISTE à implémenter (Phase 1).")

    async def fetch_texte(self, dossier_ref: str) -> TexteConsolide:
        raise NotImplementedError(
            "Récupération du texte consolidé Légifrance à implémenter (Phase 1)."
        )
