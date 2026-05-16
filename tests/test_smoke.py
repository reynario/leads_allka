"""Testes mínimos de sanidade: importar o app e checar endpoints estáticos.

Não exigem banco rodando — apenas checam que o app foi montado corretamente.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_root_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "sistema-leads-allka"


def test_openapi_loads() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Sistema de Leads Allka"
