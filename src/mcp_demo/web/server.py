"""Local web UI and event stream for the existing MCP chatbot."""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from dotenv import load_dotenv

from mcp_demo.client.mcp_chatbot import DEFAULT_CONFIG, PROJECT_ROOT
from mcp_demo.client.mcp_client_manager import MCPClientManager
from mcp_demo.client.llm_client import LLMClient
from mcp_demo.workflows.essay_writer import EssayWriter


STATIC_DIR = Path(__file__).resolve().parent
RUNS: dict[str, "Run"] = {}
RUNS_LOCK = threading.Lock()


def json_safe(value: object) -> object:
    """Turn SDK objects into plain JSON without losing their visible fields."""
    if hasattr(value, "model_dump"):
        return json_safe(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "__dict__"):
        return json_safe(vars(value))
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class Run:
    def __init__(self, query: str, max_revisions: int = 1) -> None:
        self.id = uuid4().hex
        self.query = query
        self.max_revisions = max_revisions
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.events: list[dict[str, object]] = []
        self.done = False
        self.condition = threading.Condition()

    def emit(
        self,
        node: str,
        status: str,
        input_value: object = None,
        output: object = None,
        duration: float | None = None,
        invocation_id: str | None = None,
    ) -> None:
        with self.condition:
            self.events.append({
                "seq": len(self.events),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "node": node,
                "status": status,
                "invocation_id": invocation_id,
                "input": json_safe(input_value),
                "output": json_safe(output),
                "duration_ms": round(duration * 1000, 1) if duration is not None else None,
            })
            self.condition.notify_all()

    def finish(self) -> None:
        with self.condition:
            self.done = True
            self.condition.notify_all()

    def snapshot(self) -> dict[str, object]:
        with self.condition:
            return {"version": 1, "id": self.id, "query": self.query,
                    "max_revisions": self.max_revisions,
                    "created_at": self.created_at, "events": list(self.events)}


async def execute(run: Run, config: Path) -> None:
    manager = MCPClientManager(config)
    try:
        run.emit("user", "complete", run.query, run.query, 0.0)
        run.emit("connection", "start", {"server": "research", "config": str(config)})
        from time import perf_counter
        started = perf_counter()
        try:
            servers = manager.load_config()
            if "research" not in servers:
                raise ValueError("Web Essay Writer requires the research MCP server")
            await manager.connect("research", servers["research"])
        except Exception as exc:
            run.emit("connection", "error", None, str(exc), perf_counter() - started)
            raise
        run.emit("connection", "complete", None,
                 {"servers": ["research"]}, perf_counter() - started)
        await EssayWriter(manager, LLMClient(), run.emit).run(run.query, run.max_revisions)
    except Exception as exc:
        run.emit("run", "error", None, str(exc))
    finally:
        try:
            await manager.close()
        except Exception as exc:
            run.emit("connection", "error", None, f"Cleanup: {exc}")
        run.finish()


class Handler(BaseHTTPRequestHandler):
    config_path = DEFAULT_CONFIG

    def respond(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, code: int, payload: object) -> None:
        self.respond(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")

    def do_POST(self) -> None:
        if self.path != "/api/runs":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 16384:
                raise ValueError("Request body must be 1–16384 bytes")
            payload = json.loads(self.rfile.read(length))
            query = payload.get("query", "")
            if not isinstance(query, str) or not query.strip():
                raise ValueError("Enter an essay topic")
            max_revisions = payload.get("max_revisions", 1)
            if type(max_revisions) is not int or not 0 <= max_revisions <= 2:
                raise ValueError("max_revisions must be an integer from 0 to 2")
        except (ValueError, json.JSONDecodeError, AttributeError) as exc:
            self.send_json(400, {"error": str(exc)})
            return
        run = Run(query.strip(), max_revisions)
        with RUNS_LOCK:
            RUNS[run.id] = run
        threading.Thread(target=lambda: asyncio.run(execute(run, self.config_path)),
                         daemon=True).start()
        self.send_json(201, {"id": run.id})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/runs/"):
            parts = path.split("/")
            if len(parts) != 5 or parts[4] not in {"events", "download"}:
                self.send_error(404)
                return
            with RUNS_LOCK:
                run = RUNS.get(parts[3])
            if run is None:
                self.send_error(404)
                return
            if parts[4] == "download":
                data = json.dumps(run.snapshot(), ensure_ascii=False, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="mcp-run-{run.id[:8]}.json"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.stream(run)
            return
        filename = "index.html" if path == "/" else path.lstrip("/")
        if filename not in {"index.html", "app.js", "style.css"}:
            self.send_error(404)
            return
        file_path = STATIC_DIR / filename
        self.respond(200, file_path.read_bytes(), mimetypes.guess_type(filename)[0] or "text/plain")

    def stream(self, run: Run) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            index = max(0, int(self.headers.get("Last-Event-ID", "-1")) + 1)
            while True:
                with run.condition:
                    if index >= len(run.events) and not run.done:
                        run.condition.wait(timeout=15)
                    batch = run.events[index:]
                    done = run.done
                for event in batch:
                    body = json.dumps(event, ensure_ascii=False)
                    self.wfile.write(f"id: {event['seq']}\ndata: {body}\n\n".encode("utf-8"))
                    index += 1
                if done:
                    self.wfile.write(b"event: done\ndata: {}\n\n")
                    self.wfile.flush()
                    break
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP workflow web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    MCPClientManager(args.config).load_config()
    Handler.config_path = args.config
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"MCP web UI: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
