from __future__ import annotations

import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "youtube_intelligence_stack" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from common import now_utc  # noqa: E402
import build_weekly_report as report  # noqa: E402
import yt_search  # noqa: E402
import yt_snapshots  # noqa: E402
import yt_transcripts  # noqa: E402
import yt_comments  # noqa: E402


class FakeCompleted:
    def __init__(self, stdout: str):
        self.stdout = stdout
        self.stderr = ""


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "youtube_intelligence_stack", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_search_bundle_records_filter_accounting_for_fresh_only(tmp_path: Path) -> None:
    target = tmp_path / "instance"
    assert run_cli("init", str(target)).returncode == 0
    old_date = (now_utc() - timedelta(days=60)).date().isoformat()
    fresh_date = (now_utc() - timedelta(days=1)).date().isoformat()
    search_dir = target / "data" / "search" / "2026-01-01"
    search_dir.mkdir(parents=True)
    (search_dir / "search-20260101-000000.json").write_text(
        json.dumps(
            {
                "run_at": now_utc().replace(microsecond=0).isoformat(),
                "videos": [
                    {"query": "AI agents", "video_id": "old", "title": "Old", "published_at": old_date, "views": 1000, "comments_count": 10},
                    {"query": "AI agents", "video_id": "undated", "title": "Undated", "views": 1000, "comments_count": 10},
                    {"query": "AI agents", "video_id": "fresh", "title": "Fresh", "published_at": fresh_date, "views": 1000, "comments_count": 10},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = run_cli("search", str(target), "--query", "AI agents", "--search-provider", "cache", "--skip-watchlist-channels", "--fresh-only")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    bundle = json.loads(Path(payload["bundle_path"]).read_text(encoding="utf-8"))
    assert [row["video_id"] for row in bundle["videos"]] == ["fresh"]
    assert bundle["filter_accounting"]["candidates_before_filters"] == 3
    assert bundle["filter_accounting"]["kept"] == 1
    assert bundle["filter_accounting"]["removed_by_age"] == 1
    assert bundle["filter_accounting"]["removed_by_missing_publication_date"] == 1
    assert payload["filter_accounting"]["kept"] == 1


def test_report_empty_run_is_evidence_insufficient_not_market_signal() -> None:
    text = report.render_report(
        days=7,
        generated_at="2026-01-01T00:00:00+00:00",
        top_videos=[],
        pains=[],
        migration_signals=[],
        risk_signals=[],
        hooks=[],
        content_strategy_ideas=[],
        operations_ideas=[],
        proof_assets=[],
        search_rows_count=0,
        snapshots_count=0,
        comment_sets_count=0,
        search_health={"fallback_hits": 0, "queries_total": 0, "hard_failures": 0, "providers": {}},
        filter_accounting={"candidates_before_filters": 0, "kept": 0, "removed_by_age": 0, "removed_by_missing_publication_date": 0, "removed_by_min_views": 0, "removed_by_min_comments": 0},
    )

    assert "Evidence insufficient" in text
    assert "market-signal pass" not in text
    assert "## 6. Content strategy ideas" in text
    assert "No recommendation due to insufficient evidence" in text
    assert "## 8. Proof assets / examples worth adapting" in text
    assert "- none" in text


def test_report_top_videos_include_urls_and_filter_accounting() -> None:
    text = report.render_report(
        days=7,
        generated_at="2026-01-01T00:00:00+00:00",
        top_videos=[
            {
                "title": "Demo AI agents video",
                "video_url": "https://www.youtube.com/watch?v=demo123",
                "channel_name": "Demo Channel",
                "published_at": "2026-01-01T00:00:00+00:00",
                "signal_score": 77.0,
                "queries": ["AI agents"],
                "score_components": {"topical_relevance": 1.0, "freshness": 1.0, "signal_intensity": 0.5, "repeatability": 0.3, "usefulness": 0.8},
            }
        ],
        pains=[],
        migration_signals=[],
        risk_signals=[],
        hooks=[],
        content_strategy_ideas=[],
        operations_ideas=[],
        proof_assets=[],
        search_rows_count=1,
        snapshots_count=0,
        comment_sets_count=0,
        search_health={"fallback_hits": 0, "queries_total": 1, "hard_failures": 0, "providers": {"fixture": 1}},
        filter_accounting={"candidates_before_filters": 3, "kept": 1, "removed_by_age": 1, "removed_by_missing_publication_date": 1, "removed_by_min_views": 0, "removed_by_min_comments": 0},
    )

    assert "URL: https://www.youtube.com/watch?v=demo123" in text
    assert "Filter accounting" in text
    assert "Candidates before filters: 3" in text
    assert "Removed by age/date: 1" in text
    assert "Removed by missing publication date: 1" in text


def test_report_level_filters_override_search_bundle_accounting(tmp_path: Path) -> None:
    target = tmp_path / "report-accounting"
    assert run_cli("init", str(target)).returncode == 0
    old_date = (now_utc() - timedelta(days=60)).date().isoformat()
    search_dir = target / "data" / "search" / "2026-01-01"
    search_dir.mkdir(parents=True)
    (search_dir / "search-20260101-000000.json").write_text(
        json.dumps(
            {
                "run_at": now_utc().replace(microsecond=0).isoformat(),
                "query_runs": [{"selected_provider": "fixture", "entries": 1}],
                "filter_accounting": {
                    "candidates_before_filters": 1,
                    "kept": 1,
                    "removed_by_age": 0,
                    "removed_by_missing_publication_date": 0,
                    "removed_by_min_views": 0,
                    "removed_by_min_comments": 0,
                },
                "videos": [
                    {"query": "AI agents", "video_id": "old", "title": "Old", "published_at": old_date, "views": 1000, "comments_count": 10},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = target / "report.md"

    result = run_cli("report", str(target), "--fresh-only", "--out", str(out))

    assert result.returncode == 0, result.stderr
    text = out.read_text(encoding="utf-8")
    assert "Kept: 0" in text
    assert "Removed by age/date: 1" in text
    assert "Evidence insufficient" in text


def test_search_json_decode_error_falls_back_to_cache(monkeypatch) -> None:
    monkeypatch.setattr(yt_search, "fetch_search_entries_yt_dlp", lambda *args, **kwargs: (_ for _ in ()).throw(json.JSONDecodeError("bad", "", 0)))
    monkeypatch.setattr(yt_search, "load_previous_query_results", lambda query, limit: [{"video_id": "cached"}])

    rows, meta = yt_search.fetch_query_with_fallbacks("AI agents", 1, ["ytsearch", "cache"], 0, 1, 1.0)

    assert rows == [{"video_id": "cached"}]
    assert meta["provider"] == "cache"
    assert meta["attempts"][0]["status"] == "parse_error"


def test_snapshots_batch_skips_bad_json_lines(monkeypatch) -> None:
    monkeypatch.setattr(yt_snapshots, "run_command", lambda args, timeout_sec=None: FakeCompleted('{"id":"ok"}\nnot-json\n{"id":"ok2"}\n'))

    rows = yt_snapshots.fetch_metadata_batch(["https://youtu.be/ok"], timeout_sec=1.0)

    assert [row["id"] for row in rows] == ["ok", "ok2"]


def test_transcript_fetch_metadata_accepts_timeout(monkeypatch) -> None:
    seen = {}

    def fake_run_command(args, timeout_sec=None):
        seen["timeout_sec"] = timeout_sec
        return FakeCompleted(json.dumps({"id": "abc"}))

    monkeypatch.setattr(yt_transcripts, "run_command", fake_run_command)

    assert yt_transcripts.fetch_metadata("https://youtu.be/abc", timeout_sec=12.5)["id"] == "abc"
    assert seen["timeout_sec"] == 12.5


def test_comments_fetch_retries_after_transient_error(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}

    def fake_fetch(url, sort_mode, timeout_sec):
        calls["count"] += 1
        if calls["count"] == 1:
            raise subprocess.CalledProcessError(1, ["yt-dlp"], stderr="temporary")
        return {"id": "abc", "comments": []}

    monkeypatch.setattr(yt_comments, "fetch_comments", fake_fetch)
    monkeypatch.setattr(yt_comments, "sleep_ms", lambda value: None)

    payload, error, status = yt_comments.fetch_comments_with_retries("https://youtu.be/abc", "top", 1.0, retry_count=1, retry_backoff_ms=1)

    assert payload["id"] == "abc"
    assert error is None
    assert status is None
    assert calls["count"] == 2
