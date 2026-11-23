# 課程來源對照

本文件只依 2026-11-21 在 workspace 實際找到的內容分類。由於沒有課程下載檔名、notebook 或課程頁面 metadata，單元歸類是依功能判斷，不宣稱是官方原始路徑。

## 初始檔案盤點

| 初始檔案 | 保存位置 | SHA-256 | 判定 |
| --- | --- | --- | --- |
| `mcp_chatbot.py` | `examples/adding_prompt_resource_features/mcp_chatbot.py` | `eff9afed8e8acdb47b3309fd0df9e95fb21e141a44ac55340db60ac8e4d6d7c2` | 同時列出並使用 tools、resources、prompts 的多 Server chatbot |
| `research_server.py` | `examples/adding_prompt_resource_features/research_server.py` | `5a1e5445462c1ef3ed5d40b3cafb7e95c4acc6e9035c025816fe486d3c3827f7` | Research tools、resources、prompt template |
| `server_config.json` | `examples/connecting_reference_servers/server_config.json` | `45ed8b28150f35d18cb01b256448e8d8145576b2cee49f9e62eadd1123565f47` | Research、Fetch、File System 的 stdio 啟動設定 |
| `main.py` | 已於 2026-11-23 整理時刪除 | 不適用 | uv scaffold，沒有 MCP 功能，無法證明是課程檔 |

原始檔案只搬移、未修改（2026-11-23 起 `course_examples/` 更名為 `examples/`，內容不變，雜湊仍有效）；上述雜湊可用 `shasum -a 256` 重新確認。

## 整合程式對照

| 整合檔案 | 來源 | 保留功能 | 必要修改 |
| --- | --- | --- | --- |
| `src/mcp_demo/client/mcp_chatbot.py` | 原始 `mcp_chatbot.py` | 互動聊天、tool loop、`@` resource、`/prompt` | 分離 Manager 與 LLM；一次正確加入完整 assistant tool-use 訊息；加入 `--check-config` |
| `src/mcp_demo/client/mcp_client_manager.py` | 原始 `MCP_ChatBot.connect_to_server(s)` | 多 stdio Server、tools、resources、prompts 的 discovery 與 session routing | 獨立模組；加入 resource templates 索引、名稱衝突檢查、專案路徑展開與 File System 範圍限制 |
| `src/mcp_demo/client/llm_client.py` | 原始 `Anthropic()` 與 `messages.create()` | Anthropic Messages API、原模型名稱、tools 傳入 | 集中供應商呼叫邊界；可用 `ANTHROPIC_MODEL` 覆寫模型 |
| `src/mcp_demo/servers/research_server.py` | 原始 `research_server.py` | `search_papers`、`extract_info`、`papers://folders`、`papers://{topic}`、`generate_search_prompt` | 資料固定到 `data/papers/`；UTF-8；空資料目錄可安全讀取；功能未刪減 |
| `config/mcp_servers.json` | 原始 `server_config.json` | Research、Fetch、File System 的原啟動工具與 stdio | 使用絕對專案 placeholder；File System 從原本的 `.` 收斂到 `data/` |

既有 `uv.lock` 實際鎖定 `mcp==1.7.1`；`pyproject.toml` 依課程 v1 API 加上 `<2` 上限，避免重新解依賴時跨到不相容的 major version。

## 缺少的課程檔案

- 所有課程 notebooks（workspace 沒有 `.ipynb`）。
- `creating_remote_servers/` 單元原始程式。
- 任何 SSE Server／SSE Client 範例或遠端 endpoint 設定。
- 課程提供的既有 `data/papers/` 樣本資料；目前目錄為空，執行搜尋後才會產生資料。

因此本次只整合已證實相容的 stdio 基準版。遠端傳輸不會以猜測內容補上，也不會覆蓋 Research Server 既有能力。
