#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

from common import (
    ensure_project_dirs,
    COMMENTS_DIR,
    REPORTS_DIR,
    SEARCH_DIR,
    SNAPSHOTS_DIR,
    TRANSCRIPTS_DIR,
    TARGET_KEYWORDS,
    day_stamp,
    iso_to_datetime,
    keyword_overlap_score,
    load_snapshot_history,
    now_utc,
    read_json,
    read_jsonl,
    safe_int,
    time_slug,
    write_text,
)


PAIN_PATTERNS = {
    "rate limits and quotas": ["rate limit", "quota", "usage cap", "token cap", "limit hit"],
    "pricing pressure": ["too expensive", "pricing", "cost", "credits", "subscription", "expensive"],
    "fragile reliability": ["outage", "downtime", "broken", "stopped working", "buggy", "fails", "unreliable"],
    "memory and context pain": ["memory", "context window", "forgets", "lost context", "context limit"],
    "setup and complexity": ["hard to set up", "setup", "config", "installation", "too complex", "complexity", "difficult"],
    "speed and latency": ["slow", "latency", "takes forever", "too long", "waiting", "sluggish"],
}

MIGRATION_PATTERNS = [
    "migrat", "switch", "moving from", "replace", "replacing", "left ", "dropped ", "vs ", "instead of",
]

RISK_PATTERNS = [
    "ban", "policy", "copyright", "takedown", "pricing", "rate limit", "quota", "deprec", "sunset", "outage",
    "downtime", "blocked", "compliance", "risk",
]

HOOK_PATTERNS = {
    "comparison / replacement": [" vs ", "replace", "instead of", "better than", "switch"],
    "step-by-step build": ["how to", "build", "tutorial", "guide", "walkthrough"],
    "market map / trend read": ["trend", "future", "landscape", "what changed", "state of"],
    "architecture deep dive": ["architecture", "mcp", "memory", "multi-agent", "agent stack"],
    "live proof / teardown": ["demo", "case study", "teardown", "reaction", "review"],
}

AI_OPS_KEYWORDS = {
    "operations", "workflow", "automation", "team", "telegram", "knowledge", "memory", "agent", "agents",
    "orchestration", "mcp", "monitoring", "handoff", "reporting",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build weekly markdown intelligence report from local YouTube artifacts.")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--out", help="Output markdown path")
    parser.add_argument("--max-age-days", type=int, help="Keep only videos published within this many days when publication date is known")
    parser.add_argument("--fresh-only", action="store_true", help="Shortcut for --max-age-days equal to --days")
    parser.add_argument("--min-views", type=int, default=0)
    parser.add_argument("--min-comments", type=int, default=0)
    return parser.parse_args()


def load_recent_search_data(cutoff):
    rows: list[dict[str, Any]] = []
    query_runs: list[dict[str, Any]] = []
    bundles: list[dict[str, Any]] = []
    for path in sorted(SEARCH_DIR.glob("**/search-*.json")):
        if path.name.endswith(".channels.json") or path.name.endswith(".videos.json"):
            continue
        bundle = read_json(path)
        run_at = iso_to_datetime(bundle.get("run_at"))
        if run_at and run_at >= cutoff:
            rows.extend(bundle.get("videos") or [])
            bundles.append(bundle)
            query_runs.extend(bundle.get("query_runs") or [])
    return rows, query_runs, bundles


def load_recent_comment_sets(cutoff) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for meta_path in sorted(COMMENTS_DIR.glob("*/latest.meta.json")):
        meta = read_json(meta_path)
        fetched_at = iso_to_datetime(meta.get("fetched_at") or meta.get("collected_at"))
        if fetched_at and fetched_at >= cutoff:
            jsonl_path = meta_path.parent / "latest.jsonl"
            items.append({"meta": meta, "rows": read_jsonl(jsonl_path)})
    return items


def load_recent_transcripts(cutoff) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for path in sorted(TRANSCRIPTS_DIR.glob("*/latest.json")):
        payload = read_json(path)
        fetched_at = iso_to_datetime(payload.get("fetched_at") or payload.get("collected_at"))
        if fetched_at and fetched_at >= cutoff:
            items[payload.get("video_id")] = payload
    return items


