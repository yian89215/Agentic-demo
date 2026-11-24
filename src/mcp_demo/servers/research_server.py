"""Course Research Server with tools, resources, and a prompt template."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List

import arxiv
from mcp.server.fastmcp import FastMCP


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PAPER_DIR = Path(os.getenv("PAPERS_DIR", PROJECT_ROOT / "data" / "papers")).resolve()
mcp = FastMCP("research")


def _topic_directory(topic: str) -> Path:
    slug = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", topic.lower().replace(" ", "_"))
    slug = slug.strip(" ._")[:100] or "topic"
    if slug.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                        *(f"LPT{i}" for i in range(1, 10))}:
        slug = f"topic_{slug}"
    return PAPER_DIR / slug


@mcp.tool()
def search_papers(topic: str, max_results: int = 5) -> List[str]:
    """Search arXiv by topic and save paper metadata in the project data directory."""
    client = arxiv.Client()
    search = arxiv.Search(
        query=topic,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )
    topic_path = _topic_directory(topic)
    topic_path.mkdir(parents=True, exist_ok=True)
    file_path = topic_path / "papers_info.json"

    try:
        with file_path.open(encoding="utf-8") as json_file:
            papers_info = json.load(json_file)
    except (FileNotFoundError, json.JSONDecodeError):
        papers_info = {}

    paper_ids: list[str] = []
    for paper in client.results(search):
        paper_id = paper.get_short_id()
        paper_ids.append(paper_id)
        papers_info[paper_id] = {
            "title": paper.title,
            "authors": [author.name for author in paper.authors],
            "summary": paper.summary,
            "pdf_url": paper.pdf_url,
            "published": str(paper.published.date()),
        }

    with file_path.open("w", encoding="utf-8") as json_file:
        json.dump(papers_info, json_file, indent=2, ensure_ascii=False)
    print(f"Results are saved in: {file_path}")
    return paper_ids


@mcp.tool()
def extract_info(paper_id: str) -> str:
    """Find a paper ID among all saved topics."""
    if not PAPER_DIR.exists():
        return f"There's no saved information related to paper {paper_id}."
    for item_path in PAPER_DIR.iterdir():
        file_path = item_path / "papers_info.json"
        if not item_path.is_dir() or not file_path.is_file():
            continue
        try:
            with file_path.open(encoding="utf-8") as json_file:
                papers_info = json.load(json_file)
            if paper_id in papers_info:
                return json.dumps(papers_info[paper_id], indent=2, ensure_ascii=False)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Error reading {file_path}: {exc}")
    return f"There's no saved information related to paper {paper_id}."


@mcp.resource("papers://folders")
def get_available_folders() -> str:
    """List research topics containing a papers_info.json file."""
    folders = []
    if PAPER_DIR.exists():
        folders = sorted(
            path.name
            for path in PAPER_DIR.iterdir()
            if path.is_dir() and (path / "papers_info.json").exists()
        )
    content = "# Available Topics\n\n"
    if not folders:
        return content + "No topics found.\n"
    content += "".join(f"- {folder}\n" for folder in folders)
    return content + "\nUse @<topic> to access papers in that topic.\n"


@mcp.resource("papers://{topic}")
def get_topic_papers(topic: str) -> str:
    """Get saved paper information for a research topic."""
    papers_file = _topic_directory(topic) / "papers_info.json"
    if not papers_file.exists():
        return f"# No papers found for topic: {topic}\n\nTry searching for papers on this topic first."
    try:
        with papers_file.open(encoding="utf-8") as file:
            papers_data = json.load(file)
    except json.JSONDecodeError:
        return f"# Error reading papers data for {topic}\n\nThe papers data file is corrupted."

    content = f"# Papers on {topic.replace('_', ' ').title()}\n\n"
    content += f"Total papers: {len(papers_data)}\n\n"
    for paper_id, paper_info in papers_data.items():
        content += f"## {paper_info['title']}\n"
        content += f"- **Paper ID**: {paper_id}\n"
        content += f"- **Authors**: {', '.join(paper_info['authors'])}\n"
        content += f"- **Published**: {paper_info['published']}\n"
        content += f"- **PDF URL**: [{paper_info['pdf_url']}]({paper_info['pdf_url']})\n\n"
        content += f"### Summary\n{paper_info['summary'][:500]}...\n\n---\n\n"
    return content


@mcp.prompt()
def generate_search_prompt(topic: str, num_papers: int = 5) -> str:
    """Generate a prompt for searching and organizing papers with Research tools."""
    return f"""Search for {num_papers} academic papers about '{topic}' using the search_papers tool.

Follow these instructions:
1. First, search for papers using search_papers(topic='{topic}', max_results={num_papers})
2. For each paper found, extract and organize the following information:
   - Paper title
   - Authors
   - Publication date
   - Brief summary of the key findings
   - Main contributions or innovations
   - Methodologies used
   - Relevance to the topic '{topic}'

3. Provide a comprehensive summary that includes:
   - Overview of the current state of research in '{topic}'
   - Common themes and trends across the papers
   - Key research gaps or areas for future investigation
   - Most impactful or influential papers in this area

4. Organize your findings in a clear, structured format with headings and bullet points for easy readability.

Please present both detailed information about each paper and a high-level synthesis of the research landscape in {topic}."""


if __name__ == "__main__":
    mcp.run(transport="stdio")
