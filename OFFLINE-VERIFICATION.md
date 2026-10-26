# Offline verification boundary

Pinned CI dependency graph and versioned local collector fixtures.

## Reproduce

`python -m pip install -c requirements-ci.lock ".[dev]"; python -m pytest`

Local aggregation and fake collectors are tested separately from opt-in remote adapters. No external collection or API credentials in this gate.

## Rollback

Review the commit diff and use a new checkout of the pre-change commit for source rollback. Keep user data and live installations untouched. A source rollback is not permission to restore unsafe network exposure or bypass approval.
