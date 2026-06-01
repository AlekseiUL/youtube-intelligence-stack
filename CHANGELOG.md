# Changelog

## v0.4.3 — full help safety

- Made `youtube-intel full <project> --help` and legacy `run.py full --project-root <project> --help` side-effect free.
- Added regression tests proving full help does not call pipeline layers or create search/report artifacts.

## v0.4.2 — repo audit polish

- Applied snapshot command timeouts to optional watchlist-channel expansion, not only metadata batch fetches.
- Refreshed the example report to match current filter-accounting and URL-rich output.
- Hardened the repository quality scanner for additional token shapes and generated build/dist artifacts.
- Added read-only GitHub Actions permissions.
- Added regression coverage for snapshot channel timeout propagation.

## v0.4.1 — CLI polish and timeout semantics

- Classified YouTube comment collection timeouts as `status: "timeout"` instead of generic `error`.
- Accepted wrapper-level `--json` on layer commands without forwarding it to underlying scripts.
- Replaced Python traceback output for layer argument/runtime failures with clean stderr and the underlying exit code.
- Promoted `youtube-intel full --safe` as the recommended first end-to-end smoke command.
- Added regression tests for comment timeout status, layer `--json` tolerance, and clean wrapper error handling.

## v0.4.0 — UX and robustness hardening

- Removed strict `--fresh-only` from the public quick start so first runs are less likely to produce an empty report.
- Added filter accounting to search bundles and reports: candidates, kept rows, old rows removed, undated rows removed, and threshold removals.
- Made empty reports explicitly evidence-insufficient instead of presenting them as market-signal reads.
- Added source URLs to top-video report rows.
- Added safer empty-section rendering for recommendations and proof assets.
- Added `youtube-intel full --safe` with conservative limits, timeouts, and continue-on-search-error behavior.
- Added timeout support to transcripts metadata/subtitle collection.
- Added retry support to comments collection.
- Made snapshots more resilient to bad JSON lines and batch failures.
- Expanded CI to Python 3.10–3.13, installed-package smoke outside repo cwd, and evidence-based offline report smoke.

## v0.3.0 — report quality, filters, and release posture

- Added freshness and threshold filters.
- Added insufficient-evidence behavior for small/empty samples.
- Added collector tests and stronger public safety posture.

## v0.2.0 — installable CLI

- Added package metadata and `youtube-intel` console entrypoint.
- Added editable/install smoke path and legacy `run.py` compatibility.

## v0.1.0 — sanitized public release

- Published a clean local-first YouTube public-source research stack without private watchlists, cron, credentials, generated evidence, or internal workspace paths.
