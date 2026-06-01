#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from typing import Any
from urllib.parse import quote_plus

from common import (
    ensure_project_dirs,
    SEARCH_DIR,
    WATCHLISTS_DIR,
    day_stamp,
    load_channel_watchlist,
    load_previous_query_results,
    load_yaml,
    normalize_video_record,
    iso_to_datetime,
    now_utc,
    now_iso,
    run_command,
    safe_int,
    sleep_ms,
    time_slug,
    write_json,
    write_jsonl,
)


YT_DLP = shutil.which("yt-dlp") or "yt-dlp"
SEARCH_PROVIDERS = ["ytsearch", "ytsearchdate", "youtube_url", "cache"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search YouTube by topics and watchlist channels.")
    parser.add_argument("--query", action="append", default=[], help="Repeatable search query")
    parser.add_argument("--topics-file", default=str(WATCHLISTS_DIR / "topics.yaml"))
    parser.add_argument("--channels-file", default=str(WATCHLISTS_DIR / "channels.yaml"))
    parser.add_argument("--limit-per-query", type=int, default=8)
    parser.add_argument("--limit-per-channel", type=int, default=6)
    parser.add_argument("--skip-watchlist-channels", action="store_true")
    parser.add_argument("--search-provider", choices=SEARCH_PROVIDERS, default="ytsearch")
    parser.add_argument("--fallback-provider", action="append", choices=SEARCH_PROVIDERS, default=[])
    parser.add_argument("--retry-count", type=int, default=2)
    parser.add_argument("--retry-backoff-ms", type=int, default=2500)
    parser.add_argument("--command-timeout-sec", type=float, default=4.0)
    parser.add_argument("--sleep-between-queries-ms", type=int, default=1800)
    parser.add_argument("--sleep-between-channels-ms", type=int, default=1200)
    parser.add_argument("--continue-on-search-error", action="store_true")
    parser.add_argument("--max-age-days", type=int, help="Keep only videos published within this many days when publication date is known")
    parser.add_argument("--fresh-only", action="store_true", help="Shortcut for --max-age-days 7")
    parser.add_argument("--min-views", type=int, default=0, help="Keep only videos with at least this many views")
    parser.add_argument("--min-comments", type=int, default=0, help="Keep only videos with at least this many comments")
    return parser.parse_args()


def fetch_search_entries_yt_dlp(provider: str, query: str, limit: int, timeout_sec: float) -> list[dict[str, Any]]:
    result = run_command([
        YT_DLP,
        "--dump-single-json",
        "--skip-download",
        f"{provider}{limit}:{query}",
    ], timeout_sec=timeout_sec)
    payload = json.loads(result.stdout)
    return payload.get("entries") or []


def fetch_search_entries_url(query: str, limit: int, timeout_sec: float) -> list[dict[str, Any]]:
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp=EgIQAQ%253D%253D"
    flat = run_command([
        YT_DLP,
        "--flat-playlist",
        "--playlist-end",
        str(limit),
        "--dump-single-json",
        url,
    ], timeout_sec=timeout_sec)
    payload = json.loads(flat.stdout)
    entries = payload.get("entries") or []
    urls = [f"https://www.youtube.com/watch?v={item['id']}" for item in entries if item.get("id")]
    if not urls:
        return []
    enriched = run_command([YT_DLP, "--dump-json", "--skip-download", *urls], timeout_sec=timeout_sec)
    rows: list[dict[str, Any]] = []
    for line in enriched.stdout.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def fetch_query_with_fallbacks(
    query: str,
    limit: int,
    providers: list[str],
    retry_count: int,
    retry_backoff_ms: int,
    timeout_sec: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for provider in providers:
        if provider == "cache":
            cached = load_previous_query_results(query, limit=limit)
            if cached:
                print(
                    f"[yt-search] query='{query}' provider=cache hit entries={len(cached)}",
                    file=sys.stderr,
                    flush=True,
                )
            attempts.append({
                "provider": provider,
                "status": "ok" if cached else "empty",
                "entries": len(cached),
                "error": None,
            })
            if cached:
                return cached, {"provider": provider, "attempts": attempts, "used_fallback": provider != providers[0]}
            continue

        for attempt_no in range(1, retry_count + 2):
            try:
                if provider == "youtube_url":
                    rows = fetch_search_entries_url(query, limit, timeout_sec)
                else:
                    rows = fetch_search_entries_yt_dlp(provider, query, limit, timeout_sec)
                print(
                    f"[yt-search] query='{query}' provider={provider} status={'ok' if rows else 'empty'} entries={len(rows)}",
                    file=sys.stderr,
                    flush=True,
                )
                attempts.append({
                    "provider": provider,
                    "status": "ok" if rows else "empty",
                    "entries": len(rows),
                    "attempt": attempt_no,
                    "error": None,
                })
                if rows:
                    return rows, {"provider": provider, "attempts": attempts, "used_fallback": provider != providers[0]}
                break
            except subprocess.TimeoutExpired:
                print(
                    f"[yt-search] query='{query}' provider={provider} status=timeout after={timeout_sec}s -> fallback",
                    file=sys.stderr,
                    flush=True,
                )
                attempts.append({
                    "provider": provider,
                    "status": "timeout",
                    "entries": 0,
                    "attempt": attempt_no,
                    "error": f"timeout>{timeout_sec}s",
                })
                # Timeout on entry search should fail fast into the next fallback,
                # not spend more wall-clock time retrying a stuck provider.
                break
            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or exc.stdout or str(exc)).strip()
                print(
                    f"[yt-search] query='{query}' provider={provider} status=error",
                    file=sys.stderr,
                    flush=True,
                )
                attempts.append({
                    "provider": provider,
                    "status": "error",
                    "entries": 0,
                    "attempt": attempt_no,
                    "error": stderr[-500:],
                })
                if attempt_no <= retry_count:
                    sleep_ms(retry_backoff_ms * attempt_no)
                else:
                    break
    return [], {"provider": None, "attempts": attempts, "used_fallback": False}


def fetch_channel_entries(channel_url: str, limit: int, timeout_sec: float) -> list[dict[str, Any]]:
    flat = run_command([
        YT_DLP,
        "--flat-playlist",
        "--playlist-end",
        str(limit),
        "--dump-single-json",
        channel_url,
    ], timeout_sec=timeout_sec)
    payload = json.loads(flat.stdout)
    entries = payload.get("entries") or []
    urls = [f"https://www.youtube.com/watch?v={item['id']}" for item in entries if item.get("id")]
    if not urls:
        return []
    enriched = run_command([YT_DLP, "--dump-json", "--skip-download", *urls], timeout_sec=timeout_sec)
    rows: list[dict[str, Any]] = []
    for line in enriched.stdout.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_queries(args: argparse.Namespace) -> list[str]:
    queries = list(args.query)
    if not queries:
        topics = load_yaml(args.topics_file).get("topics") or []
        queries.extend(str(item).strip() for item in topics if str(item).strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        key = query.lower().strip()
        if key and key not in seen:
            deduped.append(query)
            seen.add(key)
    return deduped


def passes_video_filters(record: dict[str, Any], *, max_age_days: int | None = None, min_views: int = 0, min_comments: int = 0) -> bool:
    if safe_int(record.get("views")) < min_views:
        return False
    if safe_int(record.get("comments_count")) < min_comments:
        return False
    if max_age_days is not None:
        published = iso_to_datetime(record.get("published_at"))
        if published is None:
            return False
        if published.tzinfo is None:
            published = published.replace(tzinfo=now_utc().tzinfo)
        age_days = max((now_utc() - published).days, 0)
        if age_days > max_age_days:
            return False
    return True


def aggregate_channels(videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for row in videos:
        key = (row.get("channel_name") or "", row.get("channel_url") or "")
        if key not in buckets:
            buckets[key] = {
                "channel_name": row.get("channel_name"),
                "channel_url": row.get("channel_url"),
                "video_count": 0,
                "queries": set(),
                "total_views": 0,
                "sample_titles": [],
            }
        bucket = buckets[key]
        bucket["video_count"] += 1
        if row.get("query"):
            bucket["queries"].add(row["query"])
        bucket["total_views"] += int(row.get("views") or 0)
        if row.get("title") and len(bucket["sample_titles"]) < 3:
            bucket["sample_titles"].append(row["title"])
    derived = []
    for item in buckets.values():
        item["queries"] = sorted(item["queries"])
        derived.append(item)
    derived.sort(key=lambda x: (x["video_count"], x["total_views"]), reverse=True)
    return derived


def main() -> None:
    ensure_project_dirs()
    args = parse_args()
    queries = load_queries(args)
    max_age_days = 7 if args.fresh_only else args.max_age_days
    watchlist_channels = [] if args.skip_watchlist_channels else load_channel_watchlist(args.channels_file)
    provider_chain = [args.search_provider, *[item for item in args.fallback_provider if item != args.search_provider]]
    if "cache" not in provider_chain:
        provider_chain.append("cache")

    run_at = now_iso()
    day_dir = SEARCH_DIR / day_stamp()
    day_dir.mkdir(parents=True, exist_ok=True)
    stamp = time_slug()

    videos: list[dict[str, Any]] = []
    channel_runs: list[dict[str, Any]] = []
    query_runs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    search_errors = 0

    for index, query in enumerate(queries, start=1):
        print(
            f"[yt-search] start query {index}/{len(queries)}: {query}",
            file=sys.stderr,
            flush=True,
        )
        rows, meta = fetch_query_with_fallbacks(
            query=query,
            limit=args.limit_per_query,
            providers=provider_chain,
            retry_count=args.retry_count,
            retry_backoff_ms=args.retry_backoff_ms,
            timeout_sec=args.command_timeout_sec,
        )
        query_runs.append({
            "query": query,
            "provider_chain": provider_chain,
            "selected_provider": meta.get("provider"),
            "used_fallback": meta.get("used_fallback"),
            "entries": len(rows),
            "timeout_sec": args.command_timeout_sec,
            "attempts": meta.get("attempts") or [],
        })

        if not rows:
            search_errors += 1
            if not args.continue_on_search_error and search_errors >= 1:
                break
        for raw in rows:
            record = normalize_video_record(
                raw,
                source="search_query",
                query=query,
                collected_at=run_at,
                source_provider=meta.get("provider") or "none",
            )
            key = record.get("video_id") or record.get("video_url")
            if key and key not in seen_ids and passes_video_filters(
                record,
                max_age_days=max_age_days,
                min_views=args.min_views,
                min_comments=args.min_comments,
            ):
                videos.append(record)
                seen_ids.add(key)
        if index < len(queries) and meta.get("provider") not in {"cache", None}:
            sleep_ms(args.sleep_between_queries_ms)

    for index, channel in enumerate(watchlist_channels, start=1):
        print(
            f"[yt-search] start watchlist {index}/{len(watchlist_channels)}: {channel['name']}",
            file=sys.stderr,
            flush=True,
        )
        try:
            entries = fetch_channel_entries(channel["url"], args.limit_per_channel, args.command_timeout_sec)
            channel_runs.append({
                "layer": channel["layer"],
                "name": channel["name"],
                "url": channel["url"],
                "fetched_videos": len(entries),
                "status": "ok",
            })
            print(
                f"[yt-search] watchlist='{channel['name']}' status=ok entries={len(entries)}",
                file=sys.stderr,
                flush=True,
            )
        except subprocess.TimeoutExpired:
            entries = []
            channel_runs.append({
                "layer": channel["layer"],
                "name": channel["name"],
                "url": channel["url"],
                "fetched_videos": 0,
                "status": "timeout",
                "error": f"timeout>{args.command_timeout_sec}s",
            })
            print(
                f"[yt-search] watchlist='{channel['name']}' status=timeout after={args.command_timeout_sec}s",
                file=sys.stderr,
                flush=True,
            )
        except subprocess.CalledProcessError as exc:
            entries = []
            channel_runs.append({
                "layer": channel["layer"],
                "name": channel["name"],
                "url": channel["url"],
                "fetched_videos": 0,
                "status": "error",
                "error": ((exc.stderr or exc.stdout or str(exc)).strip())[-500:],
            })
            print(
                f"[yt-search] watchlist='{channel['name']}' status=error",
                file=sys.stderr,
                flush=True,
            )
        for raw in entries:
            record = normalize_video_record(
                raw,
                source="watchlist_channel",
                query=channel["name"],
                collected_at=run_at,
                source_provider="channel_watchlist",
            )
            record["watchlist_layer"] = channel["layer"]
            record["watchlist_tags"] = channel.get("tags") or []
            key = record.get("video_id") or record.get("video_url")
            if key and key not in seen_ids and passes_video_filters(
                record,
                max_age_days=max_age_days,
                min_views=args.min_views,
                min_comments=args.min_comments,
            ):
                videos.append(record)
                seen_ids.add(key)
        if index < len(watchlist_channels):
            sleep_ms(args.sleep_between_channels_ms)

    derived_channels = aggregate_channels(videos)
    bundle = {
        "run_at": run_at,
        "queries": queries,
        "query_runs": query_runs,
        "watchlist_channel_runs": channel_runs,
        "videos_count": len(videos),
        "derived_channels_count": len(derived_channels),
        "search_provider": args.search_provider,
        "filters": {
            "max_age_days": max_age_days,
            "min_views": args.min_views,
            "min_comments": args.min_comments,
        },
        "notes": [
            "v1.1 search uses provider fallback plus cached-query rescue path",
            "entry search now fails fast on stuck yt-dlp calls and records timeout markers",
            "collector schema keeps collected_at, source, source_provider and normalized video fields",
            "this favors weekly reliability over one-shot maximal throughput",
        ],
        "videos": videos,
        "derived_channels": derived_channels,
    }

    bundle_path = day_dir / f"search-{stamp}.json"
    videos_path = day_dir / f"search-{stamp}.videos.jsonl"
    channels_path = day_dir / f"search-{stamp}.channels.json"

    write_json(bundle_path, bundle)
    write_jsonl(videos_path, videos)
    write_json(channels_path, derived_channels)

    print(json.dumps({
        "bundle_path": str(bundle_path),
        "videos_path": str(videos_path),
        "channels_path": str(channels_path),
        "videos_count": len(videos),
        "derived_channels_count": len(derived_channels),
        "queries": queries,
        "watchlist_channels": len(watchlist_channels),
        "query_runs": query_runs,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
