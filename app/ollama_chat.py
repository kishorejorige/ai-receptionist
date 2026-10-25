import json
import os
import re
from dataclasses import dataclass

import ollama


@dataclass
class Reply:
    text: str


def _clean(text: str) -> str:
    # remove any <think>...</think> block Qwen3 may add
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()


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
            self.messages.append(msg)
            if not msg.tool_calls:
                return Reply(_clean(msg.content))
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