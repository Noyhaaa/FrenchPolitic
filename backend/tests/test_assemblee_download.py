"""Tests du téléchargement résumable des archives lourdes (reprise HTTP Range)."""
from __future__ import annotations

import io
import json
import zipfile

import httpx
import pytest

from app.ingestion.assemblee import AssembleeOpenDataClient


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.json", json.dumps({"ok": True}))
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, status_code: int, chunks: list[bytes], *, boom: bool):
        self.status_code = status_code
        self._chunks = chunks
        self._boom = boom

    def raise_for_status(self) -> None:
        pass

    async def aiter_bytes(self):
        for c in self._chunks:
            yield c
        if self._boom:
            raise httpx.RemoteProtocolError("peer closed connection")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeClient:
    """Simule une coupure : 1er appel = début puis exception ; 2e = reste (Range)."""

    appels: list[dict] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method, url, headers=None):
        _FakeClient.appels.append(dict(headers or {}))
        data = _zip_bytes()
        moitie = len(data) // 2
        if len(_FakeClient.appels) == 1:
            # 200 complet mais coupé au milieu.
            return _FakeResponse(200, [data[:moitie]], boom=True)
        # Reprise : le client a envoyé un Range ; on renvoie 206 + le reste.
        debut = int(headers["Range"].split("=")[1].split("-")[0])
        return _FakeResponse(206, [data[debut:]], boom=False)


@pytest.mark.asyncio
async def test_download_resumable_reprend_apres_coupure(monkeypatch):
    _FakeClient.appels = []
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    client = AssembleeOpenDataClient(legislature=17)
    client._ZIP_ATTENTE_LOURD_S = 0  # pas d'attente en test

    zf = await client._download_zip_resumable("http://x/Amendements.json.zip")

    assert zf.namelist() == ["a.json"]
    # Deux appels : le premier sans Range, le second avec (reprise).
    assert len(_FakeClient.appels) == 2
    assert "Range" not in _FakeClient.appels[0]
    assert _FakeClient.appels[1]["Range"].startswith("bytes=")
