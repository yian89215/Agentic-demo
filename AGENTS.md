# 專案協作規範

本專案整合目前 workspace 中可確認的 DeepLearning.AI「MCP: Build Rich-Context AI Apps with Anthropic」課程範例。原始檔保存在 `examples/`，請勿修改；來源與整合差異見 [docs/course_source_map.md](docs/course_source_map.md)。

## 每次變更的文件同步

每次修改程式、設定、依賴、啟動方式或目錄結構時，都要在同一次變更中檢查並更新本檔 `AGENTS.md`。至少核對下方檔案樹、架構、環境變數、執行指令與限制；若有受影響的使用方式，也同步更新 `README.md`。新增或移動整合檔案時，同步更新 `docs/course_source_map.md`。文件應描述實際程式行為，不要只沿用舊說明。

## 架構

命令列入口 `src/mcp_demo/client/mcp_chatbot.py`（安裝後也可用指令 `mcp-demo`） 接收使用者輸入。`src/mcp_demo/client/llm_client.py` 對接模型：預設本機 Ollama（`qwen3.5:4b`），也可設 `LLM_PROVIDER=anthropic` 使用 Anthropic API。`src/mcp_demo/client/mcp_client_manager.py` 以 stdio 啟動、索引並路由三個 MCP Server：

- Research：本專案的 `src/mcp_demo/servers/research_server.py`。提供 `search_papers`、`extract_info` tools，`papers://folders` 與 `papers://{topic}` resources，以及 `generate_search_prompt` prompt。搜尋 arXiv 後將資料存於 `data/papers/`。
- Fetch：套件 `mcp-server-fetch`，提供網頁擷取能力。
- File System：套件 `@modelcontextprotocol/server-filesystem`，根目錄限制在專案 `data/`。

Server 的啟動命令在 `config/mcp_servers.json`。三個 MCP Server 都是由 Client 啟動的本機子程序；Docker Compose 執行時則在同一個 `mcp-chatbot` 容器內。Ollama 是獨立模型服務，不是 MCP Server。沒有遠端或 SSE MCP Server。

## 檔案樹

```text
.
├── AGENTS.md
├── README.md
├── pyproject.toml          # 專案身分、依賴、`mcp-demo` 指令與打包設定
├── uv.lock                 # 鎖定的依賴版本
├── Dockerfile
├── compose.yaml
├── .env.example
├── .gitignore
├── .dockerignore
├── config/
│   └── mcp_servers.json
├── src/
│   └── mcp_demo/           # Python package
│       ├── __init__.py
│       ├── client/
│       │   ├── __init__.py
│       │   ├── mcp_chatbot.py
│       │   ├── mcp_client_manager.py
│       │   └── llm_client.py
│       └── servers/
│           ├── __init__.py
│           └── research_server.py
├── scripts/
│   └── start.sh            # Windows Git Bash 快速啟動
├── data/
│   └── papers/.gitkeep     # 執行產物目錄，內容不追蹤
├── examples/               # 未修改的原始課程檔（唯讀參考）
│   ├── connecting_reference_servers/server_config.json
│   └── adding_prompt_resource_features/
│       ├── mcp_chatbot.py
│       └── research_server.py
└── docs/
    ├── course_source_map.md
    └── workflow.txt          # 可直接在終端機閱讀的 ASCII 流程圖
```

`.env`、`.venv/`、`.cache/`（uv 與 npm 快取）、`__pycache__` 與搜尋產生的論文資料屬本機執行產物，不列入上述追蹤樹。

## 目錄整理規範

- 根目錄只放專案設定與文件；程式放 `src/mcp_demo/`，腳本放 `scripts/`，設定放 `config/`，唯讀參考放 `examples/`。
- 本機工具快取不放在專案根目錄。`scripts/start.sh` 預設把 uv 與 npm 快取導向 `.cache/`；舊版根目錄的 `.uv-cache/`、`.uv-python/`、`.uv-tools/`、`.npm-cache/` 可直接刪除，`.uv-bootstrap/` 只在使用本機 uv 時保留。
- 分享或備份專案時不要直接壓縮整個資料夾。使用 `git archive -o Agentic-demo.zip HEAD`，或以 `zip -r` 搭配 `-x` 排除 `.venv`、`.cache`、`.uv-*`、`.npm-cache`、`__pycache__`、`.env`、`.DS_Store`。
- 真實金鑰只放在本機 `.env`，不得出現在壓縮檔、Docker image 或版本庫；範本維護在 `.env.example`。
- 新增程式模組時放進 `src/mcp_demo/` 並用 `mcp_demo.` 絕對匯入，不要再依賴「從特定資料夾執行」才能找到模組。

## 執行與檢查

需求：Python 3.10+、uv/uvx、Node.js/npx；使用 Ollama 時需本機 Ollama 與模型，使用 Anthropic 時需 API key。Fetch、arXiv 與套件首次安裝需要網路。

```bash
cp .env.example .env
uv sync --frozen
uv run --frozen mcp-demo --check-config
uv run --frozen mcp-demo
```

Windows Git Bash 可執行 `bash ./scripts/start.sh`；腳本會把快取導向 `.cache/`、尋找本地 uv、檢查 Node.js，必要時嘗試啟動本機 Ollama，再以 `mcp-demo` 啟動 Client。Docker Compose 使用 `docker compose build` 與 `docker compose run --rm mcp-chatbot`，並把 `data/` 掛載到 `/app/data`。`--check-config` 只驗證設定和 File System 範圍，不啟動 Server 或呼叫模型。

互動指令：一般文字送模型；`@folders` 列出已存主題；`@<topic>` 讀取 Research resource；`/prompts` 列出 prompts；`/prompt generate_search_prompt topic="edge ai" num_papers=3` 取得 prompt 後送模型；`quit` 結束。

高階使用流程見 `docs/workflow.txt`；在 PowerShell 用 `Get-Content docs/workflow.txt`，在 Git Bash 用 `cat docs/workflow.txt` 檢視。此文件只說明既有流程，不改變啟動方式或環境變數。

## 環境變數與限制

- `LLM_PROVIDER`：`ollama`（預設）或 `anthropic`。
- `OLLAMA_MODEL`：預設 `qwen3.5:4b`；`OLLAMA_BASE_URL`：本機預設 `http://127.0.0.1:11434`；`OLLAMA_NUM_CTX`：預設 `16384`。
- `ANTHROPIC_API_KEY`：選 Anthropic 時必填，不可提交；`ANTHROPIC_MODEL`：預設 `claude-3-7-sonnet-20250219`。
- `PAPERS_DIR`：由 MCP 設定指向 `data/papers/`，一般無需手動設定。
- 專案以 hatchling 打包；`pyproject.toml` 的 `[project.scripts]` 定義 `mcp-demo` 進入點。
- Python MCP SDK 限定 `mcp>=1.7.1,<2`，對應目前程式使用的 v1 API。
- `examples/` 沒有 notebooks、遠端 Server 或 SSE 單元原始檔；不要推測補造。
