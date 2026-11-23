"""課程 MCP chatbot 的本機互動入口。"""

from __future__ import annotations

import argparse
import asyncio
import shlex
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from mcp_demo.client.llm_client import LLMClient
from mcp_demo.client.mcp_client_manager import MCPClientManager


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "mcp_servers.json"


class MCPChatbot:
    def __init__(self, config_path: Path) -> None:
        self.manager = MCPClientManager(config_path)
        self.llm = LLMClient()

    async def process_query(self, query: str) -> None:
        messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

        while True:
            response = self.llm.create_message(messages, self.manager.available_tools)
            has_tool_use = False
            tool_results: list[dict[str, Any]] = []

            for block in response.content:
                if block.type == "text":
                    print(block.text)
                elif block.type == "tool_use":
                    has_tool_use = True
                    result = await self.manager.call_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result.content,
                        }
                    )

            if not has_tool_use:
                return

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
            print("目前沒有可用的 prompts。")
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
        print("\nMCP Chatbot 已啟動；輸入 quit 結束。")
        print("@folders / @<topic> 讀取 Research resources")
        print("/prompts 列出 prompts；/prompt <name> key=value 執行 prompt")

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
                print(f"錯誤：{exc}")

    async def handle_command(self, query: str) -> None:
        parts = shlex.split(query)
        if parts[0].lower() == "/prompts":
            self.list_prompts()
            return
        if parts[0].lower() != "/prompt" or len(parts) < 2:
            print("用法：/prompt <name> <arg1=value1> <arg2=value2>")
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
        help="只驗證並顯示設定，不啟動 Server 或呼叫模型 API。",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    manager = MCPClientManager(args.config)
    if args.check_config:
        servers = manager.load_config()
        print("MCP 設定可讀：" + ", ".join(servers))
        return
    asyncio.run(MCPChatbot(args.config).run())


if __name__ == "__main__":
    main()
