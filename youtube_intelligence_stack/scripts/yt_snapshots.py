#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from common import (
    ensure_project_dirs,
    SNAPSHOTS_DIR,
    TRANSCRIPTS_DIR,
    WATCHLISTS_DIR,
    day_stamp,
    load_channel_watchlist,
    normalize_video_record,
    now_iso,
    resolve_video_inputs,
    run_command,
    time_slug,
    write_json,
    write_jsonl,
    append_jsonl,
)


YT_DLP = shutil.which("yt-dlp") or "yt-dlp"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture YouTube public metric snapshots.")
    parser.add_argument("--video-id", action="append", default=[])
    parser.add_argument("--video-url", action="append", default=[])
    parser.add_argument("--from-search", help="Search bundle json path, defaults to latest search bundle")
    parser.add_argument("--channels-file", default=str(WATCHLISTS_DIR / "channels.yaml"))
    parser.add_argument("--include-watchlist-channels", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--limit-per-channel", type=int, default=5)
    return parser.parse_args()


def fetch_metadata_batch(urls: list[str]) -> list[dict[str, Any]]:
    if not urls:
        return []
    result = run_command([YT_DLP, "--dump-json", "--skip-download", *urls])
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def fetch_channel_video_urls(channel_url: str, limit: int) -> list[str]:
    result = run_command([
        YT_DLP,
        "--flat-playlist",
        "--playlist-end",
        str(limit),
        "--dump-single-json",
        channel_url,
    ])
    payload = json.loads(result.stdout)
    return [f"https://www.youtube.com/watch?v={item['id']}" for item in (payload.get("entries") or []) if item.get("id")]


def transcript_exists(video_id: str | None) -> bool:
    if not video_id:
        return False
    return (TRANSCRIPTS_DIR / video_id / "latest.json").exists()


def main() -> None:
    ensure_project_dirs()
    args = parse_args()
    inputs = resolve_video_inputs(
        video_ids=args.video_id,
        video_urls=args.video_url,
        from_search=args.from_search,
        limit=args.limit,
    )
    urls = [item["video_url"] for item in inputs if item.get("video_url")]

    if args.include_watchlist_channels:
        for channel in load_channel_watchlist(args.channels_file):
            urls.extend(fetch_channel_video_urls(channel["url"], args.limit_per_channel))

    deduped_urls: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            deduped_urls.append(url)
            seen.add(url)

    captured_at = now_iso()
    rows = []
    for raw in fetch_metadata_batch(deduped_urls):
        base = normalize_video_record(raw, source="snapshot", query=None)
        row = {
            "captured_at": captured_at,
            "video_id": base.get("video_id"),
            "title": base.get("title"),
            "channel_name": base.get("channel_name"),
            "views": base.get("views"),
            "comments_count": base.get("comments_count"),
            "duration": base.get("duration"),
            "published_at": base.get("published_at"),
            "transcript_available": transcript_exists(base.get("video_id")) or bool(raw.get("subtitles") or raw.get("automatic_captions")),
            "query": base.get("query"),
            "source": raw.get("webpage_url") or base.get("video_url"),
            "video_url": base.get("video_url"),
        }
        rows.append(row)

    day_dir = SNAPSHOTS_DIR / day_stamp()
    day_dir.mkdir(parents=True, exist_ok=True)
    stamp = time_slug()
    run_path = day_dir / f"snapshots-{stamp}.jsonl"
    summary_path = day_dir / f"snapshots-{stamp}.json"
    history_path = SNAPSHOTS_DIR / "history.jsonl"

    write_jsonl(run_path, rows)
    append_jsonl(history_path, rows)
    write_json(summary_path, {
        "captured_at": captured_at,
        "count": len(rows),
        "run_path": str(run_path),
        "history_path": str(history_path),
    })

    print(json.dumps({
        "captured_at": captured_at,
        "count": len(rows),
        "run_path": str(run_path),
        "history_path": str(history_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
