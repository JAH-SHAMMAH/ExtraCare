import gzip, json
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

pytestmark = pytest.mark.asyncio


async def test_disabled_without_token(monkeypatch):
    monkeypatch.delenv("RESTORE_TOKEN", raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/v1/restore")).status_code == 404


async def test_wrong_token_rejected(monkeypatch):
    monkeypatch.setenv("RESTORE_TOKEN", "correct-horse-battery")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/v1/restore")).status_code == 200
        r = await c.post("/api/v1/restore", data={"token": "nope"}, files={"file": ("b.gz", b"x")})
        assert r.status_code == 403