def report_video_filter_reason(row: dict[str, Any], *, max_age_days: int | None, min_views: int, min_comments: int) -> str | None:
    if safe_int(row.get("views")) < min_views:
        return "removed_by_min_views"
    if safe_int(row.get("comments_count")) < min_comments:
        return "removed_by_min_comments"
    if max_age_days is not None:
        published = iso_to_datetime(row.get("published_at"))
        if not published:
            return "removed_by_missing_publication_date"
        if published.tzinfo is None:
            published = published.replace(tzinfo=now_utc().tzinfo)
        if max((now_utc() - published).days, 0) > max_age_days:
            return "removed_by_age"
    return None


def report_video_passes_filters(row: dict[str, Any], *, max_age_days: int | None, min_views: int, min_comments: int) -> bool:
    return report_video_filter_reason(
        row,
        max_age_days=max_age_days,
        min_views=min_views,
        min_comments=min_comments,
    ) is None


def days_since(value: str | None) -> int | None:
    dt = iso_to_datetime(value)
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=now_utc().tzinfo)
    return max((now_utc() - dt).days, 0)


def freshness_score(published_at: str | None) -> float:
    age = days_since(published_at)
    if age is None:
        return 0.25
    if age <= 7:
        return 1.0
    if age <= 30:
        return 0.82
    if age <= 90:
        return 0.58
    if age <= 180:
        return 0.34
    return 0.18


def signal_intensity_score(views: int, comments: int) -> float:
    raw = math.log10(max(views, 1)) * 0.65 + math.log10(max(comments + 1, 1)) * 0.35
    return min(raw / 5.0, 1.0)


def usefulness_score(item: dict[str, Any]) -> float:
    texts = [
        item.get("title") or "",
        item.get("description_snippet") or "",
        " ".join(item.get("queries") or []),
    ]
    target = keyword_overlap_score(texts, TARGET_KEYWORDS)
    ai_ops = keyword_overlap_score(texts, AI_OPS_KEYWORDS)
    return min((target * 0.7 + ai_ops * 0.3) * 4.0, 1.0)


def topical_relevance_score(item: dict[str, Any]) -> float:
    queries = [item.get("query")] if item.get("query") else list(item.get("queries") or [])
    text = " ".join([item.get("title") or "", item.get("description_snippet") or "", item.get("channel_name") or ""])
    if not queries:
        return keyword_overlap_score([text], TARGET_KEYWORDS) * 3.5
    score = 0.0
    text_l = text.lower()
    for query in queries:
        q = query.lower().strip()
        if q and q in text_l:
            score += 1.0
        else:
            q_tokens = [token for token in q.replace("-", " ").split() if len(token) > 2]
            if q_tokens:
                matches = sum(1 for token in q_tokens if token in text_l)
                score += matches / len(q_tokens)
    return min(score / max(len(queries), 1), 1.0)


def repeatability_score(item: dict[str, Any]) -> float:
    queries = len(item.get("queries") or [])
    hits = safe_int(item.get("search_hits"))
    return min(((queries * 0.5) + (hits * 0.35)) / 3.0, 1.0)


def score_video(base: dict[str, Any]) -> tuple[float, dict[str, float]]:
    components = {
        "topical_relevance": round(topical_relevance_score(base), 3),
        "freshness": round(freshness_score(base.get("published_at")), 3),
        "signal_intensity": round(signal_intensity_score(safe_int(base.get("views")), safe_int(base.get("comments_count"))), 3),
        "repeatability": round(repeatability_score(base), 3),
        "usefulness": round(usefulness_score(base), 3),
    }
    total = (
        components["topical_relevance"] * 0.30
        + components["freshness"] * 0.16
        + components["signal_intensity"] * 0.24
        + components["repeatability"] * 0.12
        + components["usefulness"] * 0.18
    ) * 100
    if base.get("transcript_available"):
        total += 4.0
    return round(total, 2), components


