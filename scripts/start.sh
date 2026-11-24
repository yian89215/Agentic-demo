#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

# Keep tool caches in .cache/; the corresponding environment variables can override these paths.
export UV_CACHE_DIR="${UV_CACHE_DIR:-$project_dir/.cache/uv}"
export npm_config_cache="${npm_config_cache:-$project_dir/.cache/npm}"

# This Windows workspace has a local uv installation.
if [[ -x "$project_dir/.uv-bootstrap/bin/uv.exe" ]]; then
    export PATH="$project_dir/.uv-bootstrap/bin:$PATH"
fi
if [[ -x "$project_dir/.cache/uv-tool/bin/uv.exe" ]]; then
    export PATH="$project_dir/.cache/uv-tool/bin:$PATH"
fi

if ! command -v uv >/dev/null 2>&1 || ! command -v uvx >/dev/null 2>&1; then
    echo "uv/uvx not found. Install uv or keep .uv-bootstrap/bin in this project." >&2
    exit 1
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
    echo "Node.js and npx are required for the filesystem MCP server." >&2
    exit 1
fi

# Start the local Ollama server when the Windows app is not already running.
if command -v curl >/dev/null 2>&1 && ! curl -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
    if ! command -v cygpath >/dev/null 2>&1 || [[ -z "${LOCALAPPDATA:-}" ]]; then
        echo "Ollama is not running. Start the Ollama app and retry." >&2
        exit 1
    fi
    ollama_exe="$(cygpath -u "$LOCALAPPDATA")/Programs/Ollama/ollama.exe"
    if [[ ! -x "$ollama_exe" ]]; then
        echo "Ollama executable not found: $ollama_exe" >&2
        exit 1
    fi
    "$ollama_exe" serve >/dev/null 2>&1 &
    for ((attempt = 0; attempt < 30; attempt++)); do
        if curl -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    if ! curl -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
        echo "Ollama did not start within 30 seconds." >&2
        exit 1
    fi
fi

uv sync --frozen
if [[ "${1:-}" == "--web" ]]; then
    shift
    exec uv run --frozen mcp-demo-web "$@"
fi
exec uv run --frozen mcp-demo "$@"
