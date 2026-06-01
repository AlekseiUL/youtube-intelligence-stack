from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = PACKAGE_ROOT / "scripts"
TEMPLATES_DIR = PACKAGE_ROOT / "templates" / "watchlists"

DEFAULT_TOPICS = textwrap.dedent(
    """
    topics:
      - AI agents
      - workflow automation
      - productivity tools
      - creator economy
      - marketing automation
      - no-code automation
      - startup operations
      - customer support automation
      - knowledge management
      - platform risk
    """
).strip() + "\n"

TEMPLATE_TOPICS = {
    "general": [
        "AI agents",
        "workflow automation",
        "productivity tools",
        "creator economy",
        "marketing automation",
        "no-code automation",
        "startup operations",
        "customer support automation",
        "knowledge management",
        "platform risk",
    ],
    "creator": [
        "content hooks",
        "audience pain points",
        "viral tutorial formats",
        "creator workflow automation",
        "YouTube growth tactics",
        "community questions",
        "content repurposing",
        "trend analysis",
    ],
    "competitor": [
        "alternative to",
        "platform risk",
        "switching from",
        "competitor comparison",
        "pricing complaints",
        "migration guide",
        "vendor lock-in",
        "customer complaints",
    ],
    "ai-tools": [
        "AI agents",
        "agent memory",
        "MCP tools",
        "AI workflow automation",
        "multi-agent systems",
        "AI coding tools",
        "LLM orchestration",
        "agent reliability",
    ],
}


def render_topics(template: str = "general") -> str:
    topics = TEMPLATE_TOPICS.get(template, TEMPLATE_TOPICS["general"])
    return "topics:\n" + "".join(f"  - {topic}\n" for topic in topics)


DEFAULT_CHANNELS = textwrap.dedent(
    """
    direct:
      # - name: Example primary channel
      #   url: https://www.youtube.com/@example
      #   enabled: true
      #   tags: [primary, niche]

    adjacent:
      # - name: Example adjacent channel
      #   url: https://www.youtube.com/@example-adjacent
      #   enabled: true
      #   tags: [adjacent, market]

    global_signal:
      # - name: Example global signal channel
      #   url: https://www.youtube.com/@example-global
      #   enabled: true
      #   tags: [market, signals]
    """
).strip() + "\n"

DEFAULT_INSTANCE_README = textwrap.dedent(
    """
    # YouTube Intelligence Instance

    This is a local research instance for YouTube Intelligence Stack.

    ## Edit here
    - `watchlists/topics.yaml`
    - `watchlists/channels.yaml`

    ## Run full stack

    ```bash
    youtube-intel full {project_root}
    ```
    """
)

DEFAULT_BRIEFING = textwrap.dedent(
    """
    # Briefing - YouTube Intelligence Instance

    ## Purpose
    Use this project as a local intelligence instance backed by YouTube Intelligence Stack.

    ## What to configure
    - topics in `watchlists/topics.yaml`
    - channels in `watchlists/channels.yaml`

    ## Outputs
    - search results in `data/search/`
    - transcripts in `data/transcripts/`
    - comments in `data/comments/`
    - snapshots in `data/snapshots/`
    - weekly reports in `data/reports/`
    """
).strip() + "\n"

DEFAULT_STATUS = textwrap.dedent(
    """
    # Status - YouTube Intelligence Instance

    ## Current step
    Initialized as a project instance for YouTube Intelligence Stack.

    ## Next steps
    - fill `watchlists/topics.yaml`
    - fill `watchlists/channels.yaml`
    - run `youtube-intel full <this-project>`
    """
).strip() + "\n"

SCRIPT_MAP = {
    "search": "yt_search.py",
    "transcripts": "yt_transcripts.py",
    "comments": "yt_comments.py",
    "snapshots": "yt_snapshots.py",
    "report": "build_weekly_report.py",
}


def ensure_instance(project_root: Path, force: bool = False, template: str = "general") -> None:
    project_root = project_root.resolve()
    for rel in [
        "watchlists",
        "data/search",
        "data/transcripts",
        "data/comments",
        "data/snapshots",
        "data/reports",
        "examples",
        "result",
    ]:
        (project_root / rel).mkdir(parents=True, exist_ok=True)

    files = {
        "watchlists/topics.yaml": render_topics(template),
        "watchlists/channels.yaml": DEFAULT_CHANNELS,
        "README.md": DEFAULT_INSTANCE_README.format(project_root=project_root).strip() + "\n",
        "briefing.md": DEFAULT_BRIEFING,
        "status.md": DEFAULT_STATUS,
    }
    for rel, content in files.items():
        path = project_root / rel
        if force or not path.exists():
            path.write_text(content, encoding="utf-8")


def run_layer(command: str, project_root: Path, extra_args: list[str]) -> None:
    if command not in SCRIPT_MAP:
        raise SystemExit(f"Unknown layer: {command}")
    env = os.environ.copy()
    env["YOUTUBE_INTEL_PROJECT_ROOT"] = str(project_root.resolve())
    script = SCRIPTS_DIR / SCRIPT_MAP[command]
    subprocess.run([sys.executable, str(script), *extra_args], check=True, env=env)


def doctor(project_root: Path | None = None) -> dict:
    py_ok = sys.version_info >= (3, 10)
    ytdlp_path = shutil.which("yt-dlp")
    root_info = None
    if project_root:
        root = project_root.resolve()
        root_info = {
            "path": str(root),
            "exists": root.exists(),
            "topics": (root / "watchlists" / "topics.yaml").exists(),
            "channels": (root / "watchlists" / "channels.yaml").exists(),
            "writable": os.access(root if root.exists() else root.parent, os.W_OK),
        }
    project_ok = True
    if root_info is not None:
        project_ok = bool(root_info["exists"] and root_info["topics"] and root_info["channels"] and root_info["writable"])
    result = {
        "ok": bool(py_ok and ytdlp_path and project_ok),
        "python": {"ok": py_ok, "version": sys.version.split()[0]},
        "yt_dlp": {"ok": bool(ytdlp_path), "path": ytdlp_path},
        "project_root": root_info,
    }
    return result