def merge_video_signals(search_rows, snapshots, comment_sets, transcripts):
    videos: dict[str, dict[str, Any]] = {}

    def ensure(video_id: str) -> dict[str, Any]:
        if video_id not in videos:
            videos[video_id] = {
                "video_id": video_id,
                "title": None,
                "video_url": None,
                "channel_name": None,
                "channel_url": None,
                "queries": set(),
                "query": None,
                "search_hits": 0,
                "views": 0,
                "comments_count": 0,
                "published_at": None,
                "duration": None,
                "description_snippet": "",
                "transcript_available": False,
                "source_providers": set(),
                "collected_at": None,
            }
        return videos[video_id]

    for row in search_rows:
        video_id = row.get("video_id")
        if not video_id:
            continue
        item = ensure(video_id)
        item["title"] = item["title"] or row.get("title")
        item["video_url"] = item["video_url"] or row.get("video_url")
        item["channel_name"] = item["channel_name"] or row.get("channel_name")
        item["channel_url"] = item["channel_url"] or row.get("channel_url")
        item["published_at"] = item["published_at"] or row.get("published_at")
        item["duration"] = item["duration"] or row.get("duration")
        item["description_snippet"] = item["description_snippet"] or row.get("description_snippet") or ""
        item["query"] = item["query"] or row.get("query")
        item["collected_at"] = item["collected_at"] or row.get("collected_at")
        if row.get("query"):
            item["queries"].add(row["query"])
        if row.get("source_provider"):
            item["source_providers"].add(row.get("source_provider"))
        item["search_hits"] += 1
        item["views"] = max(item["views"], safe_int(row.get("views")))
        item["comments_count"] = max(item["comments_count"], safe_int(row.get("comments_count")))

    for row in snapshots:
        video_id = row.get("video_id")
        if not video_id:
            continue
        item = ensure(video_id)
        item["title"] = item["title"] or row.get("title")
        item["video_url"] = item["video_url"] or row.get("video_url")
        item["channel_name"] = item["channel_name"] or row.get("channel_name")
        item["published_at"] = item["published_at"] or row.get("published_at")
        item["duration"] = item["duration"] or row.get("duration")
        item["views"] = max(item["views"], safe_int(row.get("views")))
        item["comments_count"] = max(item["comments_count"], safe_int(row.get("comments_count")))
        item["transcript_available"] = item["transcript_available"] or bool(row.get("transcript_available"))

    for entry in comment_sets:
        meta = entry["meta"]
        video_id = meta.get("video_id")
        if not video_id:
            continue
        item = ensure(video_id)
        item["title"] = item["title"] or meta.get("title")
        item["video_url"] = item["video_url"] or meta.get("video_url")
        item["channel_name"] = item["channel_name"] or meta.get("channel_name")
        item["channel_url"] = item["channel_url"] or meta.get("channel_url")
        item["comments_count"] = max(item["comments_count"], safe_int(meta.get("comments_count")))

    for video_id, transcript in transcripts.items():
        if not video_id:
            continue
        item = ensure(video_id)
        item["transcript_available"] = item["transcript_available"] or bool(transcript.get("transcript_available"))

    merged = []
    for item in videos.values():
        item["queries"] = sorted(item["queries"])
        item["source_providers"] = sorted(item["source_providers"])
        signal_score, components = score_video(item)
        item["signal_score"] = signal_score
        item["score_components"] = components
        merged.append(item)
    merged.sort(key=lambda x: x["signal_score"], reverse=True)
    return merged


def extract_pains(comment_sets):
    scores = Counter()
    evidence = defaultdict(list)
    for entry in comment_sets:
        for row in entry["rows"]:
            text = (row.get("text") or "").lower()
            for label, patterns in PAIN_PATTERNS.items():
                if any(pattern in text for pattern in patterns):
                    scores[label] += 1
                    if len(evidence[label]) < 3:
                        evidence[label].append((row.get("video_id"), row.get("text") or ""))
    return [(label, count, evidence[label]) for label, count in scores.most_common(5)]


def extract_migration_signals(videos, comment_sets):
    hits = []
    for row in videos:
        hay = " ".join([row.get("title") or "", row.get("description_snippet") or ""]).lower()
        if any(pattern in hay for pattern in MIGRATION_PATTERNS):
            hits.append({
                "type": "video",
                "video_id": row.get("video_id"),
                "title": row.get("title"),
                "channel_name": row.get("channel_name"),
                "reason": "title/description hints at migration or replacement",
            })
    for entry in comment_sets:
        meta = entry["meta"]
        for row in entry["rows"][:50]:
            text = (row.get("text") or "").lower()
            if any(pattern in text for pattern in MIGRATION_PATTERNS):
                hits.append({
                    "type": "comment",
                    "video_id": meta.get("video_id"),
                    "title": meta.get("title"),
                    "channel_name": meta.get("channel_name"),
                    "reason": clean_snippet(row.get("text") or ""),
                })
                break
    deduped = []
    seen = set()
    for item in hits:
        key = (item.get("video_id"), item.get("type"))
        if key not in seen:
            deduped.append(item)
            seen.add(key)
    return deduped[:8]


