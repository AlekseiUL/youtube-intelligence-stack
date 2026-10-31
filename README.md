# YouTube Intelligence Stack

![YouTube Intelligence Stack promotional hero: bold black-and-yellow thumbnail with YouTube logo and product title.](docs/assets/youtube-intelligence-stack-hero.jpg)

Installable local-first CLI for YouTube public-source research: search public videos, collect transcripts/comments/metrics where available, and turn the evidence into weekly Markdown signal reports.

It is a collector plus deterministic report builder. It does not claim full autonomous intelligence, LLM synthesis, source-confidence scoring, or guaranteed YouTube coverage.

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
    A[Watchlists: topics/channels] --> B[youtube-intel search]
    B --> C[Metadata bundles]
    C --> D[Optional transcripts/comments]
    C --> E[Metric snapshots]
    D --> F[Weekly Markdown report]
    E --> F
```

Main capabilities:

- installable `youtube-intel` CLI;
- `doctor` environment check;
- clean project instances outside the code repo;
- topic-based YouTube search;
- channel watchlists;
- fallback/retry/throttle behavior around `yt-dlp`;
- transcript collection when subtitles are available;
- comment collection when YouTube exposes comments to `yt-dlp`;
- metric snapshots over time;
- weekly Markdown report with pains, migration/replacement signals, platform-risk signals, hooks, and next-action ideas;
- public-safe templates: `general`, `creator`, `competitor`, `ai-tools`.

## Quick start

Start with an isolated install and an offline check. You need Git and Python 3.10+ (CI tests 3.10–3.13); the examples use Python 3.12. Use a supported interpreter, not an older system Python. On Debian/Ubuntu, install the matching `python3-venv` OS package if venv creation reports that ensurepip is unavailable. Do not use `sudo pip` or `--break-system-packages`.

### Option A — install as a CLI from GitHub (recommended)

Use a new venv path for a fresh install. If the path below already exists, activate it to reuse it or choose another path; do not recreate an unrelated environment.

```bash
python3.12 --version
python3.12 -m venv "$HOME/.venvs/youtube-intel"
source "$HOME/.venvs/youtube-intel/bin/activate"
python -m pip install "git+https://github.com/AlekseiUL/youtube-intelligence-stack.git"
youtube-intel --help
youtube-intel doctor
youtube-intel init ~/youtube-intel-demo --template creator
youtube-intel doctor ~/youtube-intel-demo
youtube-intel report ~/youtube-intel-demo --out ~/youtube-intel-demo/offline-report.md
```

Package installation needs network access to GitHub and the package index. The subsequent help/doctor/init/report commands do not collect from YouTube or need cookies or credentials. Doctor should print `overall: ok`; init prints the instance path and creates `watchlists/topics.yaml` and `watchlists/channels.yaml`. The first report is `~/youtube-intel-demo/offline-report.md`. In a fresh instance it says `Evidence insufficient` because no videos have been collected: that is the expected offline result, not a research finding.

In a new terminal, run `source "$HOME/.venvs/youtube-intel/bin/activate"` before using the CLI; `deactivate` leaves the environment. If doctor reports a missing `yt-dlp`, confirm this venv is active and that package installation succeeded. [Offline verification](OFFLINE-VERIFICATION.md) reproduces this install outside the checkout.

### Option B — run from checkout

```bash
git clone https://github.com/AlekseiUL/youtube-intelligence-stack.git
cd youtube-intelligence-stack
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
youtube-intel doctor
youtube-intel init ~/youtube-intel-demo --template creator
```

You also need a working `yt-dlp` command. Installing the package normally provides it. Verify:

```bash
yt-dlp --version
```

## Project instances

Keep generated evidence outside the code repo:

```bash
youtube-intel init ~/youtube-intel-demo --template creator
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

Templates:

- `general` — broad public-source market radar;
- `creator` — hooks, audience pains, content formats;
- `competitor` — alternatives, switching, pricing complaints, platform risk;
- `ai-tools` — AI agent/tooling research.

## CLI commands

```bash
youtube-intel --help
youtube-intel doctor [project-root]
youtube-intel init <project-root> [--template creator|competitor|ai-tools|general]
youtube-intel search <project-root> [search args]
youtube-intel transcripts <project-root> [transcript args]
youtube-intel comments <project-root> [comment args]
youtube-intel snapshots <project-root> [snapshot args]
youtube-intel report <project-root> [report args]
youtube-intel full <project-root> [search args]
```

Useful filtering flags for weekly/fresh-signal workflows:

```bash
youtube-intel search ~/youtube-intel-demo --query "AI agents" --fresh-only --min-views 100 --min-comments 5
youtube-intel report ~/youtube-intel-demo --max-age-days 7 --min-views 100
```

- `--fresh-only` keeps recently published videos only (`7` days for search, current `--days` window for report). It is strict: videos with missing publication dates are excluded.
- `--max-age-days N` keeps only videos with a known publication date within `N` days.
- `--min-views` and `--min-comments` filter weak/empty results before reports.
- Search bundles and reports include filter accounting: candidates before filters, kept rows, old rows removed, undated rows removed, and threshold removals.

After the offline check, this optional end-to-end run contacts YouTube and collects public data:

```bash
youtube-intel full ~/youtube-intel-demo --safe --query "AI agents" --limit-per-query 3 --skip-watchlist-channels
```

`--safe` adds timeouts, small downstream limits, and continue-on-search-error behavior so first runs degrade visibly instead of hanging.

Legacy checkout syntax still works:

