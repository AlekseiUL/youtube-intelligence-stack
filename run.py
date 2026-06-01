#!/usr/bin/env python3
from __future__ import annotations

import sys

from youtube_intelligence_stack.cli import main as cli_main

LEGACY_MAP = {"init-instance": "init"}


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] in LEGACY_MAP:
        argv[0] = LEGACY_MAP[argv[0]]
    if argv and argv[0] in {"init", "search", "transcripts", "comments", "snapshots", "report", "full"}:
        # Legacy syntax: run.py <command> --project-root PATH [args]
        if "--project-root" in argv:
            idx = argv.index("--project-root")
            if idx + 1 < len(argv):
                project = argv[idx + 1]
                argv = [argv[0], project, *argv[1:idx], *argv[idx + 2:]]
    cli_main(argv)


if __name__ == "__main__":
    main()
