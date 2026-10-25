import json
from types import SimpleNamespace
from unittest.mock import Mock

from app.ollama_chat import OllamaChat


def test_ollama_chat_runs_tool_call_and_returns_final_text(monkeypatch):
    tool_calls = []

    def check_availability(day):
        tool_calls.append(day)
        return {"day": day, "free_slots": ["14:00"]}

    tool_call = SimpleNamespace(
        function=SimpleNamespace(
            name="check_availability",
            arguments={"day": "2026-10-26"},
        )
    )
    tool_response = SimpleNamespace(
        message=SimpleNamespace(
            role="assistant", content="", tool_calls=[tool_call]
        )
    )
    final_response = SimpleNamespace(
        message=SimpleNamespace(
            role="assistant", content="2:00 PM is available.", tool_calls=[]
        )
    )
    client = Mock()
    client.chat.side_effect = [tool_response, final_response]
    monkeypatch.setattr("app.ollama_chat.ollama.Client", Mock(return_value=client))

    chat = OllamaChat("system prompt", [check_availability])

    reply = chat.send_message("Can I come tomorrow at 2?")

    assert tool_calls == ["2026-10-26"]
    assert reply.text == "2:00 PM is available."
    assert client.chat.call_count == 2
    sent_messages = client.chat.call_args_list[1].kwargs["messages"]
    assert sent_messages[-2] == {
        "role": "tool",
        "tool_name": "check_availability",
        "content": json.dumps({"day": "2026-10-26", "free_slots": ["14:00"]}),
    }


def test_create_chat_uses_configured_ollama_provider(monkeypatch):
    from app import agent

    ollama_chat = Mock(return_value=object())
    monkeypatch.setattr(agent, "load_dotenv", Mock())
    monkeypatch.setattr(agent, "make_tools", Mock(return_value=[]))
    monkeypatch.setattr(agent, "build_system_prompt", Mock(return_value="prompt"))
    monkeypatch.setattr("app.ollama_chat.OllamaChat", ollama_chat)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")

    result = agent.create_chat("demo_clinic", {})

    assert result is ollama_chat.return_value
    ollama_chat.assert_called_once_with("prompt", [])
