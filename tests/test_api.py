from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import app.main as server


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "init_db", lambda: None)
    server.sessions.clear()
    with TestClient(server.app) as test_client:
        yield test_client
    server.sessions.clear()


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.parametrize(
    "payload",
    [
        {"message": "Hello"},
        {"session_id": "", "message": "Hello"},
        {"session_id": "valid", "message": ""},
        {"session_id": "valid", "message": "x" * 1001},
    ],
)
def test_chat_rejects_invalid_payload(client, payload):
    assert client.post("/chat", json=payload).status_code == 422


def test_chat_reuses_session(client, monkeypatch):
    chat = Mock()
    chat.send_message.return_value = SimpleNamespace(text="Hello!")
    create_chat = Mock(return_value=chat)
    monkeypatch.setattr(server, "create_chat", create_chat)

    first = client.post("/chat", json={"session_id": "patient-1", "message": "Hi"})
    second = client.post(
        "/chat", json={"session_id": "patient-1", "message": "How are you?"}
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == {"reply": "Hello!"}
    assert second.json() == {"reply": "Hello!"}
    create_chat.assert_called_once()
    assert chat.send_message.call_count == 2


def test_chat_returns_404_for_unknown_clinic(client):
    response = client.post(
        "/chat",
        json={
            "clinic_id": "missing_clinic",
            "session_id": "patient-1",
            "message": "Hi",
        },
    )

    assert response.status_code == 404


def test_chat_returns_503_when_gemini_initialization_fails(client, monkeypatch):
    monkeypatch.setattr(
        server, "create_chat", Mock(side_effect=RuntimeError("API key unavailable"))
    )

    response = client.post("/chat", json={"session_id": "patient-1", "message": "Hi"})

    assert response.status_code == 503
    assert "demo_clinic:patient-1" not in server.sessions
