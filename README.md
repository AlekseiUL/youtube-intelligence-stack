# YouTube Intelligence Stack

Local-first YouTube intelligence pipeline for public-source research: search public videos, collect transcripts/comments/metrics where available, and turn the evidence into weekly Markdown reports.

This repository is designed as a clean public product: no private watchlists, no cron jobs, no operator data, no API keys, and no generated evidence committed to Git.

## Who is this for?

YouTube Intelligence Stack is for:

- creators tracking new videos, hooks, pains, and audience questions in a niche;
- founders and marketers watching competitor/category narratives;
- researchers building a local evidence archive from public YouTube data;
- AI-agent builders who want a simple file-based pipeline instead of another dashboard.

It is not:

- a YouTube access-control bypass;
- a bot farm;
- a private data collector;
- a fully managed SaaS platform.

## What it does

```mermaid
flowchart LR
    A[Watchlists: topics/channels] --> B[Search public YouTube]
    B --> C[Collect metadata]
    C --> D[Optional transcripts/comments]
    C --> E[Metric snapshots]
    D --> F[Weekly Markdown report]
    E --> F
```

Main capabilities:

- topic-based YouTube search;
- channel watchlists;
- fallback/retry/throttle behavior around `yt-dlp`;
- transcript collection when subtitles are available;
- comment collection when YouTube exposes comments to `yt-dlp`;
- metric snapshots over time;
- weekly Markdown report with pains, migration/replacement signals, platform-risk signals, hooks, and next-action ideas;
- instance-based design: code lives in the repo, your research data lives in a separate project folder.

## Quick start

### 1. Install

```bash
git clone https://github.com/AlekseiUL/youtube-intelligence-stack.git
cd youtube-intelligence-stack
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

You also need a working `yt-dlp` command. Installing from `requirements.txt` usually provides it. You can verify:

```bash
yt-dlp --version
```

### 2. Create a clean research instance

Keep generated evidence outside the code repo:

```bash
python run.py init-instance --project-root ~/youtube-intel-demo
```

This creates:

```text
~/youtube-intel-demo/
├── README.md
├── briefing.md
├── status.md
└── watchlists/
    ├── channels.yaml
    └── topics.yaml
```

Edit `watchlists/topics.yaml` and `watchlists/channels.yaml` for your niche.

### 3. Run a tiny public smoke

```bash
python run.py search \
  --project-root ~/youtube-intel-demo \
  --query "AI agents" \
  --limit-per-query 3 \
  --skip-watchlist-channels \
  --command-timeout-sec 30 \
  --continue-on-search-error

python run.py snapshots --project-root ~/youtube-intel-demo --limit 3
python run.py report --project-root ~/youtube-intel-demo
```

Reports are written under:

```text
~/youtube-intel-demo/data/reports/
```

## CLI

```bash
python run.py --help
```

Commands:

- `init-instance` — create a clean project instance with watchlist templates;
- `search` — search topics/channels and write search bundles;
- `transcripts` — collect subtitles/transcripts for surfaced videos;
- `comments` — collect comments for surfaced videos;
- `snapshots` — capture public metadata/metrics snapshots;
- `report` — build a weekly Markdown intelligence report;
- `full` — run a bounded end-to-end pipeline.

## Data safety

Generated evidence can become sensitive even when it starts from public sources. Do not commit your instance `data/` directory.

This repo intentionally excludes:

- private watchlists;
- cron schedules;
- generated transcripts/comments/snapshots/reports;
- cookies, browser state, API keys, `.env` files;
- internal workspace paths or operator notes.

## Example output

See:

- [`examples/weekly-report.example.md`](examples/weekly-report.example.md)
- [`examples/instance-layout.md`](examples/instance-layout.md)

## Canonical source

This project is maintained by Aleksei Ulianov / Sprut_AI.
Original repository: https://github.com/AlekseiUL/youtube-intelligence-stack

If you found this project mirrored, repackaged, or redistributed elsewhere, check this repository as the source of truth.

## Attribution

Where permitted by the applicable license, if you reuse, fork, modify, package, or publish this work, keep the original copyright and license notice and link back to the canonical repository.

## License

MIT. See [`LICENSE`](LICENSE).

---

# YouTube Intelligence Stack — RU

Локальный pipeline для YouTube-разведки по публичным источникам: ищет ролики, собирает metadata/transcripts/comments/snapshots и превращает это в weekly Markdown report.

Главное: это **чистая публичная версия**. В репозитории нет личных watchlist'ов, кронов, API-ключей, приватных путей и сгенерированных данных.

## Кому подойдёт

- авторам, которые следят за темами, болями и хуками в своей нише;
- предпринимателям и маркетологам, которые смотрят category narratives;
- researchers, которым нужен локальный evidence archive;
- AI-agent builders, которым удобнее файловый pipeline, а не очередной dashboard.

## Быстрый старт

```bash
git clone https://github.com/AlekseiUL/youtube-intelligence-stack.git
cd youtube-intelligence-stack
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py init-instance --project-root ~/youtube-intel-demo
python run.py search --project-root ~/youtube-intel-demo --query "AI agents" --limit-per-query 3 --skip-watchlist-channels
python run.py snapshots --project-root ~/youtube-intel-demo --limit 3
python run.py report --project-root ~/youtube-intel-demo
```

Сгенерированные данные лежат в project instance, а не в кодовом repo. Это специально: так безопаснее публиковать код и не таскать за собой приватную исследовательскую историю.
