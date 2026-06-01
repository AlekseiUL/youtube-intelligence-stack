# Instance layout

Create a research instance outside this repository:

```bash
python run.py init-instance --project-root ~/youtube-intel-demo
```

Expected layout:

```text
~/youtube-intel-demo/
├── README.md
├── briefing.md
├── status.md
├── watchlists/
│   ├── channels.yaml
│   └── topics.yaml
└── data/                  # generated later, do not commit
    ├── search/
    ├── transcripts/
    ├── comments/
    ├── snapshots/
    └── reports/
```

The repository contains reusable code. Your instance contains your research configuration and generated evidence.
