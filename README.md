# AISOS

**Agentic Intelligence Shell Operating System** — a terminal-native multi-agent framework for security operations. Ask questions in plain English; AISOS plans the work, runs the tools, and summarises the results.

![Platform](https://img.shields.io/badge/platform-Windows%2011-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

## Features

- **Natural-language interface** — chat-style TUI powered by [Textual](https://textual.textualize.io/)
- **Agentic planning** — Azure OpenAI decomposes requests into a tool DAG automatically
- **Azure Sentinel / Log Analytics** — run KQL queries and describe table schemas
- **Threat intelligence** — VirusTotal, AbuseIPDB, AlienVault OTX, NVD CVE lookups
- **Human-in-the-loop** — high-risk tools require operator approval before execution
- **Cost tracking** — token counts and USD cost shown live in the sidebar
- **Extensible** — drop a new `*_tool.py` in `tools/` and it appears instantly

## Requirements

- Windows 11
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- Azure OpenAI deployment (chat + embeddings)

## Quick Start

```powershell
uv sync
Copy-Item .env.example .env   # then fill in your credentials
uv run aisos
```

## Configuration

### `.env`

```ini
# Azure OpenAI (required)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT=your-deployment-name   # used for chat + embeddings

# Azure Sentinel / Log Analytics (optional)
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_WORKSPACE_ID=

# Threat intelligence (optional — omit keys to skip those tools)
VIRUSTOTAL_API_KEY=
ABUSEIPDB_API_KEY=
ALIENVAULT_OTX_API_KEY=
NVD_API_KEY=
```

The `.env` is loaded relative to the project root regardless of where you run `uv run aisos` from.

### `config.toml`

Controls routing, RBAC, token cost rates, and the max step limit. Defaults work out of the box — the `model = ""` entries in `[routing]` fall back to `AZURE_OPENAI_DEPLOYMENT`.

## Tools

| Tool | Description |
|---|---|
| `log_analytics_query` | Execute KQL against an Azure Log Analytics workspace |
| `log_analytics_describe_table` | List columns and types for a Log Analytics table (cheap, no row scan) |
| `virustotal_lookup` | IP, domain, URL, or file hash reputation via VirusTotal v3 |
| `abuseipdb_check` | IP abuse-confidence score and report history |
| `alienvault_lookup` | OTX pulse count, malware families, and geo data |
| `nvd_cve_lookup` | CVE details and CVSS scores from NIST NVD |
| `echo` | Echo input back (development/testing) |

### Adding a Tool

Create `tools/<name>_tool.py` with a `BaseTool` subclass. The tool is auto-discovered on next startup — no registration needed. See `CLAUDE.md` for the full template.

## TUI

| Area | Description |
|---|---|
| Main pane | Scrollable chat history |
| Plan panel | Live step status (pending / running / complete / failed) |
| Session panel | Deployment name, running cost, token counts, step count |
| Tools panel | All registered tools with risk levels |
| Input | Type a prompt or `/command`; press `/` for the command palette |

**Keyboard shortcuts**

| Key | Action |
|---|---|
| `Ctrl+Q` | Quit |
| `Ctrl+L` | Clear chat |
| `/` | Open command palette |
| `↑` / `↓` | Navigate palette |
| `Tab` | Complete selected command |
| `Esc` | Close palette |

**Slash commands:** `/help`, `/status`, `/quit`

## Logs

| File | Contents |
|---|---|
| `aisos.audit.log` | One JSON line per tool call (action, args, result, cost) |
| `aisos.debug.log` | Full application log (Azure SDK noise suppressed) |

## Running Tests

```powershell
uv run pytest                                   # all tests
uv run pytest aisos/orchestration/planner_test.py   # one file
uv run pytest -k "test_runs_kql"                # one test by name
```
