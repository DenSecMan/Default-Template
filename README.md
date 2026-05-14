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
| `run_playbook` | Load a saved playbook by name and execute its steps with optional param substitution |
| `save_playbook` | Save a named investigation playbook to procedural memory for later recall |
| `web_search` | Mock web search returning placeholder results (development/testing) |
| `dangerous_demo` | High-risk demo tool (HITL-gated, development only) |
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

**Slash commands:** `/help`, `/status`, `/memory`, `/export`, `/quit` (or `/exit`)

## Logs

| File | Contents |
|---|---|
| `aisos.audit.log` | One JSON line per tool call (action, args, result, cost) |
| `aisos.debug.log` | Full application log (Azure SDK noise suppressed) |

## Architecture

AISOS is built around a **prompt → plan → tool** loop. Every user message goes through the same pipeline:

```
User input
  → Sanitizer          prompt-injection heuristics, secret redaction
  → Planner (LLM)      produces a JSON DAG of StepNodes
  → Orchestrator        iterates the DAG sequentially
      → Loop guard       aborts if step count exceeds max_steps
      → RBAC check       verifies the agent has the required scope
      → HITL gate        pauses for operator approval on high-risk tools
      → Tool.run()       executes the tool and returns structured output
  → Summarizer (LLM)   converts raw tool output to plain English
  → ChatLog widget      renders the answer in the TUI
```

### Core Components

**Planner** ([aisos/orchestration/planner.py](aisos/orchestration/planner.py))
Makes a single LLM call with the full tool catalog injected into the system prompt. The model returns a JSON object `{"plan": [...]}` — a list of `StepNode` objects, each naming a real tool (or `null` for direct-answer steps). A second `summarize()` call converts raw tool results into readable prose when no noop step already produced text.

**Orchestrator** ([aisos/orchestration/orchestrator.py](aisos/orchestration/orchestrator.py))
Drives the plan step by step. Noop steps (`tool=null`) short-circuit to `{"text": description}`. Tool steps go through RBAC → HITL → validate → `tool.run()`. After all steps, if nothing produced visible text, it hands the collected results to the planner's `summarize()`. All steps are traced on the `EventBus` so the TUI can show live status.

**Tool auto-discovery** ([aisos/tools/registry.py](aisos/tools/registry.py))
`ToolRegistry.discover("tools")` imports every module under `tools/`, finds all non-abstract `BaseTool` subclasses, and registers them by `name`. Adding a new `*_tool.py` makes the tool instantly available to both the planner and the TUI — no imports or registration required.

**Security layers**

| Layer | File | What it does |
|---|---|---|
| Sanitizer | [aisos/security/sanitizer.py](aisos/security/sanitizer.py) | Regex-screens input for injection patterns; redacts API keys/GUIDs from output |
| RBAC | [aisos/security/rbac.py](aisos/security/rbac.py) | Checks `agent_name` against the scope list in `config.toml [rbac]` before every tool call |
| HITL | [aisos/security/hitl.py](aisos/security/hitl.py) | Publishes `hitl.request` on the EventBus; waits for an operator `hitl.response` before running any `risk_level = "high"` tool |
| Loop guard | [aisos/orchestration/loop_guard.py](aisos/orchestration/loop_guard.py) | Raises `LoopGuardError` if `current_step` exceeds `config.toml max_steps` |

**Intelligence / Router** ([aisos/intelligence/router.py](aisos/intelligence/router.py))
Maps capability strings (`"plan"`, `"embed"`, `"default"`) to `(provider, model)` pairs using `config.toml [routing]`. Entries with `model = ""` fall back to `AZURE_OPENAI_DEPLOYMENT_CHAT` or `AZURE_OPENAI_DEPLOYMENT_EMBED` from `.env`. The `AzureOpenAIProvider` is the only concrete provider today.

**Memory** ([aisos/memory/](aisos/memory/))

| Layer | Backend | Purpose |
|---|---|---|
| `ShortTermMemory` | in-process list | Holds turns for the lifetime of one session |
| `SemanticMemory` | sqlite-vec cosine search | Long-term recall by similarity — stores and retrieves text + embeddings |
| `ProceduralMemory` | SQLite key-value | Stores named procedures / playbooks that can be recalled by key |

**Observability** ([aisos/observability/](aisos/observability/))
`CostTracker` accumulates token counts and USD cost per agent and per model using the rates in `config.toml [cost]`. `AuditLog` writes one JSON line to `aisos.audit.log` per tool call. `Tracer` emits `step.*` events on the `EventBus` so the TUI's Plan panel can show live step status.

**Configuration** ([aisos/config.py](aisos/config.py))
Pydantic-settings merges `.env` (anchored to the project root, not CWD) with `config.toml`. The process-level cached `get_config()` is the single source of truth — all tool code must use it rather than `os.environ.get()` directly.

---

## Usage

### Writing effective prompts

Be **specific and concrete**. The planner decomposes your request into tool calls, so the more detail you give, the better the plan it can produce.

| Less effective | More effective |
|---|---|
| `"Check this IP"` | `"Check 203.0.113.42 for abuse reports and known malware"` |
| `"Look at the logs"` | `"Query the last 1 hour of SecurityAlert where severity is High"` |
| `"Is this CVE bad?"` | `"Get the CVSS score and affected software for CVE-2024-12345"` |

