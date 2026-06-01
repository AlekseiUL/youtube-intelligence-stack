from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "youtube_intelligence_stack", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_module_cli_help_shows_product_command() -> None:
    result = run_cli("--help")

    assert result.returncode == 0, result.stderr
    assert "youtube-intel" in result.stdout
    assert "doctor" in result.stdout
    assert "init" in result.stdout


def test_doctor_json_reports_environment() -> None:
    result = run_cli("doctor", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["python"]["ok"] is True
    assert "yt_dlp" in payload


def test_doctor_fails_for_missing_watchlists(tmp_path: Path) -> None:
    result = run_cli("doctor", str(tmp_path), "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["project_root"]["topics"] is False
    assert payload["project_root"]["channels"] is False


def test_doctor_passes_for_initialized_instance(tmp_path: Path) -> None:
    target = tmp_path / "instance"
    init = run_cli("init", str(target))
    assert init.returncode == 0, init.stderr

    result = run_cli("doctor", str(target), "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["project_root"]["topics"] is True
    assert payload["project_root"]["channels"] is True


def test_init_creates_public_safe_instance(tmp_path: Path) -> None:
    target = tmp_path / "instance"

    result = run_cli("init", str(target))

    assert result.returncode == 0, result.stderr
    assert (target / "watchlists" / "topics.yaml").exists()
    assert (target / "watchlists" / "channels.yaml").exists()
    readme = (target / "README.md").read_text(encoding="utf-8")
    assert "youtube-intel full" in readme
    forbidden = ["private workspace", "internal agent", "operator-only"]
    assert not any(term in readme.lower() for term in forbidden)


def test_report_command_builds_from_fixture_instance(tmp_path: Path) -> None:
    target = tmp_path / "fixture-instance"
    result = run_cli("init", str(target))
    assert result.returncode == 0, result.stderr

    search_dir = target / "data" / "search" / "2026-01-01"
    search_dir.mkdir(parents=True)
    (search_dir / "search-20260101-000000.json").write_text(
        json.dumps(
            {
                "run_at": "2026-01-01T00:00:00+00:00",
                "query_runs": [
                    {"selected_provider": "fixture", "used_fallback": False, "entries": 1}
                ],
                "videos": [
                    {
                        "video_id": "demo123",
                        "title": "How to build an AI agent workflow",
                        "video_url": "https://www.youtube.com/watch?v=demo123",
                        "channel_name": "Example Channel",
                        "published_at": "2026-01-01T00:00:00+00:00",
                        "views": 1000,
                        "comments_count": 5,
                        "description_snippet": "A practical workflow automation guide",
                        "query": "AI agents",
                        "source_provider": "fixture",
                        "collected_at": "2026-01-01T00:00:00+00:00",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    out = target / "report.md"
    result = run_cli("report", str(target), "--days", "3650", "--out", str(out))

    assert result.returncode == 0, result.stderr
    text = out.read_text(encoding="utf-8")
    assert "YouTube Intelligence Weekly Report" in text
    assert "How to build an AI agent workflow" in text
    assert "private workspace" not in text.lower()
    assert "operator-only" not in text.lower()
