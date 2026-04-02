"""Tests for API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from entity_resolution.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestSearchEndpoint:
    @pytest.mark.asyncio
    async def test_search_validation_empty_query(self, client):
        """Empty query should fail validation."""
        response = await client.post("/search", json={"query": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_valid_request(self, client):
        """Valid search should return 200."""
        response = await client.post("/search", json={"query": "Sony"})
        assert response.status_code == 200
        data = response.json()
        assert "matches" in data
        assert data["query"] == "Sony"


class TestMatchEndpoint:
    @pytest.mark.asyncio
    async def test_match_valid(self, client):
        response = await client.post("/match", json={"name_a": "Sony", "name_b": "ソニー"})
        assert response.status_code == 200
        data = response.json()
        assert "final_score" in data

    @pytest.mark.asyncio
    async def test_match_validation(self, client):
        response = await client.post("/match", json={"name_a": "Sony"})
        assert response.status_code == 422


class TestBatchEndpoint:
    @pytest.mark.asyncio
    async def test_batch_submit(self, client):
        response = await client.post(
            "/batch", json={"queries": [{"query": "Sony"}, {"query": "Toyota"}]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    @pytest.mark.asyncio
    async def test_batch_get_nonexistent(self, client):
        response = await client.get("/batch/nonexistent-id")
        assert response.status_code == 404
