from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .core import SCRIPT_MAP, doctor, ensure_instance, run_layer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="youtube-intel",
        description="Local-first YouTube intelligence pipeline for public-source research.",
    )
    parser.add_argument("--version", action="version", version=f"youtube-intel {__version__}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("doctor", help="Check Python, yt-dlp, and optional project instance readiness.")
    p.add_argument("project_root", nargs="?", type=Path)
    p.add_argument("--json", action="store_true", dest="as_json")

    p = sub.add_parser("init", help="Create a clean research instance.")
    p.add_argument("project_root", type=Path)
    p.add_argument("--force", action="store_true")
    p.add_argument("--template", default="general", choices=["general", "creator", "competitor", "ai-tools"])

    for name in ["search", "transcripts", "comments", "snapshots", "report"]:
        p = sub.add_parser(name, help=f"Run the {name} layer.")
        p.add_argument("project_root", type=Path)
        p.add_argument("args", nargs=argparse.REMAINDER)

    p = sub.add_parser("full", help="Run search, transcripts, comments, snapshots, then report.")
    p.add_argument("project_root", type=Path)
    p.add_argument("args", nargs=argparse.REMAINDER, help="Extra args passed to the search layer. Use --safe for conservative timeouts and degraded-run behavior.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return

    if args.command == "doctor":
        payload = doctor(args.project_root)
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"python: {'ok' if payload['python']['ok'] else 'fail'} {payload['python']['version']}")
            print(f"yt-dlp: {'ok' if payload['yt_dlp']['ok'] else 'missing'} {payload['yt_dlp']['path'] or ''}".rstrip())
            if payload["project_root"]:
                root = payload["project_root"]
                print(f"project: {root['path']}")
                print(f"watchlists: topics={root['topics']} channels={root['channels']}")
            print(f"overall: {'ok' if payload['ok'] else 'fail'}")
        raise SystemExit(0 if payload["ok"] else 1)

    if args.command == "init":
        ensure_instance(args.project_root, force=args.force, template=args.template)
        print(str(args.project_root.resolve()))
        return

    if args.command == "full":
        safe_mode = "--safe" in args.args
        search_args = [item for item in args.args if item != "--safe"]
        if safe_mode:
            if "--command-timeout-sec" not in search_args:
                search_args.extend(["--command-timeout-sec", "30"])
            if "--continue-on-search-error" not in search_args:
                search_args.append("--continue-on-search-error")
        run_layer("search", args.project_root, search_args)
        if safe_mode:
            run_layer("transcripts", args.project_root, ["--limit", "5", "--command-timeout-sec", "30", "--retry-count", "1"])
            run_layer("comments", args.project_root, ["--limit", "5", "--command-timeout-sec", "30", "--retry-count", "1"])
            run_layer("snapshots", args.project_root, ["--limit", "5", "--command-timeout-sec", "30"])
        else:
            run_layer("transcripts", args.project_root, [])
            run_layer("comments", args.project_root, [])
            run_layer("snapshots", args.project_root, [])
        run_layer("report", args.project_root, [])
        return

    if args.command in SCRIPT_MAP:
        run_layer(args.command, args.project_root, args.args)
        return

    raise SystemExit(f"Unknown command: {args.command}")
