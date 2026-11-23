# MCP 課程範例整合專案

命令列 Chatbot 透過 stdio 連接 Research、Fetch、File System 三個 MCP Server。聊天模型預設為本機 Ollama `qwen3.5:4b`，也可選 Anthropic API。架構和完整檔案樹見 [AGENTS.md](AGENTS.md)；原始課程檔保存在 `examples/`，來源見 [docs/course_source_map.md](docs/course_source_map.md)。

## 快速開始

需要 Python 3.10+、uv/uvx、Node.js/npx；預設模式還需要安裝 Ollama 並備妥 `qwen3.5:4b` 模型。首次取得套件與使用 Fetch、arXiv 需網路。

```bash
cp .env.example .env
uv sync --frozen
uv run --frozen mcp-demo --check-config
uv run --frozen mcp-demo
```

Windows Git Bash 可以執行 `bash ./scripts/start.sh`。此腳本會把 uv／npm 快取導向 `.cache/`、同步依賴，必要時嘗試啟動本機 Ollama，然後啟動 Chatbot。`--check-config` 只檢查設定與 File System 存取路徑，不啟動 Server 或呼叫模型。

互動中可輸入一般問題、`@folders`、`@<topic>`、`/prompts`、`/prompt generate_search_prompt topic="edge ai" num_papers=3`，或 `quit` 結束。一般問題由模型決定是否呼叫 MCP tools；`@` 指令直接讀取 Research resources。

想在終端機查看完整流程圖，執行 `Get-Content docs/workflow.txt`（PowerShell）或 `cat docs/workflow.txt`（Git Bash）。文字版流程圖見 [docs/workflow.txt](docs/workflow.txt)。

## 模型設定

`.env.example` 列出所有變數。預設 `LLM_PROVIDER=ollama`，Ollama 位址為 `http://127.0.0.1:11434`，模型為 `qwen3.5:4b`。若改用 Anthropic，在 `.env` 設定 `LLM_PROVIDER=anthropic` 與 `ANTHROPIC_API_KEY`；模型預設為 `claude-3-7-sonnet-20250219`。請勿提交真實金鑰。

## Docker Compose

```bash
docker compose build
docker compose run --rm mcp-chatbot
docker compose down --remove-orphans
```

Compose 只建立一個 `mcp-chatbot` 容器；三個 MCP Server 是容器內的子程序。`data/` 掛載到 `/app/data`。若使用主機上的 Ollama，Compose 預設用 `http://host.docker.internal:11434` 連線，需確認容器可存取該服務。

## 專案目錄

- `src/mcp_demo/client/`：互動入口、MCP 連線管理、模型介接。
- `src/mcp_demo/servers/`：本專案實作的 Research Server。
- `scripts/`：啟動腳本。
- `config/`：三個 MCP Server 的啟動設定。
- `data/papers/`：Research 搜尋結果。
- `examples/`：未修改的原始課程檔。
- `docs/`：原始檔與整合程式的對照，以及終端機可讀的流程圖。

修改程式、設定或目錄時，請同步核對並更新 `AGENTS.md`，詳見該檔的協作規範。
