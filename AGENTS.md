# Project Collaboration Guidelines

This project integrates the DeepLearning.AI “MCP: Build Rich-Context AI Apps with Anthropic” course examples that can be confirmed in this workspace. Original files are preserved in `examples/` and must not be modified. See [docs/course_source_map.md](docs/course_source_map.md) for sources and integration differences.

## Documentation updates for every change

Whenever code, configuration, dependencies, startup behavior, or directory structure changes, review and update this file in the same change. Check the file tree, architecture, environment variables, commands, and limitations below. Update `README.md` when usage changes. Update `docs/course_source_map.md` when integrated files are added or moved. Documentation must describe actual behavior.

## Language convention

Use English for code comments, docstrings, CLI messages, configuration descriptions, and developer documentation. The web UI may contain Chinese and English. Essay content may use the language requested by the user. Keep the original course files under `examples/` unchanged.

## Architecture

`src/mcp_demo/web/server.py` provides the local Essay Writer web UI from `src/mcp_demo/web/` through the `mcp-demo-web` command. Each topic gets its own MCP connection and run record. `src/mcp_demo/workflows/essay_writer.py` follows the state and node order in `examples/langraph.ipynb`: plan, initial research, draft, review, follow-up research, and revise. Users set a maximum of 0–2 revisions. Research nodes ask the model whether to call the Research MCP Server's `search_papers` and `extract_info` tools; they can proceed without tool calls. Review can approve early, and a review at the limit records whether the draft passed or the limit was reached. This integration uses the existing arXiv tools instead of the notebook's Tavily search, implements the node sequence in Python, and does not install LangGraph. SSE sends node status, inputs, outputs, and durations to the browser. Runs can be downloaded as JSON and imported for replay. The CLI retains normal chat and model-directed tool use; the web UI does not support CLI `@` or `/prompt` commands.

`src/mcp_demo/client/mcp_chatbot.py` is the CLI entry point (`mcp-demo` when installed). `src/mcp_demo/client/llm_client.py` uses local Ollama (`qwen3.5:4b`) by default, or Anthropic with `LLM_PROVIDER=anthropic`. `src/mcp_demo/client/mcp_client_manager.py` starts, indexes, and routes these stdio MCP servers:

- Research: `src/mcp_demo/servers/research_server.py` provides `search_papers`, `extract_info`, `papers://folders`, `papers://{topic}`, and `generate_search_prompt`. arXiv results are stored in `data/papers/`. Windows-invalid characters in topic folder names are replaced with underscores.
- Fetch: the `mcp-server-fetch` package retrieves web pages.
- File System: `@modelcontextprotocol/server-filesystem` is restricted to the project's `data/` directory.

Startup commands are in `config/mcp_servers.json`. The CLI starts all three servers; the Essay Writer web service starts only Research. The Research subprocess uses the current Python executable and does not require `uv` on PATH. In Docker Compose, subprocesses run inside the selected `mcp-chatbot` or `mcp-web` container. Ollama is a separate model service. There are no remote or SSE MCP servers; web SSE only streams run events to the browser.

The active web interface lives in `src/mcp_demo/web/`: `server.py` provides HTTP, SSE, and JSON run records, while `index.html`, `app.js`, and `style.css` are the only served browser assets. The earlier frontend is retained only in the ignored local `.cache/retired-web-v1/` backup. `src/mcp_demo/workflows/essay_writer.py` owns the writing flow. The interface has topic input, a workflow diagram, and one result panel with Planning, Research, Write, and Review tabs. Research may skip MCP tools based on a model decision. Review can approve early or report a revision limit. Result tabs include versions, feedback, sources, and expandable tool calls. Replay advances by completed agent node while retaining tool events inside Research. A labeled illustrative run appears on first open. Live runs and imported version 1 JSON remain supported.

## Tracked file tree

```text
.
├── AGENTS.md
├── README.md
├── pyproject.toml          # Package metadata, dependencies, entry points, build settings
├── uv.lock                 # Locked dependencies
├── Dockerfile
├── compose.yaml
├── .env.example
├── .gitignore
├── .dockerignore
├── config/
│   └── mcp_servers.json
├── src/
│   └── mcp_demo/
│       ├── __init__.py
│       ├── workflows/
│       │   ├── __init__.py
│       │   └── essay_writer.py # Planning, research, drafting, and revision flow
│       ├── web/
│       │   ├── __init__.py
│       │   ├── server.py      # Local HTTP, SSE, and JSON run records
│       │   ├── index.html
│       │   ├── app.js
│       │   └── style.css
│       ├── client/
│       │   ├── __init__.py
│       │   ├── mcp_chatbot.py
│       │   ├── mcp_client_manager.py
│       │   └── llm_client.py
│       └── servers/
│           ├── __init__.py
│           └── research_server.py
├── scripts/
│   └── start.sh            # Windows Git Bash launcher
├── tests/
│   └── test_essay_writer.py # Automatic research and revision tests
├── data/
│   └── papers/.gitkeep     # Untracked runtime paper data goes here
├── examples/               # Unmodified, read-only course references
│   ├── langraph.ipynb       # Essay Writer notebook; course origin unconfirmed
│   ├── connecting_reference_servers/server_config.json
│   └── adding_prompt_resource_features/
│       ├── mcp_chatbot.py
│       └── research_server.py
└── docs/
    ├── course_source_map.md
    └── workflow.txt          # Terminal-readable ASCII workflow
```

