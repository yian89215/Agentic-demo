"""Behavioral checks for the fixed essay workflow."""

import asyncio
import json
import unittest
from types import SimpleNamespace

from mcp_demo.workflows.essay_writer import EssayWriter, _queries, _source_relevant
from mcp_demo.servers.research_server import _topic_directory


class FakeLLM:
    def __init__(self, approve_after=1, use_tools=True):
        self.reviews = 0
        self.approve_after = approve_after
        self.use_tools = use_tools

    def create_text(self, system, prompt, max_tokens):
        if "essay planner" in system:
            return "1. Introduce the topic\n2. Explain the evidence\n3. Conclude"
        if "academic researcher" in system:
            return json.dumps({"use_tools": self.use_tools,
                               "queries": ["cough sound music generation"]})
        if "essay editor" in system:
            self.reviews += 1
            decision = "approve" if self.reviews > self.approve_after else "revise"
            return json.dumps({"decision": decision, "reason": "Check source support",
                               "feedback": "Add a clearer conclusion and cite the paper."})
        return "An essay with a cited source: https://arxiv.org/abs/2501.12345"


class FakeManager:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "search_papers":
            text = "['2501.12345']"
        else:
            text = json.dumps({"title": "Cough to Music", "summary": "A useful abstract",
                               "pdf_url": "https://arxiv.org/abs/2501.12345"})
        return SimpleNamespace(content=[SimpleNamespace(text=text)], isError=False)


class EssayWriterTests(unittest.TestCase):
    def test_search_queries_and_windows_folder_name(self):
        self.assertEqual(_queries('[\\"cough to music\\"]', 'Cough to music: write an essay'),
                         ['cough to music'])
        self.assertEqual(_queries('[{"query":"music generation"},{"query":"cough sound sonification"}]',
                                  'Cough to Music: write an essay'), ['cough sound sonification'])
        self.assertEqual(_queries("['cough audio research']", 'Cough to Music'),
                         ['cough audio research'])
        self.assertEqual(_queries('[["cough sound generation", "music theory"]]',
                                  'Cough to Music'), ['cough sound generation'])
        self.assertEqual(_topic_directory('Cough to music: write an essay').name,
                         'cough_to_music__write_an_essay')
        self.assertFalse(_source_relevant('Cough to Music',
                         {'title': 'Music performance', 'summary': 'Generative instruments'}))
        self.assertTrue(_source_relevant('Cough to Music',
                        {'title': 'Cough sound sonification', 'summary': 'Audio conversion'}))

    def test_topic_always_triggers_research_and_revision(self):
        manager = FakeManager()
        events = []
        writer = EssayWriter(manager, FakeLLM(), lambda *event: events.append(event))
        state = asyncio.run(writer.run("Cough to Music", max_revisions=1))
        self.assertEqual(state["revision_number"], 1)
        self.assertEqual(len(state["content"]), 1)
        self.assertTrue(any(name == "search_papers" for name, _ in manager.calls))
        self.assertTrue(any(name == "extract_info" for name, _ in manager.calls))
        self.assertEqual([event[0] for event in events if event[0] == "generate" and event[1] == "complete"],
                         ["generate", "generate"])
        self.assertEqual([event[3]["route"] for event in events if event[0] == "gate"],
                         ["research_critique", "answer"])
        self.assertEqual([event[3]["reason"] for event in events if event[0] == "gate"],
                         ["needs_revision", "approved"])
        self.assertEqual(events[-1][0:2], ("answer", "complete"))

    def test_review_can_approve_first_draft_and_research_can_skip_tools(self):
        manager = FakeManager()
        events = []
        writer = EssayWriter(manager, FakeLLM(approve_after=0, use_tools=False),
                             lambda *event: events.append(event))
        state = asyncio.run(writer.run("Cough to Music", max_revisions=2))
        self.assertEqual(state["revision_number"], 0)
        self.assertEqual(manager.calls, [])
        self.assertEqual([event[3]["reason"] for event in events if event[0] == "gate"],
                         ["approved"])

    def test_revision_limit_is_distinct_from_approval(self):
        events = []
        writer = EssayWriter(FakeManager(), FakeLLM(approve_after=9),
                             lambda *event: events.append(event))
        state = asyncio.run(writer.run("Cough to Music", max_revisions=1))
        self.assertEqual(state["revision_number"], 1)
        self.assertEqual([event[3]["reason"] for event in events if event[0] == "gate"],
                         ["needs_revision", "revision_limit"])

    def test_zero_limit_produces_only_first_draft(self):
        events = []
        writer = EssayWriter(FakeManager(), FakeLLM(), lambda *event: events.append(event))
        state = asyncio.run(writer.run("Cough to Music", max_revisions=0))
        self.assertEqual(state["revision_number"], 0)
        self.assertEqual(len([event for event in events if event[0] == "generate" and
                              event[1] == "complete"]), 1)
        self.assertFalse(any(event[0] == "reflect" for event in events))
        self.assertEqual(next(event[3]["reason"] for event in events if event[0] == "gate"),
                         "revision_limit")


if __name__ == "__main__":
    unittest.main()
