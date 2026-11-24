"""Manage stdio connections and capability indexes for multiple MCP servers."""

from __future__ import annotations

import json
import os
import re
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClientManager:
    """Connect to configured MCP servers and index their capabilities."""

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path).resolve()
        self.project_root = self.config_path.parent.parent
        self.exit_stack = AsyncExitStack()
        self.available_tools: list[dict[str, Any]] = []
        self.available_prompts: list[dict[str, Any]] = []
        self.available_resources: list[dict[str, Any]] = []
        self.available_resource_templates: list[dict[str, Any]] = []
        self._tool_sessions: dict[str, ClientSession] = {}
        self.tool_servers: dict[str, str] = {}
        self._prompt_sessions: dict[str, ClientSession] = {}
        self._resource_sessions: dict[str, ClientSession] = {}
        self._resource_template_sessions: dict[str, ClientSession] = {}

    def load_config(self) -> dict[str, dict[str, Any]]:
        """Load configuration and expand project paths without starting processes."""
        with self.config_path.open(encoding="utf-8") as file:
            data = json.load(file)

        servers = data.get("mcpServers")
        if not isinstance(servers, dict) or not servers:
            raise ValueError("Configuration must contain a nonempty mcpServers object.")

        expanded: dict[str, dict[str, Any]] = {}
        for name, server in servers.items():
            if not isinstance(server, dict):
                raise ValueError(f"Server '{name}' configuration must be an object.")
            if not isinstance(server.get("command"), str):
                raise ValueError(f"Server '{name}' is missing a command.")
            args = server.get("args", [])
            if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
                raise ValueError(f"Server '{name}' args must be an array of strings.")

            values = {
                "PROJECT_ROOT": str(self.project_root),
                "PAPERS_DIR": str(self.project_root / "data" / "papers"),
                "PYTHON": sys.executable,
            }
            command = self._expand(server["command"], values)
            expanded_args = [self._expand(arg, values) for arg in args]
            environment = {
                key: self._expand(value, values)
                for key, value in server.get("env", {}).items()
            }
            expanded[name] = {
                "command": command,
                "args": expanded_args,
                "env": {**os.environ, **environment},
            }

        self._validate_filesystem_scope(expanded)
        return expanded

    @staticmethod
    def _expand(value: str, values: dict[str, str]) -> str:
        for key, replacement in values.items():
            value = value.replace(f"${{{key}}}", replacement)
        return value

    def _validate_filesystem_scope(self, servers: dict[str, dict[str, Any]]) -> None:
        """Restrict the File System server to the project data directory."""
        filesystem = servers.get("filesystem")
        if not filesystem or not filesystem["args"]:
            return
        allowed_root = (self.project_root / "data").resolve()
        configured_root = Path(filesystem["args"][-1]).resolve()
        if not configured_root.is_relative_to(allowed_root):
            raise ValueError(
                "filesystem Server may access only the project data directory or its subdirectories: "
                f"{configured_root}"
            )

    async def connect_all(self) -> None:
        for server_name, server_config in self.load_config().items():
            await self.connect(server_name, server_config)

    async def connect(self, server_name: str, server_config: dict[str, Any]) -> None:
        params = StdioServerParameters(**server_config)
        read, write = await self.exit_stack.enter_async_context(stdio_client(params))
        session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        await self._index_tools(server_name, session)
        await self._index_prompts(server_name, session)
        await self._index_resources(server_name, session)
        print(f"Connected to MCP Server: {server_name}")

    async def _index_tools(self, server_name: str, session: ClientSession) -> None:
        try:
            response = await session.list_tools()
        except Exception as exc:
            print(f"Warning: {server_name} could not list tools: {exc}")
            return
        for tool in response.tools:
            self._register_unique(self._tool_sessions, tool.name, session, "tool")
            self.tool_servers[tool.name] = server_name
            self.available_tools.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                }
            )

    async def _index_prompts(self, server_name: str, session: ClientSession) -> None:
        try:
            response = await session.list_prompts()
        except Exception as exc:
            print(f"Warning: {server_name} could not list prompts: {exc}")
            return
        for prompt in response.prompts:
            self._register_unique(self._prompt_sessions, prompt.name, session, "prompt")
            self.available_prompts.append(
                {
                    "name": prompt.name,
                    "description": prompt.description or "",
                    "arguments": prompt.arguments or [],
                }
            )

    async def _index_resources(self, server_name: str, session: ClientSession) -> None:
        try:
            response = await session.list_resources()
            for resource in response.resources:
                uri = str(resource.uri)
                self._register_unique(self._resource_sessions, uri, session, "resource")
                self.available_resources.append(
                    {
                        "uri": uri,
                        "name": resource.name,
                        "description": resource.description or "",
                    }
                )
        except Exception as exc:
            print(f"Warning: {server_name} could not list resources: {exc}")

        try:
            response = await session.list_resource_templates()
            for template in response.resourceTemplates:
                uri_template = str(template.uriTemplate)
                self._register_unique(
                    self._resource_template_sessions,
                    uri_template,
                    session,
                    "resource template",
                )
                self.available_resource_templates.append(
                    {
                        "uri_template": uri_template,
                        "name": template.name,
                        "description": template.description or "",
                    }
                )
        except Exception as exc:
            print(f"Warning: {server_name} could not list resource templates: {exc}")

    @staticmethod
    def _register_unique(
        registry: dict[str, ClientSession],
        name: str,
        session: ClientSession,
        capability: str,
    ) -> None:
        if name in registry:
            raise ValueError(f"Duplicate {capability} name across servers: {name}")
        registry[name] = session

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        session = self._tool_sessions.get(name)
        if session is None:
            raise KeyError(f"Tool not found: {name}")
        return await session.call_tool(name, arguments=arguments)

    async def read_resource(self, uri: str) -> Any:
        session = self._resource_sessions.get(uri)
        if session is None:
            for template, candidate in self._resource_template_sessions.items():
                if self._matches_uri_template(template, uri):
                    session = candidate
                    break
        if session is None:
            raise KeyError(f"Resource not found: {uri}")
        return await session.read_resource(uri=uri)

    async def get_prompt(self, name: str, arguments: dict[str, str]) -> Any:
        session = self._prompt_sessions.get(name)
        if session is None:
            raise KeyError(f"Prompt not found: {name}")
        return await session.get_prompt(name, arguments=arguments)

    @staticmethod
    def _matches_uri_template(template: str, uri: str) -> bool:
        pattern = re.escape(template)
        pattern = re.sub(r"\\\{[^{}]+\\\}", r"[^/]+", pattern)
        return re.fullmatch(pattern, uri) is not None

    async def close(self) -> None:
        await self.exit_stack.aclose()