`.env`, `.venv/`, `.cache/`, `__pycache__`, and generated paper data are local runtime artifacts and are not part of the tracked tree.

## Directory rules

- Keep project configuration and documentation at the root; code in `src/mcp_demo/`, scripts in `scripts/`, server configuration in `config/`, and read-only references in `examples/`.
- Keep local tool caches under `.cache/`. `scripts/start.sh` directs uv and npm caches there and can use `.cache/uv-tool/bin`. Legacy root cache directories `.uv-cache/`, `.uv-python/`, `.uv-tools/`, and `.npm-cache/` can be removed. Keep `.uv-bootstrap/` only when an older local uv installation uses it.
- For sharing or backup, use `git archive -o Agentic-demo.zip HEAD`, or exclude `.venv`, `.cache`, `.uv-*`, `.npm-cache`, `__pycache__`, `.env`, and `.DS_Store` when using `zip -r`.
- Keep real secrets only in local `.env`, never in an archive, Docker image, or repository. Maintain the template in `.env.example`.
- Place new modules in `src/mcp_demo/` and use absolute `mcp_demo.` imports so imports do not depend on the working directory.

## Run and check

Requirements: Python 3.10+, uv/uvx, and Node.js/npx. Ollama mode needs a local Ollama service and model; Anthropic mode needs an API key. Initial Fetch and package installation, and arXiv searches, need network access.

```bash
cp .env.example .env
uv sync --frozen
uv run --frozen mcp-demo --check-config
uv run --frozen mcp-demo
uv run --frozen mcp-demo-web
```

The web UI defaults to `http://127.0.0.1:8000`; `--host`, `--port`, and `--config` customize it. An illustrative completed run appears on first open and can be reset and replayed by node. Enter an essay topic and requirements, then select a maximum of 0–2 revisions. Research decides whether arXiv tools would help. Run events stay in server memory; download the run JSON to keep it and import it later for browser replay. JSON contains the topic and model/tool inputs and outputs, so inspect it before sharing. The web server binds locally by default and has no login; do not expose it directly to the public internet. Run the Docker web service with `docker compose up --build mcp-web` and visit `http://127.0.0.1:8000` on the host. `mcp-chatbot` remains the interactive terminal service.

Before starting a test service on this development host, check whether the target port is in use and record the port and process started for this test. Stop only that process afterward. A VS Code SSH browser's `127.0.0.1` may refer to a remote host or forwarded port; verify the actual host reached.

Windows Git Bash can run `bash ./scripts/start.sh` for CLI or `bash ./scripts/start.sh --web` for web. The script redirects caches to `.cache/`, locates uv on PATH or in `.cache/uv-tool/bin` or `.uv-bootstrap/bin`, checks Node.js, tries to start local Ollama when needed, and launches the selected entry point. Docker Compose uses `docker compose build` and `docker compose run --rm mcp-chatbot`, mounting `data/` at `/app/data`. `--check-config` validates configuration and File System scope without starting servers or calling a model.

CLI commands: plain text goes to the model; `@folders` lists saved topics; `@<topic>` reads a Research resource; `/prompts` lists prompts; `/prompt generate_search_prompt topic="edge ai" num_papers=3` retrieves a prompt and sends it to the model; `quit` exits.

The high-level flow is in `docs/workflow.txt`. View it with `Get-Content docs/workflow.txt` in PowerShell or `cat docs/workflow.txt` in Git Bash. It documents existing behavior without changing startup or environment variables.

## Environment variables and limitations

- `LLM_PROVIDER`: `ollama` (default) or `anthropic`.
- `OLLAMA_MODEL`: defaults to `qwen3.5:4b`; `OLLAMA_BASE_URL`: defaults to `http://127.0.0.1:11434`; `OLLAMA_NUM_CTX`: defaults to `16384`.
- Essay Writer sets `think=false` for Ollama text stages so outlines and essays do not become empty when the model only returns reasoning. Existing CLI chat calls are unaffected.
- `ANTHROPIC_API_KEY`: required for Anthropic and must not be committed; `ANTHROPIC_MODEL`: defaults to `claude-3-7-sonnet-20250219`.
- `PAPERS_DIR`: set by MCP configuration to `data/papers/`; usually no manual setting is needed.
- Hatchling packages the project. `[project.scripts]` in `pyproject.toml` defines both `mcp-demo` and `mcp-demo-web`.
- The web server uses Python's standard HTTP server and SSE without extra Python dependencies or environment variables. Essay Writer uses the existing LLM settings. arXiv research needs network access and does not search general web pages. If search fails or finds no papers, research records a warning and writing continues; the resulting essay is not source-verified. Run records are held only in server memory, so import a previously downloaded JSON file after restart.
- English-topic research results receive a basic filter using the topic's first main keyword. This does not replace full relevance or quality review.
- The Python MCP SDK is limited to `mcp>=1.7.1,<2` for the v1 API used here.
- `examples/langraph.ipynb` exists in the workspace, but its course lesson is unconfirmed. Do not invent remote Server or SSE course files.
