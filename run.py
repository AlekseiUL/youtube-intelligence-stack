#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import textwrap
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = TOOL_ROOT / "scripts"
TOOL_PATH_DISPLAY = str(TOOL_ROOT)

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
    From the cloned `youtube-intelligence-stack` repository, run:

    ```bash
    python3 run.py full --project-root /path/to/this-instance
    ```
    """
)

DEFAULT_BRIEFING = textwrap.dedent(
    """
    # Briefing - YouTube Intelligence Instance

    ## Purpose
    Use this project as a local intelligence instance backed by the shared YouTube Intelligence Stack.

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

    ## Текущий шаг
    Инициализирован как project instance для shared YouTube Intelligence Stack.

    ## Что сделать
    - заполнить `watchlists/topics.yaml`
    - заполнить `watchlists/channels.yaml`
    - прогнать `run.py full --project-root <this-project>`
    """
).strip() + "\n"

SCRIPT_MAP = {
    "search": "yt_search.py",
    "transcripts": "yt_transcripts.py",
    "comments": "yt_comments.py",
    "snapshots": "yt_snapshots.py",
    "report": "build_weekly_report.py",
}


def parse_global(argv: list[str]):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", nargs="?")
    parser.add_argument("--project-root")
    known, remainder = parser.parse_known_args(argv)
    return known, remainder


def ensure_instance(project_root: Path, force: bool = False) -> None:
    for rel in [
        "watchlists",
        "data/search",
        "data/transcripts",
        "data/comments",
        "data/snapshots",
        "data/reports",
        "examples",
        "result",
        "scripts",
    ]:
        (project_root / rel).mkdir(parents=True, exist_ok=True)

    files = {
        "watchlists/topics.yaml": DEFAULT_TOPICS,
        "watchlists/channels.yaml": DEFAULT_CHANNELS,
        "README.md": DEFAULT_INSTANCE_README.format(
            project_root=project_root,
            tool_root=TOOL_PATH_DISPLAY,
        ).strip() + "\n",
        "briefing.md": DEFAULT_BRIEFING,
        "status.md": DEFAULT_STATUS,
    }
    for rel, content in files.items():
        path = project_root / rel
        if force or not path.exists():
            path.write_text(content, encoding="utf-8")


def run_layer(command: str, project_root: Path, extra_args: list[str]) -> None:
    env = os.environ.copy()
    env["YOUTUBE_INTEL_PROJECT_ROOT"] = str(project_root)
    script = SCRIPTS_DIR / SCRIPT_MAP[command]
    subprocess.run([sys.executable, str(script), *extra_args], check=True, env=env)


def main() -> None:
    known, remainder = parse_global(sys.argv[1:])
    command = known.command
    project_root = Path(known.project_root).resolve() if known.project_root else Path.cwd().resolve()

    if command in (None, "-h", "--help"):
        print("Usage: run.py <init-instance|search|transcripts|comments|snapshots|report|full> [--project-root PATH] [extra args]")
        return

    if command == "init-instance":
        parser = argparse.ArgumentParser()
        parser.add_argument("command")
        parser.add_argument("--project-root", required=True)
        parser.add_argument("--force", action="store_true")
        args = parser.parse_args(sys.argv[1:])
        target = Path(args.project_root).resolve()
        ensure_instance(target, force=args.force)
        print(str(target))
        return

    if command == "full":
        run_layer("search", project_root, remainder)
        run_layer("transcripts", project_root, [])
        run_layer("comments", project_root, [])
        run_layer("snapshots", project_root, [])
        run_layer("report", project_root, [])
        return

    if command not in SCRIPT_MAP:
        raise SystemExit(f"Unknown command: {command}")

    run_layer(command, project_root, remainder)


if __name__ == "__main__":
    main()
