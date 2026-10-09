import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import init_db


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_health_check_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "Novel Translator AI" in data["app"]


@pytest.mark.asyncio
async def test_analyze_ssrf_blocked():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/analyze", json={"url": "http://127.0.0.1:8000/internal"})
        assert res.status_code == 400
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "SSRF_BLOCKED"


@pytest.mark.asyncio
async def test_novels_empty_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/novels")
        assert res.status_code == 200
        assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_proxy_image_ssrf_blocked():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/proxy/image?url=http://127.0.0.1:8000/secret.png")
        assert res.status_code == 400
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "SSRF_BLOCKED"
