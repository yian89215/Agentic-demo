# Course Source Map

This document classifies only course material confirmed in this workspace. Lesson placement is inferred from behavior because course download filenames and page metadata are unavailable. The course origin of `examples/langraph.ipynb` remains unconfirmed.

## Original file inventory

| Initial file | Preserved location | SHA-256 | Assessment |
| --- | --- | --- | --- |
| `mcp_chatbot.py` | `examples/adding_prompt_resource_features/mcp_chatbot.py` | `eff9afed8e8acdb47b3309fd0df9e95fb21e141a44ac55340db60ac8e4d6d7c2` | Multi-server chatbot that lists and uses tools, resources, and prompts |
| `research_server.py` | `examples/adding_prompt_resource_features/research_server.py` | `5a1e5445462c1ef3ed5d40b3cafb7e95c4acc6e9035c025816fe486d3c3827f7` | Research tools, resources, and prompt template |
| `server_config.json` | `examples/connecting_reference_servers/server_config.json` | `45ed8b28150f35d18cb01b256448e8d8145576b2cee49f9e62eadd1123565f47` | Research, Fetch, and File System stdio startup settings |
| `main.py` | Removed during cleanup on 2026-11-23 | Not applicable | uv scaffold without MCP behavior; course origin unverified |

Original files were moved without modification. `course_examples/` was renamed `examples/` on 2026-11-23; the hashes remain valid and can be checked with `shasum -a 256`.

## Integration map

The web UI, HTTP service, SSE events, and JSON run records are project additions. `src/mcp_demo/web/server.py` serves the active `src/mcp_demo/web/index.html`, `app.js`, and `style.css`. The earlier frontend was moved to the ignored local `.cache/retired-web-v1/` backup and is not served. The writing workflow in `src/mcp_demo/workflows/essay_writer.py` takes its planning, research, drafting, review, follow-up research, and revision concepts from the “Lesson 6: Essay Writer” nodes in `examples/langraph.ipynb`. This integration uses arXiv MCP tools rather than Tavily, allows the model to skip tool calls, supports early review approval, and records when the revision limit is reached. It runs direct Python code without LangGraph, OpenAI, or a SQLite checkpointer. The CLI retains normal chat and its tool loop. The notebook's course origin is unconfirmed.

| Integrated file | Source | Preserved behavior | Adaptation |
| --- | --- | --- | --- |
| `src/mcp_demo/client/mcp_chatbot.py` | Original chatbot | Interactive chat, tool loop, `@` resources, `/prompt` | Separate manager and LLM; include complete assistant tool-use messages; add `--check-config` |
| `src/mcp_demo/client/mcp_client_manager.py` | Original connection methods | Multi-server stdio discovery and routing | Index resource templates, detect name conflicts, expand project paths and the current Python executable, restrict File System scope |
| `src/mcp_demo/client/llm_client.py` | Original Anthropic calls | Messages API, model name, and tool passing | Centralize provider calls and allow an `ANTHROPIC_MODEL` override |
| `src/mcp_demo/workflows/essay_writer.py` | Notebook Essay Writer nodes | Planning, research, drafting, review, follow-up research, revision | Use Research MCP arXiv tools when selected by the model in a direct Python flow |
| `src/mcp_demo/servers/research_server.py` | Original Research Server | Search and extract tools, paper resources, search prompt | Store UTF-8 data in `data/papers/`, handle empty data, sanitize Windows-invalid folder characters |
| `config/mcp_servers.json` | Original server config | Three stdio server definitions | Expand absolute project paths, start Research with the current Python executable, confine File System to `data/` |

`uv.lock` pins `mcp==1.7.1`. `pyproject.toml` limits the SDK to `<2` for compatibility with the v1 API.

## Unavailable course material

- The source lesson for `examples/langraph.ipynb` and any other notebooks has not been confirmed.
- Original `creating_remote_servers/` code, SSE Server or Client examples, and remote endpoint configuration are unavailable.
- Course sample data for `data/papers/` is unavailable; searches create data in the initially empty directory.

Only confirmed compatible stdio examples are integrated. Remote transport behavior has not been inferred.
