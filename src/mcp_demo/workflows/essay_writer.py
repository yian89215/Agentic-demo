"""Essay workflow adapted from examples/langraph.ipynb.

The course graph uses Tavily. This project uses its existing arXiv MCP server,
so research here is academic-paper research rather than general web search.
"""

from __future__ import annotations

import ast
import asyncio
import json
import re
from time import perf_counter
from typing import Any, Callable, TypedDict

from mcp_demo.client.llm_client import LLMClient
from mcp_demo.client.mcp_client_manager import MCPClientManager

Emit = Callable[[str, str, Any, Any, float | None, str | None], None]


class EssayState(TypedDict):
    task: str
    plan: str
    draft: str
    critique: str
    content: list[dict[str, str]]
    revision_number: int
    max_revisions: int


PLAN_PROMPT = (
    "You are an expert essay planner. Make a useful outline for the topic. "
    "Include a thesis, section notes, and what evidence is needed. "
    "Interpret 'X to Y' as transforming X into Y unless the user says otherwise. "
    "Follow the user's language and requested format."
)
QUERY_PROMPT = (
    "You are an academic researcher. Decide whether arXiv papers would help this "
    "writing task. Return JSON only: {\"use_tools\": true or false, "
    "\"queries\": [one or two short English arXiv search queries]}. "
    "Set use_tools to false when papers would not help, such as a personal or "
    "creative piece. Keep the topic's core concept in every query."
)
WRITER_PROMPT = (
    "You are an essay writer. Write a coherent essay following the outline and "
    "the user's requested language, length, and style. Use the research notes only "
    "where relevant. Cite a paper with its arXiv URL when making a sourced claim. "
    "Never invent sources, citations, facts, or search results. If research is "
    "missing, do not claim the essay is source-backed."
)
REFLECTION_PROMPT = (
    "You are an essay editor. Review the draft against the user's topic. "
    "Return JSON only: {\"decision\": \"approve\" or \"revise\", "
    "\"reason\": \"one sentence explaining the decision\", "
    "\"feedback\": \"specific actionable comments\"}. Approve when the draft "
    "meets the request. Do not rewrite the essay."
)


def _json_object(raw: str) -> dict[str, Any] | None:
    try:
        value = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        return value if isinstance(value, dict) else None
    except (ValueError, TypeError):
        return None


def _text_blocks(result: Any) -> str:
    return "\n".join(
        str(getattr(block, "text", "")) for block in getattr(result, "content", [])
        if getattr(block, "text", None) is not None
    )


