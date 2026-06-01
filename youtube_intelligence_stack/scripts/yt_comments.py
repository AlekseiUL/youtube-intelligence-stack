#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from common import ensure_project_dirs, COMMENTS_DIR, now_iso, resolve_video_inputs, run_command, sleep_ms, write_json, write_jsonl


YT_DLP = shutil.which("yt-dlp") or "yt-dlp"
SORT_ALIASES = {
    "top": "top",
    "new": "new",
    "recent": "new",
}
DEFAULT_SORTS = ["top", "recent"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch YouTube comments via yt-dlp infojson.")
    parser.add_argument("--video-id", action="append", default=[])
    parser.add_argument("--video-url", action="append", default=[])
    parser.add_argument("--from-search", help="Search bundle json path, defaults to latest search bundle")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--sort", action="append", choices=["top", "new", "recent"], default=[])
    parser.add_argument("--command-timeout-sec", type=float, default=8.0)
    parser.add_argument("--retry-count", type=int, default=1)
    parser.add_argument("--retry-backoff-ms", type=int, default=2500)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def normalize_sort_modes(raw_modes: list[str]) -> list[str]:
    modes = raw_modes or DEFAULT_SORTS
    result: list[str] = []
    seen: set[str] = set()
    for mode in modes:
        key = mode.strip().lower()
        if key and key not in seen:
            result.append(key)
            seen.add(key)
    return result


def fetch_comments(url: str, sort_mode: str, timeout_sec: float) -> dict[str, Any]:
    extractor_sort = SORT_ALIASES[sort_mode]
    with tempfile.TemporaryDirectory(prefix="yt-comments-") as tmpdir:
        out_template = str(Path(tmpdir) / "%(id)s.%(ext)s")
        run_command([
            YT_DLP,
            "--skip-download",
            "--write-info-json",
            "--write-comments",
            "--extractor-args",
            f"youtube:comment_sort={extractor_sort}",
            "-o",
            out_template,
            url,
        ], timeout_sec=timeout_sec)
        info_files = sorted(Path(tmpdir).glob("*.info.json"))
        if not info_files:
            return {}
        return json.loads(info_files[0].read_text(encoding="utf-8"))


def fetch_comments_with_retries(
    url: str,
    sort_mode: str,
    timeout_sec: float,
    *,
    retry_count: int,
    retry_backoff_ms: int,
) -> tuple[dict[str, Any], str | None]:
    last_error: str | None = None
    for attempt_no in range(1, retry_count + 2):
        try:
            return fetch_comments(url, sort_mode, timeout_sec), None
        except Exception as exc:
            last_error = str(exc)
            if attempt_no <= retry_count:
                sleep_ms(retry_backoff_ms * attempt_no)
            else:
                break
    return {}, last_error


def get_thread_fields(comment_id: str | None, parent: str | None) -> tuple[str | None, str | None, bool]:
    parent = (parent or "").strip()
    if not parent or parent == "root":
        return comment_id, None, False
    thread_id = parent.split(".")[0]
    return thread_id, parent, True


def normalize_comments(payload: dict[str, Any], sort_mode: str, collected_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload.get("comments") or []:
        comment_id = item.get("id")
        thread_id, parent_comment_id, is_reply = get_thread_fields(comment_id, item.get("parent"))
        rows.append({
            "video_id": payload.get("id"),
            "comment_id": comment_id,
            "thread_id": thread_id,
            "parent_comment_id": parent_comment_id,
            "is_reply": is_reply,
            "author": item.get("author") or item.get("author_id") or "unknown",
            "author_id": item.get("author_id"),
            "author_url": item.get("author_url"),
            "author_is_uploader": bool(item.get("author_is_uploader")),
            "text": item.get("text") or item.get("html") or "",
            "likes": item.get("like_count") or 0,
            "published_at": item.get("timestamp") or item.get("time_text"),
            "reply_count": item.get("reply_count") or 0,
            "sort_mode": sort_mode,
            "collected_at": collected_at,
        })
    return rows


def merge_comment_rows(rows_by_sort: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for sort_mode, rows in rows_by_sort.items():
        for row in rows:
            key = row.get("comment_id")
            if not key:
                continue
            if key not in merged:
                base = dict(row)
                base["sort_modes"] = [sort_mode]
                merged[key] = base
                continue
            target = merged[key]
            if sort_mode not in target["sort_modes"]:
                target["sort_modes"].append(sort_mode)
            target["likes"] = max(int(target.get("likes") or 0), int(row.get("likes") or 0))
            target["reply_count"] = max(int(target.get("reply_count") or 0), int(row.get("reply_count") or 0))
            if not target.get("text") and row.get("text"):
                target["text"] = row.get("text")
            if not target.get("published_at") and row.get("published_at"):
                target["published_at"] = row.get("published_at")
    merged_rows = list(merged.values())
    merged_rows.sort(key=lambda item: (bool(item.get("is_reply")), -(int(item.get("likes") or 0))))
    return merged_rows


def write_sort_files(out_dir: Path, rows_by_sort: dict[str, list[dict[str, Any]]]) -> None:
    for sort_mode, rows in rows_by_sort.items():
        write_jsonl(out_dir / f"latest.{sort_mode}.jsonl", rows)


def main() -> None:
    ensure_project_dirs()
    args = parse_args()
    sort_modes = normalize_sort_modes(args.sort)
    inputs = resolve_video_inputs(
        video_ids=args.video_id,
        video_urls=args.video_url,
        from_search=args.from_search,
        limit=args.limit,
    )

    summary: list[dict[str, Any]] = []
    for item in inputs:
        url = item.get("video_url")
        if not url:
            continue

        video_id = item.get("video_id")
        out_dir = COMMENTS_DIR / (video_id or "unknown")
        latest_meta = out_dir / "latest.meta.json"
        latest_jsonl = out_dir / "latest.jsonl"
        if latest_meta.exists() and latest_jsonl.exists() and not args.overwrite:
            meta = json.loads(latest_meta.read_text(encoding="utf-8"))
            summary.append(meta)
            continue

        collected_at = now_iso()
        payloads: dict[str, dict[str, Any]] = {}
        rows_by_sort: dict[str, list[dict[str, Any]]] = {}
        errors: dict[str, str] = {}

        for sort_mode in sort_modes:
            print(
                f"[yt-comments] video='{video_id or url}' sort={sort_mode} start",
                file=sys.stderr,
                flush=True,
            )
            try:
                payload, retry_error = fetch_comments_with_retries(
                    url,
                    sort_mode,
                    args.command_timeout_sec,
                    retry_count=args.retry_count,
                    retry_backoff_ms=args.retry_backoff_ms,
                )
                if retry_error:
                    errors[sort_mode] = retry_error
                payloads[sort_mode] = payload
                rows_by_sort[sort_mode] = normalize_comments(payload, sort_mode, collected_at) if payload else []
                print(
                    f"[yt-comments] video='{video_id or url}' sort={sort_mode} status={'ok' if payload else 'empty'} rows={len(rows_by_sort[sort_mode])}",
                    file=sys.stderr,
                    flush=True,
                )
            except subprocess.TimeoutExpired:
                errors[sort_mode] = f"timeout>{args.command_timeout_sec}s"
                rows_by_sort[sort_mode] = []
                print(
                    f"[yt-comments] video='{video_id or url}' sort={sort_mode} status=timeout after={args.command_timeout_sec}s",
                    file=sys.stderr,
                    flush=True,
                )
            except Exception as exc:
                errors[sort_mode] = str(exc)
                rows_by_sort[sort_mode] = []
                print(
                    f"[yt-comments] video='{video_id or url}' sort={sort_mode} status=error",
                    file=sys.stderr,
                    flush=True,
                )

        payload = next((value for value in payloads.values() if value), {})
        if not payload:
            status = "missing_infojson"
            if errors and all(str(value).startswith("timeout>") for value in errors.values()):
                status = "timeout"
            elif errors:
                status = "error"
            meta = {
                "fetched_at": collected_at,
                "collected_at": collected_at,
                "video_id": video_id,
                "video_url": url,
                "comments_count": 0,
                "sort_modes": sort_modes,
                "status": status,
                "errors": errors,
                "source": "yt_dlp_comments",
            }
            out_dir.mkdir(parents=True, exist_ok=True)
            write_json(latest_meta, meta)
            summary.append(meta)
            continue

        video_id = payload.get("id") or video_id or "unknown"
        out_dir = COMMENTS_DIR / video_id
        out_dir.mkdir(parents=True, exist_ok=True)

        merged_rows = merge_comment_rows(rows_by_sort)
        thread_roots_count = sum(1 for row in merged_rows if not row.get("is_reply"))
        reply_rows_count = sum(1 for row in merged_rows if row.get("is_reply"))
        meta = {
            "fetched_at": collected_at,
            "collected_at": collected_at,
            "video_id": video_id,
            "video_url": payload.get("webpage_url") or url,
            "title": payload.get("title"),
            "channel_name": payload.get("channel") or payload.get("uploader"),
            "channel_url": payload.get("channel_url") or payload.get("uploader_url"),
            "comments_count": len(merged_rows),
            "thread_roots_count": thread_roots_count,
            "reply_rows_count": reply_rows_count,
            "sort_modes": sort_modes,
            "per_sort_counts": {sort_mode: len(rows) for sort_mode, rows in rows_by_sort.items()},
            "status": "ok" if merged_rows else "empty",
            "errors": errors,
            "source": "yt_dlp_comments",
        }
        write_sort_files(out_dir, rows_by_sort)
        write_jsonl(out_dir / "latest.jsonl", merged_rows)
        write_json(out_dir / "latest.meta.json", meta)
        summary.append(meta)

    print(json.dumps({
        "processed": len(summary),
        "with_comments": sum(1 for item in summary if item.get("comments_count", 0) > 0),
        "sort_modes": sort_modes,
        "items": summary,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