def extract_risk_signals(videos, comment_sets):
    hits = []
    for row in videos:
        hay = " ".join([row.get("title") or "", row.get("description_snippet") or ""]).lower()
        if any(pattern in hay for pattern in RISK_PATTERNS):
            hits.append({
                "video_id": row.get("video_id"),
                "title": row.get("title"),
                "channel_name": row.get("channel_name"),
                "reason": "title/description contains platform risk vocabulary",
            })
    for entry in comment_sets:
        meta = entry["meta"]
        for row in entry["rows"][:50]:
            text = (row.get("text") or "").lower()
            if any(pattern in text for pattern in RISK_PATTERNS):
                hits.append({
                    "video_id": meta.get("video_id"),
                    "title": meta.get("title"),
                    "channel_name": meta.get("channel_name"),
                    "reason": clean_snippet(row.get("text") or ""),
                })
                break
    deduped = []
    seen = set()
    for item in hits:
        key = item.get("video_id")
        if key and key not in seen:
            deduped.append(item)
            seen.add(key)
    return deduped[:8]


def extract_hook_patterns(videos):
    counts = Counter()
    evidence = defaultdict(list)
    for row in videos:
        title = (row.get("title") or "").lower()
        for label, patterns in HOOK_PATTERNS.items():
            if any(pattern in title for pattern in patterns):
                counts[label] += 1
                if len(evidence[label]) < 3:
                    evidence[label].append(row.get("title"))
    hooks = []
    for label, count in counts.most_common(5):
        hooks.append({"label": label, "count": count, "examples": evidence[label]})
    return hooks


def build_content_strategy_ideas(pains, migration_signals, hooks):
    ideas = []
    if migration_signals:
        ideas.append("Map migrations between AI stacks: who is switching, why they move, and what that means for builders and operators.")
    if pains:
        label = pains[0][0]
        ideas.append(f"Create a practical content asset around '{label}': show how to avoid that pain and where the market is breaking.")
    if hooks:
        ideas.append(f"Use the '{hooks[0]['label']}', format because the pattern is already attracting audience attention.")
    if not ideas:
        return ["Insufficient evidence: collect more videos/comments before recommending content actions."]
    return list(dict.fromkeys(ideas))[:3]


def build_operations_ideas(pains, risk_signals, hooks):
    ideas = []
    if pains:
        ideas.append(f"Create a practical workflow breakdown around '{pains[0][0]}': show how to solve it with process instead of manual heroics.")
    if risk_signals:
        ideas.append("Create a platform-risk brief: what breaks, where vendor lock-in appears, and how to design fallback chains.")
    if hooks:
        ideas.append(f"Use the '{hooks[0]['label']}' format for education: less abstraction, more operational walkthrough.")
    if not ideas:
        return ["Insufficient evidence: collect more videos/comments before recommending workflow actions."]
    return list(dict.fromkeys(ideas))[:3]


def build_proof_assets(migration_signals, risks, hooks):
    assets = []
    if migration_signals:
        assets.append("Migration Radar: a short Markdown note mapping switches between tools, platforms, workflows, and adjacent stacks.")
    if risks:
        assets.append("Platform Risk Brief: a compact weekly memo about limits, pricing, policy risk, and reliability signals.")
    if hooks and len(assets) < 3:
        assets.append(f"Hook Swipefile: 10 titles and narrative patterns in the '{hooks[0]['label']}', that can be adapted to your context.")
    return assets[:3]


