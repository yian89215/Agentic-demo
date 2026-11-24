"""Local interactive entry point for the course MCP chatbot."""

from __future__ import annotations

import argparse
import asyncio
import shlex
from pathlib import Path
from typing import Any
from collections.abc import Callable
from time import perf_counter

from dotenv import load_dotenv

from mcp_demo.client.llm_client import LLMClient
from mcp_demo.client.mcp_client_manager import MCPClientManager


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "mcp_servers.json"


class MCPChatbot:
    def __init__(self, config_path: Path) -> None:
        self.manager = MCPClientManager(config_path)
        self.llm = LLMClient()

    async def process_query(
        self,
        query: str,
        emit: Callable[[str, str, Any, Any, float | None, str | None], None] | None = None,
        print_output: bool = True,
    ) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

        while True:
            answer_parts: list[str] = []
            llm_input = {"messages": messages, "tools": self.manager.available_tools}
            if emit:
                emit("llm", "start", llm_input, None, None, None)
            started = perf_counter()
            try:
                response = await asyncio.to_thread(
                    self.llm.create_message, messages, self.manager.available_tools
                )
            except Exception as exc:
                if emit:
                    emit("llm", "error", llm_input, str(exc), perf_counter() - started, None)
                raise
            llm_output = []
            for block in response.content:
                if block.type == "text":
                    llm_output.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    llm_output.append({"type": "tool_use", "id": block.id,
                                       "name": block.name, "input": block.input})
                else:
                    llm_output.append({"type": block.type, "value": str(block)})
            if emit:
                emit("llm", "complete", llm_input, llm_output, perf_counter() - started, None)
            has_tool_use = False
            tool_results: list[dict[str, Any]] = []

            for block in response.content:
                if block.type == "text":
                    if print_output:
                        print(block.text)
                    answer_parts.append(block.text)
                elif block.type == "tool_use":
                    has_tool_use = True
                    server = self.manager.tool_servers.get(block.name, "unknown")
                    tool_input = {"tool": block.name, "arguments": block.input}
                    if emit:
                        emit(server, "start", tool_input, None, None, block.id)
                    started = perf_counter()
                    try:
                        result = await self.manager.call_tool(block.name, block.input)
                    except Exception as exc:
                        if emit:
                            emit(server, "error", tool_input, str(exc), perf_counter() - started, block.id)
                        raise
                    if emit:
                        emit(server, "error" if getattr(result, "isError", False) else "complete",
                             tool_input, result, perf_counter() - started, block.id)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result.content,
                        }
                    )

            if not has_tool_use:
                answer = "\n".join(answer_parts)
                if emit:
                    emit("answer", "complete", llm_output, answer, 0.0, None)
                return answer

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    async def print_resource(self, uri: str) -> None:
        result = await self.manager.read_resource(uri)
        print(f"\nResource: {uri}")
        for content in result.contents:
            text = getattr(content, "text", None)
            print(text if text is not None else content)

    def list_prompts(self) -> None:
        if not self.manager.available_prompts:
            print("No prompts are available.")
            return
        print("\nAvailable prompts:")
        for prompt in self.manager.available_prompts:
            print(f"- {prompt['name']}: {prompt['description']}")
            for argument in prompt["arguments"]:
                name = getattr(argument, "name", str(argument))
                print(f"  - {name}")

    async def execute_prompt(self, name: str, arguments: dict[str, str]) -> None:
        result = await self.manager.get_prompt(name, arguments)
        parts: list[str] = []
        for message in result.messages:
            content = message.content
            if isinstance(content, str):
                parts.append(content)
            elif hasattr(content, "text"):
                parts.append(content.text)
            elif isinstance(content, list):
                parts.extend(
                    item.text if hasattr(item, "text") else str(item) for item in content
                )
        await self.process_query("\n".join(parts))

    async def chat_loop(self) -> None:
        print("\nMCP Chatbot is ready; enter quit to exit.")
        print("@folders / @<topic> reads Research resources")
        print("/prompts lists prompts; /prompt <name> key=value runs a prompt")

        while True:
            query = (await asyncio.to_thread(input, "\nQuery: ")).strip()
            if not query:
                continue
            if query.lower() == "quit":
                return
            try:
                if query.startswith("@"):
                    topic = query[1:]
                    uri = "papers://folders" if topic == "folders" else f"papers://{topic}"
                    await self.print_resource(uri)
                elif query.startswith("/"):
                    await self.handle_command(query)
                else:
                    await self.process_query(query)
            except Exception as exc:
                print(f"Error: {exc}")

    async def handle_command(self, query: str) -> None:
        parts = shlex.split(query)
        if parts[0].lower() == "/prompts":
            self.list_prompts()
            return
        if parts[0].lower() != "/prompt" or len(parts) < 2:
            print("Usage: /prompt <name> <arg1=value1> <arg2=value2>")
            return
        arguments = dict(part.split("=", 1) for part in parts[2:] if "=" in part)
        await self.execute_prompt(parts[1], arguments)

    async def run(self) -> None:
        try:
            await self.manager.connect_all()
            await self.chat_loop()
        finally:
            await self.manager.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCP course chatbot")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate and display configuration without starting servers or calling the model API.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    manager = MCPClientManager(args.config)
    if args.check_config:
        servers = manager.load_config()
        print("MCP configuration is valid: " + ", ".join(servers))
        return
    asyncio.run(MCPChatbot(args.config).run())


if __name__ == "__main__":
    main()
