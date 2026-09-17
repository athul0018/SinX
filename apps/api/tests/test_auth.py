from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_login_invalid(client: TestClient) -> None:
    res = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-password-here"})
    assert res.status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