def summarize_search_health(query_runs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(query_runs)
    fallback_hits = sum(1 for item in query_runs if item.get("used_fallback"))
    hard_failures = sum(1 for item in query_runs if not item.get("entries"))
    providers = Counter(item.get("selected_provider") or "none" for item in query_runs)
    return {
        "queries_total": total,
        "fallback_hits": fallback_hits,
        "hard_failures": hard_failures,
        "providers": dict(providers),
    }


def merge_search_filter_accounting(bundles: list[dict[str, Any]], fallback: dict[str, int]) -> dict[str, int]:
    keys = [
        "candidates_before_filters",
        "kept",
        "removed_by_age",
        "removed_by_missing_publication_date",
        "removed_by_min_views",
        "removed_by_min_comments",
    ]
    merged = {key: 0 for key in keys}
    found = False
    for bundle in bundles:
        accounting = bundle.get("filter_accounting") or {}
        if accounting:
            found = True
        for key in keys:
            merged[key] += safe_int(accounting.get(key))
    return merged if found else fallback


def summarize_filter_accounting(videos: list[dict[str, Any]], *, max_age_days: int | None, min_views: int, min_comments: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    accounting = {
        "candidates_before_filters": len(videos),
        "kept": 0,
        "removed_by_age": 0,
        "removed_by_missing_publication_date": 0,
        "removed_by_min_views": 0,
        "removed_by_min_comments": 0,
    }
    kept: list[dict[str, Any]] = []
    for row in videos:
        reason = report_video_filter_reason(
            row,
            max_age_days=max_age_days,
            min_views=min_views,
            min_comments=min_comments,
        )
        if reason:
            accounting[reason] += 1
            continue
        accounting["kept"] += 1
        kept.append(row)
    return kept, accounting


def clean_snippet(text: str, limit: int = 160) -> str:
    text = " ".join((text or "").split())
    return text[: limit - 1] + "…" if len(text) > limit else text


def render_report(*, days: int, generated_at: str, top_videos, pains, migration_signals, risk_signals, hooks, content_strategy_ideas, operations_ideas, proof_assets, search_rows_count, snapshots_count, comment_sets_count, search_health, filter_accounting: dict[str, int] | None = None) -> str:
    filter_accounting = filter_accounting or {
        "candidates_before_filters": search_rows_count,
        "kept": len(top_videos or []),
        "removed_by_age": 0,
        "removed_by_missing_publication_date": 0,
        "removed_by_min_views": 0,
        "removed_by_min_comments": 0,
    }
    lines = []
    lines.append("# YouTube Intelligence Weekly Report\n")
    lines.append(f"- Generated at: {generated_at}")
    lines.append(f"- Lookback window: last {days} days")
    lines.append(f"- Search rows: {search_rows_count}")
    lines.append(f"- Snapshot rows: {snapshots_count}")
    lines.append(f"- Comment sets: {comment_sets_count}")
    lines.append(f"- Search fallback hits: {search_health['fallback_hits']} / {search_health['queries_total']}")
    lines.append(f"- Search hard failures: {search_health['hard_failures']}")
    lines.append("- Filter accounting:")
    lines.append(f"  - Candidates before filters: {filter_accounting.get('candidates_before_filters', 0)}")
    lines.append(f"  - Kept: {filter_accounting.get('kept', 0)}")
    lines.append(f"  - Removed by age/date: {filter_accounting.get('removed_by_age', 0)}")
    lines.append(f"  - Removed by missing publication date: {filter_accounting.get('removed_by_missing_publication_date', 0)}")
    lines.append(f"  - Removed by min views: {filter_accounting.get('removed_by_min_views', 0)}")
    lines.append(f"  - Removed by min comments: {filter_accounting.get('removed_by_min_comments', 0)}\n")

    lines.append("## Executive read")
    if top_videos:
        lines.append("This run surfaced usable evidence: repeated titles, public metrics, narrative patterns, replacement language, and source links for your content, product, or operating workflow.\n")
    else:
        lines.append("Evidence insufficient: this run did not surface videos after filters. Treat the output as a run-status note, not as market insight.\n")

    lines.append("## 1. Top videos by signal")
    if top_videos:
        for row in top_videos[:10]:
            c = row.get("score_components") or {}
            lines.append(
                f"- **{row.get('title') or 'Untitled'}** | score: {row.get('signal_score')} | "
                f"channel: {row.get('channel_name') or 'Unknown'} | "
                f"URL: {row.get('video_url') or 'unavailable'} | "
                f"relevance={c.get('topical_relevance')} freshness={c.get('freshness')} intensity={c.get('signal_intensity')} repeatability={c.get('repeatability')} usefulness={c.get('usefulness')} | "
                f"queries: {', '.join(row.get('queries') or [])}"
            )
    else:
        lines.append("- No surfaced videos after filters. Treat this report as insufficient evidence, not an insight.")
    lines.append("")

    lines.append("## 2. Top repeated pains from comments")
    if pains:
        for label, count, evidence in pains:
            lines.append(f"- **{label}** - {count} hits")
            for video_id, snippet in evidence[:2]:
                lines.append(f"  - {video_id}: {clean_snippet(snippet)}")
    else:
        lines.append("- Not enough comment evidence yet. Run the comments layer on more surfaced videos.")
    lines.append("")

    lines.append("## 3. Migration / replacement signals")
    if migration_signals:
        for item in migration_signals:
            lines.append(f"- **{item.get('title') or item.get('video_id')}** | {item.get('channel_name') or 'Unknown'} | {item.get('reason')}")
    else:
        lines.append("- Clear migration signals not detected in the current local sample.")
    lines.append("")

    lines.append("## 4. Platform risk signals")
    if risk_signals:
        for item in risk_signals:
            lines.append(f"- **{item.get('title') or item.get('video_id')}** | {item.get('channel_name') or 'Unknown'} | {item.get('reason')}")
    else:
        lines.append("- Clear platform risk signals not detected in the current local sample.")
    lines.append("")

    lines.append("## 5. Strongest hooks / narrative patterns")
    if hooks:
        for hook in hooks:
            lines.append(f"- **{hook['label']}** - {hook['count']} matches")
            for example in hook["examples"][:2]:
                lines.append(f"  - {example}")
    else:
        lines.append("- Hook patterns need more surfaced titles to become meaningful.")
    lines.append("")

    lines.append("## 6. Content strategy ideas")
    if content_strategy_ideas:
        for idea in content_strategy_ideas:
            lines.append(f"- {idea}")
    else:
        lines.append("- No recommendation due to insufficient evidence.")
    lines.append("")

    lines.append("## 7. Workflow / operations ideas")
    if operations_ideas:
        for idea in operations_ideas:
            lines.append(f"- {idea}")
    else:
        lines.append("- No recommendation due to insufficient evidence.")
    lines.append("")

    lines.append("## 8. Proof assets / examples worth adapting")
    if proof_assets:
        for asset in proof_assets:
            lines.append(f"- {asset}")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Infra note")
    lines.append(f"- Active search providers this window: {search_health['providers']}")
    lines.append("- If fallback hits grow, treat it as a reliability signal: the run is surviving through backup paths/cache instead of failing completely.")
    lines.append("- The next quality gain should come from stronger search coverage and better signal scoring, not from more noise.\n")

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    ensure_project_dirs()
    args = parse_args()
    cutoff = now_utc() - timedelta(days=args.days)

    search_rows, query_runs, bundles = load_recent_search_data(cutoff)
    snapshots = [row for row in load_snapshot_history() if (iso_to_datetime(row.get("captured_at")) or now_utc()) >= cutoff]
    comment_sets = load_recent_comment_sets(cutoff)
    transcripts = load_recent_transcripts(cutoff)

    max_age_days = args.days if args.fresh_only else args.max_age_days
    all_merged_videos = merge_video_signals(search_rows, snapshots, comment_sets, transcripts)
    merged_videos, local_filter_accounting = summarize_filter_accounting(
        all_merged_videos,
        max_age_days=max_age_days,
        min_views=args.min_views,
        min_comments=args.min_comments,
    )
    report_filters_active = max_age_days is not None or args.min_views > 0 or args.min_comments > 0
    filter_accounting = local_filter_accounting if report_filters_active else merge_search_filter_accounting(bundles, local_filter_accounting)
    pains = extract_pains(comment_sets)
    migration_signals = extract_migration_signals(merged_videos, comment_sets)
    risk_signals = extract_risk_signals(merged_videos, comment_sets)
    hooks = extract_hook_patterns(merged_videos)
    if merged_videos:
        content_strategy_ideas = build_content_strategy_ideas(pains, migration_signals, hooks)
        operations_ideas = build_operations_ideas(pains, risk_signals, hooks)
    else:
        content_strategy_ideas = []
        operations_ideas = []
    proof_assets = build_proof_assets(migration_signals, risk_signals, hooks)
    search_health = summarize_search_health(query_runs)

    generated_at = now_utc().replace(microsecond=0).isoformat()
    report = render_report(
        days=args.days,
        generated_at=generated_at,
        top_videos=merged_videos,
        pains=pains,
        migration_signals=migration_signals,
        risk_signals=risk_signals,
        hooks=hooks,
        content_strategy_ideas=content_strategy_ideas,
        operations_ideas=operations_ideas,
        proof_assets=proof_assets,
        search_rows_count=len(search_rows),
        snapshots_count=len(snapshots),
        comment_sets_count=len(comment_sets),
        search_health=search_health,
        filter_accounting=filter_accounting,
    )

    out_path = Path(args.out) if args.out else REPORTS_DIR / f"weekly-report-{day_stamp()}-{time_slug()}.md"
    write_text(out_path, report)
    print(str(out_path))


if __name__ == "__main__":
    main()
