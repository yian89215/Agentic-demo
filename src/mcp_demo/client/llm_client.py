"""LLM adapter for Anthropic and a local Ollama server."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from anthropic import Anthropic


DEFAULT_ANTHROPIC_MODEL = "claude-3-7-sonnet-20250219"
DEFAULT_OLLAMA_MODEL = "qwen3.5:4b"


class LLMClient:
    """Return Anthropic-style content blocks to the MCP chatbot."""

    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
        self._tool_names: dict[str, str] = {}
        if self.provider == "anthropic":
            self.model = os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
            self.client = Anthropic()
        elif self.provider == "ollama":
            self.model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
            self.base_url = os.getenv(
                "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
            ).rstrip("/")
        else:
            raise ValueError("LLM_PROVIDER must be 'ollama' or 'anthropic'")

    def create_message(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        if self.provider == "anthropic":
            return self.client.messages.create(
                max_tokens=2024,
                model=self.model,
                tools=tools,
                messages=messages,
            )

        payload = {
            "model": self.model,
            "stream": False,
            "options": {"num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "16384"))},
            "messages": self._ollama_messages(messages),
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool["input_schema"],
                    },
                }
                for tool in tools
            ],
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=300) as response:
                message = json.load(response)["message"]
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(
                f"Cannot reach Ollama at {self.base_url}; start the Ollama app."
            ) from exc

        content: list[Any] = []
        if message.get("content"):
            content.append(SimpleNamespace(type="text", text=message["content"]))
        for call in message.get("tool_calls") or []:
            function = call["function"]
            call_id = str(uuid4())
            self._tool_names[call_id] = function["name"]
            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            content.append(
                SimpleNamespace(
                    type="tool_use",
                    id=call_id,
                    name=function["name"],
                    input=arguments,
                )
            )
        return SimpleNamespace(content=content)

    def create_text(self, system: str, prompt: str, max_tokens: int = 3072) -> str:
        """Generate one plain-text response for a deterministic writing stage."""
        if self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return "\n".join(block.text for block in response.content if block.type == "text")

        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "options": {"num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "16384")),
                        "num_predict": max_tokens},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=300) as response:
                return json.load(response)["message"]["content"]
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(
                f"Cannot reach Ollama at {self.base_url}; start the Ollama app."
            ) from exc

    def _ollama_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for message in messages:
            body = message["content"]
            if isinstance(body, str):
                converted.append({"role": message["role"], "content": body})
            elif message["role"] == "assistant":
                text = "\n".join(block.text for block in body if block.type == "text")
                calls = [
                    {
                        "type": "function",
                        "function": {"name": block.name, "arguments": block.input},
                    }
                    for block in body
                    if block.type == "tool_use"
                ]
                converted.append(
                    {"role": "assistant", "content": text, "tool_calls": calls}
                )
            else:
                for block in body:
                    if block["type"] != "tool_result":
                        continue
                    parts = block["content"]
                    result_text = "\n".join(
                        part.text if hasattr(part, "text") else str(part)
                        for part in parts
                    )
                    converted.append(
                        {
                            "role": "tool",
                            "tool_name": self._tool_names[block["tool_use_id"]],
                            "content": result_text,
                        }
                    )
        return converted
