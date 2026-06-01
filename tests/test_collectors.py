from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "youtube_intelligence_stack" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import yt_comments  # noqa: E402
import yt_search  # noqa: E402
import yt_snapshots  # noqa: E402
import yt_transcripts  # noqa: E402


class FakeCompleted:
    def __init__(self, stdout: str):
        self.stdout = stdout
        self.stderr = ""


def test_search_yt_dlp_parser_uses_mocked_stdout(monkeypatch) -> None:
    def fake_run_command(args, timeout_sec=None):
        return FakeCompleted(json.dumps({"entries": [{"id": "abc", "title": "Demo"}]}, ensure_ascii=False))

    monkeypatch.setattr(yt_search, "run_command", fake_run_command)

    rows = yt_search.fetch_search_entries_yt_dlp("ytsearch", "AI agents", 1, 2.0)

    assert rows == [{"id": "abc", "title": "Demo"}]


def test_search_fallback_records_error_then_cache_hit(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_fetch(provider, query, limit, timeout_sec):
        calls["count"] += 1
        raise subprocess.CalledProcessError(1, ["yt-dlp"], stderr="rate limited")

    monkeypatch.setattr(yt_search, "fetch_search_entries_yt_dlp", fake_fetch)
    monkeypatch.setattr(yt_search, "load_previous_query_results", lambda query, limit: [{"video_id": "cached"}])
    monkeypatch.setattr(yt_search, "sleep_ms", lambda value: None)

    rows, meta = yt_search.fetch_query_with_fallbacks(
        query="AI agents",
        limit=1,
        providers=["ytsearch", "cache"],
        retry_count=0,
        retry_backoff_ms=1,
        timeout_sec=1.0,
    )

    assert rows == [{"video_id": "cached"}]
    assert meta["provider"] == "cache"
    assert meta["used_fallback"] is True
    assert meta["attempts"][0]["status"] == "error"


def test_snapshots_metadata_batch_parses_json_lines(monkeypatch) -> None:
    def fake_run_command(args, timeout_sec=None):
        return FakeCompleted('{"id":"a","title":"A"}\n{"id":"b","title":"B"}\n')

    monkeypatch.setattr(yt_snapshots, "run_command", fake_run_command)

    rows = yt_snapshots.fetch_metadata_batch(["https://youtu.be/a", "https://youtu.be/b"])

    assert [row["id"] for row in rows] == ["a", "b"]


def test_snapshots_channel_url_fetch_uses_timeout(monkeypatch) -> None:
    seen = {}

    def fake_run_command(args, timeout_sec=None):
        seen["timeout_sec"] = timeout_sec
        return FakeCompleted(json.dumps({"entries": [{"id": "abc"}]}, ensure_ascii=False))

    monkeypatch.setattr(yt_snapshots, "run_command", fake_run_command)

    urls = yt_snapshots.fetch_channel_video_urls("https://www.youtube.com/@example/videos", 1, timeout_sec=12.5)

    assert urls == ["https://www.youtube.com/watch?v=abc"]
    assert seen["timeout_sec"] == 12.5


def test_transcript_language_prefers_manual_before_auto() -> None:
    meta = {
        "subtitles": {"en": [{"url": "manual"}]},
        "automatic_captions": {"en": [{"url": "auto"}], "ru": [{"url": "auto-ru"}]},
    }

    lang, is_generated = yt_transcripts.choose_language(meta, ["en", "ru"])

    assert lang == "en"
    assert is_generated is False


def test_transcript_parse_vtt_deduplicates_cues(tmp_path: Path) -> None:
    path = tmp_path / "demo.vtt"
    path.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello world\n\n00:00:01.000 --> 00:00:02.000\nHello world\n\n00:00:02.000 --> 00:00:03.000\nNext cue\n",
        encoding="utf-8",
    )

    assert yt_transcripts.parse_vtt(path) == ["Hello world", "Next cue"]


def test_comments_normalize_and_merge_threads() -> None:
    payload = {
        "id": "video1",
        "comments": [
            {"id": "root1", "parent": "root", "author": "A", "text": "first", "like_count": 2},
            {"id": "reply1", "parent": "root1", "author": "B", "text": "reply", "like_count": 1},
        ],
    }

    rows = yt_comments.normalize_comments(payload, "top", "2026-01-01T00:00:00+00:00")
    merged = yt_comments.merge_comment_rows({"top": rows, "recent": rows})

    assert rows[0]["thread_id"] == "root1"
    assert rows[1]["is_reply"] is True
    assert len(merged) == 2
    assert sorted(merged[0]["sort_modes"]) == ["recent", "top"]
