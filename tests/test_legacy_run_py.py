from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_legacy_init_instance_syntax_still_works(tmp_path: Path) -> None:
    target = tmp_path / "legacy-instance"

    result = subprocess.run(
        [sys.executable, "run.py", "init-instance", "--project-root", str(target)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (target / "watchlists" / "topics.yaml").exists()


def test_legacy_search_project_root_syntax_routes_to_new_cli(tmp_path: Path) -> None:
    target = tmp_path / "legacy-search"
    subprocess.run([sys.executable, "run.py", "init-instance", "--project-root", str(target)], check=True)

    result = subprocess.run(
        [
            sys.executable,
            "run.py",
            "search",
            "--project-root",
            str(target),
            "--query",
            "AI agents",
            "--search-provider",
            "cache",
            "--skip-watchlist-channels",
            "--continue-on-search-error",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "videos_count" in result.stdout
