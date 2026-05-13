# AISOS

Agentic Intelligence Shell Operating System — a local-first, terminal-native multi-agent framework.

## Requirements

- Windows 11
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- Azure OpenAI credentials

## Quick start

```powershell
uv sync
Copy-Item .env.example .env  # fill in Azure OpenAI values
uv run aisos
```

See [`tasks/0001-prd-aisos-framework.md`](tasks/0001-prd-aisos-framework.md) for the v1.0 PRD.
