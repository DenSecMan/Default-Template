# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the TUI
uv run aisos

# Run all tests
uv run pytest

# Run a single test file
uv run pytest aisos/orchestration/planner_test.py

# Run a single test by name
uv run pytest -k "test_runs_kql_and_serialises_rows"

# Add a dependency
uv add <package>
```

All logging during TUI runtime goes to `aisos.debug.log` (not stderr). Azure SDK HTTP noise is suppressed at WARNING. The audit trail is `aisos.audit.log` (JSON, one entry per tool call).

## Architecture

The system is a prompt → plan → tool loop rendered in a Textual TUI.

```
User input
  → Planner (LLM)         aisos/orchestration/planner.py
  → DAG of StepNodes      aisos/orchestration/state.py
  → Orchestrator           aisos/orchestration/orchestrator.py
      → RBAC check         aisos/security/rbac.py
      → HITL gate          aisos/security/hitl.py   (high-risk tools only)
      → Tool.run()         tools/*.py
  → Planner.summarize()   (if no noop steps produced text)
  → ChatLog widget         aisos/tui/widgets.py
```

**Config** (`aisos/config.py`): pydantic-settings reads `.env` anchored to the project root via `Path(__file__).parent.parent` — not CWD. This matters when running from outside the project directory. `get_config()` is process-level cached. All tool code must use `get_config().settings.*` rather than `os.environ.get()` directly.

**Planner** (`aisos/orchestration/planner.py`): Makes one LLM call to produce a JSON DAG (`{"plan": [StepNode, ...]}`). The full tool catalog is injected into the system prompt so the model can only name real tools. A second `summarize()` call converts raw tool output into plain-English when no noop step provided text.

**Orchestrator** (`aisos/orchestration/orchestrator.py`): Iterates the plan sequentially. Noop steps (`tool=null`) return `{"text": description}` directly; tool steps call `tool.run()`. After all steps, if `output_chunks` is empty, calls `planner.summarize()` with the tool results dict.

**Tool auto-discovery** (`aisos/tools/registry.py`): `ToolRegistry.discover("tools")` imports every module under `tools/`, instantiates each non-abstract `BaseTool` subclass, and registers it by `name`. Drop a new `*_tool.py` in `tools/` — it appears automatically in the running app and the planner's catalog.

**TUI** (`aisos/tui/app.py`, `aisos/tui/widgets.py`): Two-column layout — `ChatLog` (2fr) + sidebar (`PlanPanel`, `SessionPanel`, `ToolPanel`). The `#input-area` is bottom-docked. On submit, the orchestrator runs as a background `asyncio.create_task` with a *Thinking…* placeholder; the input is disabled until the task completes. The `CommandPalette` (above the input) activates when the user types `/`.

**Memory** (`aisos/memory/`): `ShortTermMemory` (in-process list), `SemanticMemory` (sqlite-vec cosine search), `ProceduralMemory` (SQLite key-value). sqlite-vec requires `WHERE v.embedding MATCH ? AND k = ?` — not SQL `LIMIT`.

**Intelligence** (`aisos/intelligence/`): `AzureOpenAIProvider` is the only concrete provider. `model` arg in `chat()` falls back to `_chat_deployment` when empty/None — routing entries in `config.toml` should leave `model = ""` to pick up `AZURE_OPENAI_DEPLOYMENT_CHAT` from `.env`. `Router` maps capability strings (`"plan"`, `"embed"`, `"default"`) to providers via `config.toml [routing]`.

**HITL** (`aisos/security/hitl.py`): Tools with `risk_level = "high"` are paused; a `HITLModal` is pushed over the TUI. The modal publishes the approval event back to `EventBus` on confirm/cancel.

## Writing a New Tool

Create `tools/<name>_tool.py`:

```python
from pydantic import BaseModel, Field
from aisos.config import get_config
from aisos.tools.base import BaseTool

class MyInput(BaseModel):
    value: str = Field(..., description="...")

class MyTool(BaseTool):
    name = "my_tool"               # used by the planner — must be unique
    description = "..."            # injected into planner system prompt
    input_schema = MyInput
    risk_level = "low"             # "low" | "medium" | "high"
    required_scope = "read"        # checked against agent RBAC in config.toml

    async def run(self, input: MyInput) -> dict:
        key = get_config().settings.my_api_key   # never os.environ directly
        ...
```

For async HTTP: use `httpx.AsyncClient`. For Azure SDK async clients, use `async with` on both the credential and the client to avoid unclosed aiohttp session warnings.

Add new API key env vars to `Settings` in `aisos/config.py` alongside a matching line in `.env.example`.

## Critical Pitfalls

**Textual attribute shadowing**: Never name instance attributes `_nodes`, `_render`, or other names that shadow `Widget` internals. Use `_node_status`, `_redraw`, `_format`, etc. Symptoms are `'NoneType' object has no attribute 'get_height'` or `'dict' object has no attribute '_clear'` during layout.

**Monkeypatching and import binding**: In test files that patch functions in a tool module, always import the module itself and patch via `monkeypatch.setattr(module, "_build_client", ...)`. A `from module import _build_client` copy is unaffected by the patch.

**Rich markup in error messages**: Pydantic validation errors contain `[type=literal_error, ...]` which Textual's `Static` widget parses as Rich markup and crashes. All plain-text content passed to `Static` should be wrapped with `rich.markup.escape()` (already done in `ChatMessage`).

**Planner indicator_type consistency**: All tools that accept an `indicator_type` field for threat-intel lookups use the same literal set: `"ip"`, `"domain"`, `"url"`, `"file"`. The VirusTotal endpoint maps `"ip"` → `/ip_addresses/` internally.
