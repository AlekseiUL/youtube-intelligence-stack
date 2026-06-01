# Contributing

Contributions are welcome if they keep the project local-first, reproducible, and safe to publish.

Before opening a PR:

1. Run `python scripts/repository_quality.py`.
2. Run `python run.py init-instance --project-root /tmp/youtube-intel-contrib-smoke`.
3. Do not include generated `data/`, cookies, `.env`, private watchlists, or local paths.
4. Keep examples synthetic or clearly public-safe.

Good contributions:

- better scoring heuristics;
- safer collectors;
- offline tests;
- cleaner reports;
- documentation improvements.

Out of scope:

- bypassing YouTube access controls;
- shipping private datasets;
- scraping behind authentication by default;
- adding hidden cron/scheduler behavior.
