#!/usr/bin/env python3
"""Run the bilingual README quick start using a fresh, non-editable install."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SOURCE = "git+https://github.com/AlekseiUL/youtube-intelligence-stack.git"


def quick_start(text: str, heading: str) -> str:
    section = text.split(heading, 1)[1]
    return section.split("```bash\n", 1)[1].split("```", 1)[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(ROOT), help="Package path or exact public git URL")
    args = parser.parse_args()
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    block = quick_start(text, "### Option A")
    assert block == quick_start(text, "## Быстрый старт"), "EN/RU quick starts differ"
    assert block.count(f'"{PUBLIC_SOURCE}"') == 1
    assert " -e " not in block, "Quick start must not use an editable install"
    commands = [line.split()[1] for line in block.splitlines() if line.startswith("youtube-intel ")]
    assert commands == ["--help", "doctor", "init", "doctor", "report"], commands
    block = re.sub(r"(?m)^python3\.12\b", shlex.quote(sys.executable), block)
    block = block.replace(f'"{PUBLIC_SOURCE}"', shlex.quote(args.source))

    with tempfile.TemporaryDirectory(prefix="youtube-install-") as temp:
        home = Path(temp)
        env = {
            "HOME": str(home), "PATH": os.defpath,
            "TMPDIR": str(home), "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1",
        }
        subprocess.run(["bash", "-e", "-c", block], cwd=home, env=env, check=True)
        bin_dir = home / ".venvs" / "youtube-intel" / "bin"
        env["PATH"] = str(bin_dir) + os.pathsep + os.defpath
        cli = str(bin_dir / "youtube-intel")
        project = home / "youtube-intel-demo"
        assert "content hooks" in (project / "watchlists/topics.yaml").read_text()
        assert (project / "watchlists/channels.yaml").is_file()
        assert "Evidence insufficient" in (project / "offline-report.md").read_text()
        assert not list((project / "data/search").iterdir()), "Offline smoke collected data"
        result = subprocess.run([cli, "doctor", str(project), "--json"], cwd=home,
                                env=env, text=True, capture_output=True, check=True)
        assert json.loads(result.stdout)["ok"] is True
        subprocess.run([cli, "--version"], cwd=home, env=env, check=True)
        probe = (
            "import json, sys, youtube_intelligence_stack as p; "
            "from importlib.metadata import distribution; "
            "d=distribution('youtube-intelligence-stack'); "
            "print(json.dumps({'file':p.__file__, 'prefix':sys.prefix, "
            "'direct':json.loads(d.read_text('direct_url.json') or '{}')}))"
        )
        result = subprocess.run([str(bin_dir / "python"), "-I", "-c", probe], cwd=home,
                                env=env, capture_output=True, text=True, check=True)
        installed = json.loads(result.stdout)
        assert Path(installed["file"]).is_relative_to(home / ".venvs" / "youtube-intel")
        assert not installed["direct"].get("dir_info", {}).get("editable", False)
        for argv in (["doctor", str(home / "missing")], ["not-a-command"]):
            result = subprocess.run([cli, *argv], cwd=home, env=env, text=True, capture_output=True)
            assert result.returncode != 0, argv
            print(f"Expected refusal: {argv[0]} exit={result.returncode}")
        print("Documented install: PASS (normal venv install, EN/RU parity, offline CLI and failure paths)")
        print("Live YouTube smoke: NOT_RUN")


if __name__ == "__main__":
    main()