Multi-step investigations work naturally — AISOS will plan and run them in sequence:

> "Check if IP 203.0.113.42 has abuse reports, then look up its reputation on VirusTotal, then query our logs for any connections to it in the last 24 hours."

### Improving system effectiveness

**Describe the Log Analytics schema first.** KQL queries fail silently if column names are wrong. Before running queries on an unfamiliar table, ask AISOS to describe it:

> "Describe the schema of the SecurityAlert table"

This uses `log_analytics_describe_table` which reads metadata only — no row scan and no cost.

**Increase `max_steps` for complex investigations.** `config.toml` defaults to 25 steps. A multi-indicator investigation (several IPs, then log correlation, then CVE lookups) can exceed this. Raise it in `config.toml`:

```toml
max_steps = 50
```

**Configure cost rates for accurate tracking.** Without rates the session panel shows $0.00. Add your deployment's per-1k-token pricing to `config.toml`:

```toml
[cost.gpt-4o]
input  = 0.005   # USD per 1k input tokens
output = 0.015   # USD per 1k output tokens
```

**Use separate chat and embed deployments.** If you have distinct deployments for chat and embeddings, set them explicitly in `.env`:

```ini
AZURE_OPENAI_DEPLOYMENT_CHAT=gpt-4o
AZURE_OPENAI_DEPLOYMENT_EMBED=text-embedding-3-small
```

This prevents the planner from accidentally routing embedding calls to a chat model.

**Add domain-specific tools.** The tool catalog is what the planner sees — a richer catalog means better plans. If you have internal APIs (CMDB, ticketing, EDR), create `tools/<name>_tool.py` and they appear automatically. See the `CLAUDE.md` template.

**Tune RBAC for least-privilege.** `config.toml [rbac]` controls which scopes the `default` agent is allowed. Restrict write/execute scopes if the agent should only read:

```toml
[rbac]
default = ["read"]
```

---

### Common problems and fixes

**"Planner referenced unknown tool"**
The planner named a tool that isn't registered — usually because it invented a name not in the catalog. This can't happen by design (the catalog is injected), but if you see it the tool file may have a syntax error that prevented auto-discovery.

Fix: check `aisos.debug.log` for an import error in `tools/`. Run `uv run pytest aisos/tools/registry_test.py` to verify discovery.

---

**`LoopGuardError: Step counter N exceeded max_steps=25`**
The plan required more steps than the configured budget.

Fix: raise `max_steps` in `config.toml`, or break the request into smaller questions.

---

**HITL approval modal appears and blocks**
Any tool with `risk_level = "high"` pauses and waits for operator confirmation. If you aren't watching the TUI, the session will hang until the `hitl_timeout_s` (default: no timeout).

Fix: approve or deny in the modal. To set a timeout so unattended sessions don't hang indefinitely, set `hitl_timeout_s` in the `Orchestrator` constructor (currently only configurable in code).

---

**`RBACDenied: Agent 'default' lacks required scope 'write'`**
The agent tried to call a tool whose `required_scope` isn't in its RBAC list.

Fix: add the scope to `config.toml [rbac]` if the action is intentional, or rephrase the request to avoid write operations.

---

**KQL query returns no rows or errors**
Common causes: wrong table name, wrong column name, time range too narrow, or workspace ID not set.

Fix: run `log_analytics_describe_table` first to verify column names. Check `AZURE_WORKSPACE_ID` is set and the Service Principal has *Log Analytics Reader* on the workspace.

---

**Threat-intel tools return nothing / are skipped**
Tools check for their API key at call time. If the key is blank they skip silently.

Fix: ensure the relevant key is set in `.env` (`VIRUSTOTAL_API_KEY`, `ABUSEIPDB_API_KEY`, `ALIENVAULT_OTX_API_KEY`, `NVD_API_KEY`). Restart AISOS after editing `.env`.

---

**Summarizer output is vague or misses data**
The `summarize()` call serialises all tool results as JSON. Very large result sets (thousands of rows from KQL) exceed the model's context window and the summary degrades.

Fix: narrow the KQL query with a tighter time range or a `| take N` clause, or add a noop step that explicitly formats what you want: *"Summarise only the top 5 results by severity."*

---

**Semantic memory search returns unrelated results**
`SemanticMemory` uses cosine similarity — if the embedding model differs between writes and reads, results will be nonsensical.

Fix: do not change `AZURE_OPENAI_DEPLOYMENT_EMBED` after seeding the database. If you need to switch models, delete `aisos.db` and reseed.

---

**TUI crashes with `'NoneType' object has no attribute 'get_height'`**
An instance attribute in a `Widget` subclass is shadowing a Textual internal (e.g. naming something `_nodes` or `_render`).

Fix: rename the attribute — use a suffix like `_node_status`, `_format_fn`, etc. See the *Critical Pitfalls* section in `CLAUDE.md`.

---

## Running Tests

```powershell
uv run pytest                                   # all tests
uv run pytest aisos/orchestration/planner_test.py   # one file
uv run pytest -k "test_runs_kql"                # one test by name
```
