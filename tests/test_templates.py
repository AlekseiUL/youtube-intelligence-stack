from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "youtube_intelligence_stack", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_creator_template_has_creator_research_topics(tmp_path: Path) -> None:
    target = tmp_path / "creator"

    result = run_cli("init", str(target), "--template", "creator")

    assert result.returncode == 0, result.stderr
    topics = (target / "watchlists" / "topics.yaml").read_text(encoding="utf-8")
    assert "content hooks" in topics
    assert "audience pain points" in topics


def test_competitor_template_has_market_topics(tmp_path: Path) -> None:
    target = tmp_path / "competitor"

    result = run_cli("init", str(target), "--template", "competitor")

    assert result.returncode == 0, result.stderr
    topics = (target / "watchlists" / "topics.yaml").read_text(encoding="utf-8")
    assert "alternative to" in topics
    assert "platform risk" in topics