def _paper_ids(result: Any) -> list[str]:
    raw = _text_blocks(result).strip()
    for parser in (json.loads, ast.literal_eval):
        try:
            value = parser(raw)
            if isinstance(value, list):
                return [str(item) for item in value if isinstance(item, str)][:3]
        except (ValueError, SyntaxError, TypeError):
            pass
    return re.findall(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b", raw)[:3]


def _queries(raw: str, fallback: str) -> list[str]:
    raw = raw.strip().replace('\\"', '"')
    candidate = raw[raw.find("["):] if "[" in raw else raw
    values: Any = []
    try:
        values, _ = json.JSONDecoder().raw_decode(candidate)
    except (ValueError, TypeError):
        first_line = candidate.splitlines()[0]
        try:
            values = ast.literal_eval(first_line)
        except (ValueError, SyntaxError, TypeError):
            pass
    topic_words = re.findall(r"[a-zA-Z]{3,}", fallback.split(":", 1)[0].lower())
    core = next((word for word in topic_words if word not in {
        "the", "and", "for", "from", "with", "how", "what", "why", "write",
        "essay", "about", "please", "using", "into",
    }), None)
    queries = []
    if isinstance(values, list):
        items = [nested for item in values for nested in (item if isinstance(item, list) else [item])]
        for item in items:
            query = item.get("query") if isinstance(item, dict) else item
            if not isinstance(query, str):
                continue
            query = query.strip()[:120]
            if query and (core is None or re.search(rf"\b{re.escape(core)}\b", query.lower())):
                queries.append(query)
    safe_fallback = fallback.split(":", 1)[0].strip()[:80] or fallback[:80]
    return list(dict.fromkeys(queries or [safe_fallback]))[:2]


def _source_relevant(topic: str, source: dict[str, str]) -> bool:
    """Reject papers that omit the topic's primary English concept entirely."""
    words = re.findall(r"[a-zA-Z]{3,}", topic.split(":", 1)[0].lower())
    core = next((word for word in words if word not in {
        "the", "and", "for", "from", "with", "how", "what", "why", "write",
        "essay", "about", "please", "using", "into",
    }), None)
    if core is None:
        return True
    haystack = f"{source['title']} {source['summary']}".lower()
    return re.search(rf"\b{re.escape(core)}\b", haystack) is not None


class EssayWriter:
    def __init__(self, manager: MCPClientManager, llm: LLMClient, emit: Emit) -> None:
        self.manager = manager
        self.llm = llm
        self.emit = emit

    async def _model(self, node: str, system: str, prompt: str, tokens: int = 3072) -> str:
        input_value = {"system": system, "prompt": prompt}
        self.emit(node, "start", input_value, None, None, None)
        started = perf_counter()
        try:
            output = await asyncio.to_thread(self.llm.create_text, system, prompt, tokens)
            if not output.strip():
                raise RuntimeError(f"{node} returned empty text")
        except Exception as exc:
            self.emit(node, "error", input_value, str(exc), perf_counter() - started, None)
            raise
        self.emit(node, "complete", input_value, output, perf_counter() - started, None)
        return output

    async def _research(self, node: str, task: str, state: EssayState) -> None:
        self.emit(node, "start", {"topic": state["task"], "focus": task}, None, None, None)
        started = perf_counter()
        query_prompt = task if node == "research_plan" else (
            f"Original topic: {state['task']}\nEditor feedback to investigate: {task}"
        )
        raw_queries = await self._model("queries", QUERY_PROMPT, query_prompt, 300)
        decision = _json_object(raw_queries)
        use_tools = decision.get("use_tools", True) is not False if decision else True
        queries = _queries(json.dumps(decision.get("queries", [])), state["task"]) if decision and use_tools else (
            _queries(raw_queries, state["task"]) if use_tools else []
        )
        new_sources: list[dict[str, str]] = []
        warnings: list[str] = []
        seen = {source["id"] for source in state["content"]}
        for query in queries:
            tool_input = {"tool": "search_papers", "arguments": {"topic": query, "max_results": 2}}
            self.emit("research", "start", tool_input, None, None, query)
            tool_started = perf_counter()
            try:
                result = await self.manager.call_tool("search_papers", tool_input["arguments"])
                if getattr(result, "isError", False):
                    raise RuntimeError(_text_blocks(result))
                ids = _paper_ids(result)
                self.emit("research", "complete", tool_input, {"paper_ids": ids},
                          perf_counter() - tool_started, query)
            except Exception as exc:
                warning = f"Search failed for '{query}': {exc}"
                warnings.append(warning)
                self.emit("research", "error", tool_input, warning,
                          perf_counter() - tool_started, query)
                continue
            for paper_id in ids:
                if paper_id in seen:
                    continue
                seen.add(paper_id)
                info_input = {"tool": "extract_info", "arguments": {"paper_id": paper_id}}
                self.emit("research", "start", info_input, None, None, paper_id)
                info_started = perf_counter()
                try:
                    info = await self.manager.call_tool("extract_info", {"paper_id": paper_id})
                    if getattr(info, "isError", False):
                        raise RuntimeError(_text_blocks(info))
                    data = json.loads(_text_blocks(info))
                    source = {
                        "id": paper_id,
                        "title": str(data["title"]),
                        "summary": str(data["summary"])[:1800],
                        "url": str(data.get("pdf_url", f"https://arxiv.org/abs/{paper_id}")),
                    }
                    if not _source_relevant(state["task"], source):
                        warning = f"Skipped unrelated paper {paper_id}: {source['title']}"
                        warnings.append(warning)
                        self.emit("research", "complete", info_input, {"skipped": warning},
                                  perf_counter() - info_started, paper_id)
                        continue
                    new_sources.append(source)
                    self.emit("research", "complete", info_input, source,
                              perf_counter() - info_started, paper_id)
                except (KeyError, ValueError, TypeError, RuntimeError) as exc:
                    warning = f"Could not read paper {paper_id}: {exc}"
                    warnings.append(warning)
                    self.emit("research", "error", info_input, warning,
                              perf_counter() - info_started, paper_id)
        state["content"].extend(new_sources)
        self.emit(node, "complete", {"topic": task, "queries": queries},
                  {"sources": new_sources, "warnings": warnings, "tool_decision": "use" if use_tools else "skip"},
                  perf_counter() - started, None)

    async def run(self, topic: str, max_revisions: int = 1) -> EssayState:
        state: EssayState = {
            "task": topic, "plan": "", "draft": "", "critique": "",
            "content": [], "revision_number": 0, "max_revisions": max_revisions,
        }
        state["plan"] = await self._model("planner", PLAN_PROMPT, topic, 900)
        await self._research("research_plan", topic, state)
        while True:
            notes = json.dumps(state["content"], ensure_ascii=False)
            prompt = (
                f"Topic and instructions:\n{topic}\n\nOutline:\n{state['plan']}\n\n"
                f"Research notes:\n{notes or 'No sources found.'}\n\n"
                f"Previous draft:\n{state['draft']}\n\nEditor feedback:\n{state['critique']}"
            )
            state["draft"] = await self._model("generate", WRITER_PROMPT, prompt)
            if max_revisions == 0:
                self.emit("gate", "complete", {"completed_revisions": 0, "max_revisions": 0},
                          {"route": "answer", "reason": "revision_limit", "reviewed_version": 0}, 0.0, None)
                break
            raw_review = await self._model(
                "reflect", REFLECTION_PROMPT,
                f"Topic: {topic}\n\nDraft:\n{state['draft']}", 900,
            )
            review = _json_object(raw_review)
            wants_revision = review.get("decision") != "approve" if review else True
            state["critique"] = str(review.get("feedback") or review.get("reason") or raw_review) if review else raw_review
            at_limit = state["revision_number"] >= max_revisions
            reason = "revision_limit" if wants_revision and at_limit else "approved" if not wants_revision else "needs_revision"
            route = "answer" if at_limit or not wants_revision else "research_critique"
            self.emit("gate", "complete", {"completed_revisions": state["revision_number"],
                                            "max_revisions": max_revisions},
                      {"route": route, "reason": reason,
                       "reviewed_version": state["revision_number"],
                       "summary": str(review.get("reason", "")) if review else raw_review}, 0.0, None)
            if route == "answer":
                break
            await self._research("research_critique", state["critique"], state)
            state["revision_number"] += 1
        self.emit("answer", "complete", {"revisions": state["revision_number"],
                                          "sources": state["content"]},
                  state["draft"], 0.0, None)
        return state
