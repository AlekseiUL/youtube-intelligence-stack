#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(os.environ.get("YOUTUBE_INTEL_PROJECT_ROOT", str(Path(__file__).resolve().parents[1]))).resolve()
WATCHLISTS_DIR = ROOT / "watchlists"
DATA_DIR = ROOT / "data"
SEARCH_DIR = DATA_DIR / "search"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
COMMENTS_DIR = DATA_DIR / "comments"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
REPORTS_DIR = DATA_DIR / "reports"
EXAMPLES_DIR = ROOT / "examples"

YOUTUBE_BASE = "https://www.youtube.com/watch?v="
STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "have", "into", "your", "about", "they", "their",
    "what", "when", "where", "which", "there", "would", "could", "should", "been", "were", "them", "then",
    "just", "than", "more", "some", "much", "very", "really", "because", "still", "after", "before", "over",
    "under", "while", "into", "also", "only", "like", "dont", "doesnt", "cant", "wont", "isnt", "arent",
    "это", "как", "что", "для", "или", "если", "когда", "потому", "очень", "только", "после", "перед",
    "уже", "ещё", "еще", "тоже", "лишь", "надо", "нужно", "просто", "тут", "там", "где", "кто", "они",
    "она", "оно", "мы", "вы", "нас", "вам", "его", "её", "их", "про", "под", "без", "при", "из", "на",
    "по", "в", "и", "а", "но", "не", "да", "ну", "то", "же", "бы", "до", "от", "за", "об", "о"
}

TARGET_KEYWORDS = {
    "ai agents", "multi-agent", "multi agent", "agent framework", "agent runtime",
    "agent memory", "memory", "automation", "ai automation", "workflow", "orchestration",
    "knowledge management", "customer support automation", "productivity", "no-code automation",
    "platform risk", "vendor lock-in", "reliability", "operations", "agents", "agent",
}


def ensure_project_dirs() -> None:
    for path in [
        DATA_DIR,
        SEARCH_DIR,
        TRANSCRIPTS_DIR,
        COMMENTS_DIR,
        SNAPSHOTS_DIR,
        REPORTS_DIR,
        EXAMPLES_DIR,
        ROOT / "scripts",
        WATCHLISTS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)




def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().replace(microsecond=0).isoformat()


def sleep_ms(value: int) -> None:
    if value > 0:
        time.sleep(value / 1000)


def day_stamp(dt: datetime | None = None) -> str:
    return (dt or now_utc()).strftime("%Y-%m-%d")


def time_slug(dt: datetime | None = None) -> str:
    return (dt or now_utc()).strftime("%Y%m%d-%H%M%S")


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ]+", "-", value.strip().lower())
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "item"


