from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import ollama
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


def test_home_serves_chat_page(client):
    response = client.get("/?clinic=demo_clinic")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Dental Clinic Assistant" in response.text


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


def test_chat_uses_new_backend_when_provider_changes(client, monkeypatch):
    first_chat = Mock()
    first_chat.send_message.return_value = SimpleNamespace(text="Gemini")
    second_chat = Mock()
    second_chat.send_message.return_value = SimpleNamespace(text="Ollama")
    create_chat = Mock(side_effect=[first_chat, second_chat])
    monkeypatch.setattr(server, "create_chat", create_chat)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")

    first = client.post("/chat", json={"session_id": "patient-1", "message": "Hi"})
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    second = client.post("/chat", json={"session_id": "patient-1", "message": "Hi"})

    assert first.json() == {"reply": "Gemini"}
    assert second.json() == {"reply": "Ollama"}
    assert create_chat.call_count == 2


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


def test_chat_returns_500_when_chat_initialization_fails(client, monkeypatch):
    monkeypatch.setattr(
        server, "create_chat", Mock(side_effect=RuntimeError("API key unavailable"))
    )

    response = client.post("/chat", json={"session_id": "patient-1", "message": "Hi"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong."}
    assert "demo_clinic:patient-1" not in server.sessions


@pytest.mark.parametrize(
    ("error", "expected_detail", "log_message"),
    [
        (
            ConnectionError("Ollama unavailable"),
            "Ollama is unavailable. Check that the local server is running.",
            "Ollama connection refused or unavailable",
        ),
        (
            httpx.ReadTimeout("Ollama timeout"),
            "Ollama timed out. Please try again shortly.",
            "Ollama request timed out",
        ),
        (
            ollama.ResponseError("model not found", status_code=404),
            "The configured Ollama model was not found. Pull the model and try again.",
            "Ollama model not found",
        ),
    ],
)
def test_chat_returns_clear_503_for_ollama_errors(
    client, monkeypatch, caplog, error, expected_detail, log_message
):
    monkeypatch.setattr(server, "create_chat", Mock(side_effect=error))

    response = client.post("/chat", json={"session_id": "patient-1", "message": "Hi"})

    assert response.status_code == 503
    assert response.json() == {"detail": expected_detail}
    assert log_message in caplog.text
