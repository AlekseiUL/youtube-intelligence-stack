# Offline verification boundary

Pinned CI dependency graph and versioned local collector fixtures.

## Reproduce

Use Python 3.10+ (the example uses 3.12), in a fresh development venv:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements-ci.lock ".[dev]"
python -m pytest
python scripts/repository_quality.py
python scripts/smoke_documented_install.py
```

The install smoke executes the identical EN/RU README quick-start block in a temporary HOME outside the checkout, replacing only the interpreter and package source with this candidate checkout. It creates a fresh venv and installs a normal, non-editable package. It checks help, doctor, creator watchlists and the empty offline report, then checks failure for a missing project and an unknown command. Package installation may contact the package index; the CLI smoke does not contact YouTube. Set `TMPDIR` to choose where disposable verification files live.

For a public-source post-merge check, run `python scripts/smoke_documented_install.py --source "git+https://github.com/AlekseiUL/youtube-intelligence-stack.git@<verified-main-sha>"`, substituting the verified commit. This does not test live YouTube access.

Local aggregation and fake collectors are tested separately from opt-in remote adapters. No external collection or API credentials in this gate.

## Rollback

Review the commit diff and use a new checkout of the pre-change commit for source rollback. Keep user data and live installations untouched. A source rollback is not permission to restore unsafe network exposure or bypass approval.