def load_yaml(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> int:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with target.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def append_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> int:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with target.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def run_command(
    args: list[str],
    *,
    cwd: str | Path | None = None,
    timeout_sec: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        add = len(word) + (1 if current else 0)
        if current and current_len + add > max_chars:
            chunks.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += add
    if current:
        chunks.append(" ".join(current))
    return chunks


def parse_upload_date(value: str | None) -> str | None:
    if not value:
        return None
    if re.fullmatch(r"\d{8}", value):
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
    return value


def parse_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).replace(microsecond=0).isoformat()
    except Exception:
        return None


def video_url_from_id(video_id: str | None) -> str | None:
    if not video_id:
        return None
    return f"{YOUTUBE_BASE}{video_id}"


def normalize_video_record(
    raw: dict[str, Any],
    *,
    source: str,
    query: str | None = None,
    collected_at: str | None = None,
    source_provider: str | None = None,
) -> dict[str, Any]:
    video_id = first_non_empty(raw.get("id"), raw.get("display_id"), raw.get("video_id"))
    title = clean_text(first_non_empty(raw.get("title"), raw.get("fulltitle")))
    channel_name = clean_text(first_non_empty(raw.get("channel"), raw.get("channel_name"), raw.get("uploader")))
    return {
        "query": query,
        "source": source,
        "source_provider": source_provider,
        "collected_at": collected_at or now_iso(),
        "title": title,
        "video_url": first_non_empty(raw.get("webpage_url"), raw.get("url"), video_url_from_id(video_id)),
        "video_id": video_id,
        "channel_name": channel_name,
        "channel_url": first_non_empty(raw.get("channel_url"), raw.get("uploader_url")),
        "published_at": first_non_empty(parse_timestamp(raw.get("timestamp")), parse_upload_date(raw.get("upload_date"))),
        "duration": first_non_empty(raw.get("duration_string"), raw.get("duration")),
        "views": first_non_empty(raw.get("view_count"), raw.get("views_count"), 0),
        "comments_count": first_non_empty(raw.get("comment_count"), 0),
        "likes": first_non_empty(raw.get("like_count"), 0),
        "description_snippet": clean_text((raw.get("description") or "")[:400]),
        "tags": raw.get("tags") or [],
    }


def load_channel_watchlist(path: str | Path) -> list[dict[str, Any]]:
    data = load_yaml(path)
    items: list[dict[str, Any]] = []
    for layer in ["direct", "adjacent", "global_signal"]:
        raw_items = data.get(layer) or []
        for raw in raw_items:
            if isinstance(raw, str):
                items.append({"layer": layer, "name": raw, "url": raw, "enabled": True, "tags": []})
            elif isinstance(raw, dict):
                items.append({
                    "layer": layer,
                    "name": raw.get("name") or raw.get("url") or raw.get("handle") or "unknown",
                    "url": raw.get("url"),
                    "enabled": raw.get("enabled", True),
                    "tags": raw.get("tags") or [],
                })
    return [item for item in items if item.get("enabled") and item.get("url")]


def latest_path(directory: str | Path, pattern: str) -> Path | None:
    base = Path(directory)
    matches = sorted(base.glob(pattern))
    return matches[-1] if matches else None


def iter_search_bundle_paths() -> list[Path]:
    return sorted(
        p for p in SEARCH_DIR.glob("**/search-*.json")
        if not p.name.endswith(".channels.json") and not p.name.endswith(".videos.json")
    )


def load_previous_query_results(query: str, limit: int = 10) -> list[dict[str, Any]]:
    needle = query.strip().lower()
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in reversed(iter_search_bundle_paths()):
        try:
            bundle = read_json(path)
        except Exception:
            continue
        for row in bundle.get("videos") or []:
            row_query = str(row.get("query") or "").strip().lower()
            if row_query != needle:
                continue
            key = row.get("video_id") or row.get("video_url")
            if not key or key in seen:
                continue
            seen.add(key)
            cloned = dict(row)
            cloned["source"] = cloned.get("source") or "cached_query_result"
            cloned["source_provider"] = cloned.get("source_provider") or "cache"
            results.append(cloned)
            if len(results) >= limit:
                return results
    return results


def latest_search_bundle(explicit: str | Path | None = None) -> Path | None:
    if explicit:
        return Path(explicit)
    matches = iter_search_bundle_paths()
    return matches[-1] if matches else None


def resolve_video_inputs(
    *,
    video_ids: list[str] | None = None,
    video_urls: list[str] | None = None,
    from_search: str | Path | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for video_id in video_ids or []:
        items.append({"video_id": video_id, "video_url": video_url_from_id(video_id)})
    for url in video_urls or []:
        items.append({"video_id": None, "video_url": url})
    bundle_path = latest_search_bundle(from_search)
    if bundle_path:
        bundle = read_json(bundle_path)
        for row in bundle.get("videos") or []:
            items.append({"video_id": row.get("video_id"), "video_url": row.get("video_url")})
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = item.get("video_id") or item.get("video_url")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:limit] if limit else deduped


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def load_snapshot_history() -> list[dict[str, Any]]:
    history_path = SNAPSHOTS_DIR / "history.jsonl"
    return read_jsonl(history_path)


def count_tokens(text: str) -> Counter[str]:
    tokens = re.findall(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9+._-]{2,}", text.lower())
    return Counter(token for token in tokens if token not in STOPWORDS)


def keyword_overlap_score(texts: Iterable[str], keywords: Iterable[str] | None = None) -> float:
    hay = " ".join(texts).lower()
    lexicon = [item.lower() for item in (keywords or TARGET_KEYWORDS)]
    if not lexicon:
        return 0.0
    hits = sum(1 for keyword in lexicon if keyword and keyword in hay)
    return round(hits / max(len(lexicon), 1), 4)


def iso_to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except Exception:
        try:
            return datetime.fromisoformat(value + "T00:00:00+00:00")
        except Exception:
            return None
