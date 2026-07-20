# Bank Statement Parser

Starter skeleton for a multilingual bank statement PDF parser.

The project is organized around one shared Python core that can later power both a desktop app and a web app.

## Quick Start

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

## Key Docs

- `PROJECT_STARTER_DOC.md` - wholemap, IDE prompts, team ownership, sprint backlog.
- `docs/roadmap.md` - cleaned roadmap from the v2 plan.

## Owners

- Mohsin: parsing engine.
- Umer: validation and data.
- Talha: apps, export, localization.