```bash
python run.py init-instance --project-root ~/youtube-intel-demo
python run.py search --project-root ~/youtube-intel-demo --query "AI agents"
```

## Tiny public smoke

```bash
youtube-intel search ~/youtube-intel-demo \
  --query "AI agents" \
  --limit-per-query 3 \
  --skip-watchlist-channels \
  --command-timeout-sec 30 \
  --continue-on-search-error

youtube-intel snapshots ~/youtube-intel-demo --limit 3
youtube-intel report ~/youtube-intel-demo
```

Reports are written under:

```text
~/youtube-intel-demo/data/reports/
```

## Known limitations

This is a best-effort research CLI, not a guaranteed data product.

- YouTube and `yt-dlp` can break or change behavior because of rate limits, `403`/`429` responses, region differences, extractor changes, removed videos, age gates, or metadata availability.
- Transcripts depend on subtitles being available to `yt-dlp`; comments depend on YouTube exposing them to the extractor.
- `--fresh-only` and `--max-age-days` require a known publication date; videos with missing dates are excluded in those modes.
- The report builder is deterministic. It does not perform LLM synthesis, confidence scoring, or source credibility assessment.
- Small samples are explicitly treated as insufficient evidence; collect more videos/comments before treating output as insight.

## Data safety

Generated evidence can become sensitive even when it starts from public sources. Do not commit your instance `data/` directory.

This repo intentionally excludes:

- private watchlists;
- cron schedules;
- generated transcripts/comments/snapshots/reports;
- cookies, browser state, API keys, `.env` files;
- internal workspace paths or operator notes.

## Development checks

From the checkout, create and activate a dedicated development venv first:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python scripts/repository_quality.py
python -m pytest -q
youtube-intel doctor
```

## Example output

See:

- [`examples/weekly-report.example.md`](examples/weekly-report.example.md)
- [`examples/instance-layout.md`](examples/instance-layout.md)

## Public links / Полезные ссылки

- YouTube: https://youtube.com/@alekseiulianov
- Telegram channel - Sprut AI: https://t.me/Sprut_AI
- Telegram chat - Sprut AI: https://t.me/+eH-qNIDmud8zNDZi
- AI Операционка: https://t.me/tribute/app?startapp=sJyg

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

Устанавливаемый локальный CLI для YouTube-разведки по публичным источникам: ищет ролики, собирает metadata/transcripts/comments/snapshots и превращает это в weekly Markdown report.

Главное: это **чистая публичная версия**. В репозитории нет личных watchlist'ов, кронов, API-ключей, приватных путей и сгенерированных данных.

## Кому подойдёт

- авторам, которые следят за темами, болями и хуками в своей нише;
- предпринимателям и маркетологам, которые смотрят category narratives;
- researchers, которым нужен локальный evidence archive;
- AI-agent builders, которым удобнее файловый pipeline, а не очередной dashboard.

## Быстрый старт

Нужны Git и Python 3.10+; CI проверяет версии 3.10–3.13, команды ниже используют Python 3.12. Не полагайтесь на старый системный Python. Если Debian/Ubuntu сообщает об отсутствии ensurepip, установите соответствующий системный пакет `python3-venv`. Не используйте `sudo pip` и `--break-system-packages`.

Для первой установки выберите свободный путь venv. Если указанный каталог уже существует, активируйте его для повторного использования или выберите другой путь; не пересоздавайте чужое окружение.

```bash
python3.12 --version
python3.12 -m venv "$HOME/.venvs/youtube-intel"
source "$HOME/.venvs/youtube-intel/bin/activate"
python -m pip install "git+https://github.com/AlekseiUL/youtube-intelligence-stack.git"
youtube-intel --help
youtube-intel doctor
youtube-intel init ~/youtube-intel-demo --template creator
youtube-intel doctor ~/youtube-intel-demo
youtube-intel report ~/youtube-intel-demo --out ~/youtube-intel-demo/offline-report.md
```

Установка скачивает пакет и зависимости через GitHub и индекс пакетов. Следующие команды help/doctor/init/report не обращаются к YouTube, не требуют cookies или учётных данных. Doctor должен вывести `overall: ok`; init — путь к проекту и создать `watchlists/topics.yaml` и `watchlists/channels.yaml`. Первый файл — `~/youtube-intel-demo/offline-report.md`. В новом проекте он содержит `Evidence insufficient`: видео ещё не собраны, это ожидаемый результат проверки, а не исследовательский вывод.

В новом терминале сначала выполните `source "$HOME/.venvs/youtube-intel/bin/activate"`; выйти из окружения можно командой `deactivate`. Если doctor не видит `yt-dlp`, проверьте активацию venv и результат установки пакета. Воспроизводимая проверка установки описана в [Offline verification](OFFLINE-VERIFICATION.md).

После локальной проверки можно отдельно запустить сбор публичных данных — эта команда уже обращается к YouTube:

```bash
youtube-intel full ~/youtube-intel-demo --safe --query "AI agents" --limit-per-query 3 --skip-watchlist-channels
```

Сгенерированные данные лежат в project instance, а не в кодовом repo. Это специально: так безопаснее публиковать код и не таскать за собой приватную исследовательскую историю.

## Полезные ссылки / ресурсы

- YouTube: https://youtube.com/@alekseiulianov
- Telegram-канал Sprut AI: https://t.me/Sprut_AI
- Чат Telegram-канала Sprut AI: https://t.me/+eH-qNIDmud8zNDZi
- AI Операционка: https://t.me/tribute/app?startapp=sJyg
