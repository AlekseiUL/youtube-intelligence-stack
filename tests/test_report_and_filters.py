from __future__ import annotations

from datetime import timedelta
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "youtube_intelligence_stack" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from common import now_utc  # noqa: E402
import build_weekly_report as report  # noqa: E402


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "youtube_intelligence_stack", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_fallback_ideas_are_not_duplicated_when_evidence_is_missing() -> None:
    content = report.build_content_strategy_ideas([], [], [])
    ops = report.build_operations_ideas([], [], [])

    assert len(content) == len(set(content))
    assert len(ops) == len(set(ops))
    assert content == ["Insufficient evidence: collect more videos/comments before recommending content actions."]
    assert ops == ["Insufficient evidence: collect more videos/comments before recommending workflow actions."]


def test_report_marks_empty_top_videos_as_insufficient_evidence() -> None:
    text = report.render_report(
        days=7,
        generated_at="2026-01-01T00:00:00+00:00",
        top_videos=[],
        pains=[],
        migration_signals=[],
        risk_signals=[],
        hooks=[],
        content_strategy_ideas=["Insufficient evidence: collect more videos/comments before recommending content actions."],
        operations_ideas=["Insufficient evidence: collect more videos/comments before recommending workflow actions."],
        proof_assets=[],
        search_rows_count=0,
        snapshots_count=0,
        comment_sets_count=0,
        search_health={"fallback_hits": 0, "queries_total": 0, "hard_failures": 0, "providers": {}},
    )

    assert "Insufficient evidence" in text
    assert "Top videos by signal" in text
    assert "No surfaced videos after filters" in text


def test_search_max_age_days_filters_cached_old_videos(tmp_path: Path) -> None:
    target = tmp_path / "instance"
    init = run_cli("init", str(target))
    assert init.returncode == 0, init.stderr

    search_dir = target / "data" / "search" / "2026-01-01"
    search_dir.mkdir(parents=True)
    old_date = (now_utc() - timedelta(days=90)).date().isoformat()
    fresh_date = (now_utc() - timedelta(days=1)).date().isoformat()
    (search_dir / "search-20260101-000000.json").write_text(
        json.dumps(
            {
                "run_at": now_utc().replace(microsecond=0).isoformat(),
                "videos": [
                    {
                        "query": "AI agents",
                        "video_id": "old123",
                        "title": "Old AI agents video",
                        "published_at": old_date,
                        "views": 10000,
                        "comments_count": 100,
                    },
                    {
                        "query": "AI agents",
                        "video_id": "new123",
                        "title": "Fresh AI agents video",
                        "published_at": fresh_date,
                        "views": 100,
                        "comments_count": 1,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = run_cli(
        "search",
        str(target),
        "--query",
        "AI agents",
        "--search-provider",
        "cache",
        "--skip-watchlist-channels",
        "--max-age-days",
        "7",
        "--continue-on-search-error",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    bundle = json.loads(Path(payload["bundle_path"]).read_text(encoding="utf-8"))
    assert [item["video_id"] for item in bundle["videos"]] == ["new123"]


def test_search_min_views_and_comments_filters_cached_videos(tmp_path: Path) -> None:
    target = tmp_path / "instance"
    init = run_cli("init", str(target))
    assert init.returncode == 0, init.stderr

    search_dir = target / "data" / "search" / "2026-01-01"
    search_dir.mkdir(parents=True)
    fresh_date = (now_utc() - timedelta(days=1)).date().isoformat()
    (search_dir / "search-20260101-000000.json").write_text(
        json.dumps(
            {
                "run_at": now_utc().replace(microsecond=0).isoformat(),
                "videos": [
                    {"query": "AI agents", "video_id": "low", "title": "Low", "published_at": fresh_date, "views": 10, "comments_count": 0},
                    {"query": "AI agents", "video_id": "high", "title": "High", "published_at": fresh_date, "views": 1000, "comments_count": 20},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = run_cli(
        "search",
        str(target),
        "--query",
        "AI agents",
        "--search-provider",
        "cache",
        "--skip-watchlist-channels",
        "--min-views",
        "100",
        "--min-comments",
        "5",
        "--continue-on-search-error",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    bundle = json.loads(Path(payload["bundle_path"]).read_text(encoding="utf-8"))
    assert [item["video_id"] for item in bundle["videos"]] == ["high"]


def test_report_max_age_days_filters_old_videos(tmp_path: Path) -> None:
    target = tmp_path / "report-filter"
    init = run_cli("init", str(target))
    assert init.returncode == 0, init.stderr
    search_dir = target / "data" / "search" / "2026-01-01"
    search_dir.mkdir(parents=True)
    old_date = (now_utc() - timedelta(days=90)).date().isoformat()
    fresh_date = (now_utc() - timedelta(days=1)).date().isoformat()
    (search_dir / "search-20260101-000000.json").write_text(
        json.dumps(
            {
                "run_at": now_utc().replace(microsecond=0).isoformat(),
                "query_runs": [{"selected_provider": "fixture", "entries": 2}],
                "videos": [
                    {"query": "AI agents", "video_id": "old", "title": "Old market map", "published_at": old_date, "views": 99999, "comments_count": 99},
                    {"query": "AI agents", "video_id": "fresh", "title": "Fresh AI agents tutorial", "published_at": fresh_date, "views": 100, "comments_count": 1},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = target / "filtered-report.md"

    result = run_cli("report", str(target), "--days", "3650", "--max-age-days", "7", "--out", str(out))

    assert result.returncode == 0, result.stderr
    text = out.read_text(encoding="utf-8")
    assert "Fresh AI agents tutorial" in text
    assert "Old market map" not in text
