from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "youtube_intelligence_stack" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import yt_comments  # noqa: E402


def test_comments_timeout_is_classified_as_timeout(monkeypatch) -> None:
    def fake_fetch(url, sort_mode, timeout_sec):
        raise subprocess.TimeoutExpired(["yt-dlp"], timeout_sec)

    monkeypatch.setattr(yt_comments, "fetch_comments", fake_fetch)
    monkeypatch.setattr(yt_comments, "sleep_ms", lambda value: None)

    payload, error, status = yt_comments.fetch_comments_with_retries(
        "https://www.youtube.com/watch?v=demo123",
        "top",
        0.001,
        retry_count=0,
        retry_backoff_ms=1,
    )

    assert payload == {}
    assert status == "timeout"
    assert "timed out" in error


def test_layer_json_flag_is_accepted_and_not_forwarded(monkeypatch, tmp_path: Path) -> None:
    from youtube_intelligence_stack import cli

    calls = []

    def fake_run_layer(command, project_root, extra_args):
        calls.append((command, Path(project_root), list(extra_args)))

    monkeypatch.setattr(cli, "run_layer", fake_run_layer)

    cli.main(["search", str(tmp_path), "--json", "--query", "AI agents"])

    assert calls == [("search", tmp_path, ["--query", "AI agents"])]


def test_layer_subprocess_errors_are_clean_without_traceback(monkeypatch, tmp_path: Path, capsys) -> None:
    from youtube_intelligence_stack import cli

    def fake_run_layer(command, project_root, extra_args):
        raise subprocess.CalledProcessError(2, ["yt_search.py", "--bad"], stderr="usage: yt_search.py\nerror: bad args\n")

    monkeypatch.setattr(cli, "run_layer", fake_run_layer)

    try:
        cli.main(["search", str(tmp_path), "--bad"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")

    captured = capsys.readouterr()
    assert "error: bad args" in captured.err
    assert "Traceback" not in captured.err
