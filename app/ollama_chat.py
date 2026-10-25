import json
import os
import re
from dataclasses import dataclass

import ollama


@dataclass
class Reply:
    text: str


def _clean(text: str) -> str:
    text = text or ""
    # Qwen3 may print reasoning, then </think>, with no opening tag
    if "</think>" in text:
        text = text.split("</think>")[-1]
    text = re.sub(r"<think>.*?(</think>|$)", "", text, flags=re.DOTALL)
    return text.strip()


class OllamaChat:
    """Same interface as the Gemini chat: send_message(text) -> object with .text"""

    def __init__(self, system_prompt: str, tools: list):
        self.client = ollama.Client(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
        self.model = os.getenv("OLLAMA_MODEL", "qwen3:4b")
        self.tools = {t.__name__: t for t in tools}
        self.messages = [{"role": "system", "content": system_prompt}]

    def send_message(self, text: str) -> Reply:
        self.messages.append({"role": "user", "content": text})
        for _ in range(5):  # max tool-call rounds
            resp = self.client.chat(
                model=self.model,
                messages=self.messages,
                tools=list(self.tools.values()),
                think=False,
                options={"temperature": 0.3, "num_ctx": 8192},
            )
            msg = resp.message
            if not msg.tool_calls:
                text = _clean(msg.content)
                self.messages.append({"role": "assistant", "content": text})
                return Reply(text)
            self.messages.append(msg)
            for call in msg.tool_calls:
                fn = self.tools.get(call.function.name)
                try:
                    result = fn(**call.function.arguments) if fn else {"error": "Unknown tool"}
                except TypeError as e:
                    result = {"error": f"Bad arguments: {e}"}
                self.messages.append({
                    "role": "tool",
                    "tool_name": call.function.name,
                    "content": json.dumps(result),
                })
        return Reply("Sorry, I couldn't complete that. Please call the clinic.")