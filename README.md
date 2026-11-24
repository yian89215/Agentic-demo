# MCP Essay Writer and Course Example Integration

The CLI chatbot connects to Research, Fetch, and File System MCP servers over stdio. It uses local Ollama `qwen3.5:4b` by default, or Anthropic when configured. See [AGENTS.md](AGENTS.md) for architecture and the complete file tree, and [docs/course_source_map.md](docs/course_source_map.md) for the preserved course sources. The original files in `examples/` are unchanged.

## Quick start

Requirements: Python 3.10+, uv/uvx, Node.js/npx, and either local Ollama with `qwen3.5:4b` or an Anthropic API key. Initial package installation, Fetch, and arXiv searches need network access.

```bash
cp .env.example .env
uv sync --frozen
uv run --frozen mcp-demo --check-config
uv run --frozen mcp-demo
```

Windows Git Bash can run `bash ./scripts/start.sh`. The script directs uv and npm caches to `.cache/`, syncs dependencies, tries to start local Ollama when needed, and launches the chatbot. `--check-config` validates configuration and File System scope without starting servers or calling a model.

In the CLI, enter a normal question, `@folders`, `@<topic>`, `/prompts`, `/prompt generate_search_prompt topic="edge ai" num_papers=3`, or `quit`. The model decides whether to call MCP tools for normal questions; `@` commands read Research resources directly. View the terminal workflow with `Get-Content docs/workflow.txt` in PowerShell or `cat docs/workflow.txt` in Git Bash.

## Web Essay Writer

After installing dependencies and configuring a model, run:

```bash
uv run --frozen mcp-demo-web
```

Open `http://127.0.0.1:8000`. The page first shows a clearly labeled illustrative completed run that can be reset and replayed by node. Its three sections are topic input, workflow, and node results. Select Planning, Research, Write, or Review in the graph or tabs to inspect each stage. Research shows sources and expandable tool calls; Write switches between drafts; Review shows decisions for each version. Reset the replay, then use Next step to advance one completed node at a time.

To run your own essay, enter a topic and choose a maximum of 0, 1, or 2 revisions. Research may decide that MCP tools are unnecessary. Review may approve a draft before the limit; if it still recommends changes at the limit, the result records that the limit was reached. With a limit of 0, writing ends after the first draft. The web UI does not accept the CLI `@` or `/prompt` commands.

Download the run JSON to preserve its events and import it later for replay. Each writing run has its own MCP connection; records stay only in server memory. JSON can contain the topic and model or tool data, so inspect it before sharing. The server binds locally by default and provides no login. Use `mcp-demo-web --host 127.0.0.1 --port 8000 --config config/mcp_servers.json` to change its address, port, or configuration. Windows Git Bash can run `bash ./scripts/start.sh --web`, followed by web options such as `--port 8001`.

The notebook searched general web pages with Tavily. This integration uses the project's arXiv Research MCP server, which suits academic or technical topics and does not search the general web. English topics receive a basic keyword relevance filter, not a full literature review. When research fails or finds no relevant papers, it records a warning and continues; the essay must not be treated as source verified. The workflow follows the notebook's node logic without a LangGraph dependency. The CLI still handles general questions and model-directed MCP tool calls.

The web UI defaults to Traditional Chinese and can switch to English. Its graph and result tabs use Planning, Research, Write, and Review. Solid lines show fixed steps; dashed lines show conditional completion, revision, and optional MCP Tools. Three one-click topic examples are included. The first-load demonstration is illustrative and does not represent real papers. This diagram explains the Python flow; it does not run LangGraph or a checkpointer.

## Model settings

`.env.example` lists all variables. The default is `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://127.0.0.1:11434`, and `OLLAMA_MODEL=qwen3.5:4b`. For Anthropic, set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` in local `.env`; the default model is `claude-3-7-sonnet-20250219`. Do not commit real keys.

## Docker Compose

```bash
docker compose build
docker compose run --rm mcp-chatbot
docker compose up --build mcp-web
docker compose down --remove-orphans
```

Compose offers a CLI service and a web service. The CLI starts all three MCP servers; the web service starts Research only. Each server subprocess runs inside its selected container. Research uses the main process's Python executable. The web service is available on the host at `http://127.0.0.1:8000`. `data/` is mounted at `/app/data`. To use host Ollama, Compose defaults to `http://host.docker.internal:11434`; ensure the container can reach it.

## Project layout

- `src/mcp_demo/client/`: CLI, MCP connection management, and model integration.
- `src/mcp_demo/workflows/`: Essay Writer planning, research, drafting, and revision.
- `src/mcp_demo/web/`: HTTP server, SSE stream, and the only served browser assets (`index.html`, `app.js`, `style.css`).
- `src/mcp_demo/servers/`: the project's Research MCP server.
- `scripts/`: launch scripts.
- `config/`: startup configuration for three MCP servers.
- `data/papers/`: generated Research results.
- `examples/`: unchanged course reference files.
- `docs/`: source map and terminal-readable workflow.

When changing code, configuration, or directories, review and update `AGENTS.md` as required by its collaboration guidelines.
