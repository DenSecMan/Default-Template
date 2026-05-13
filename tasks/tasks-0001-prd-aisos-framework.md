# Tasks: AISOS Framework Shell — v1.0

Source PRD: [0001-prd-aisos-framework.md](0001-prd-aisos-framework.md)

## Relevant Files

### Project root
- `pyproject.toml` — uv project metadata, deps, entry script.
- `.python-version` — pins interpreter to 3.11.
- `uv.lock` — lockfile (committed).
- `.gitignore` — excludes `.env`, `*.db`, `.venv/`, `__pycache__/`.
- `.env.example` — Azure OpenAI placeholders + `AISOS_DB_PATH`.
- `config.toml` — routing rules, RBAC scopes, cost profile.
- `README.md` — install + run instructions.

### Core package (`aisos/`)
- `aisos/__init__.py`
- `aisos/__main__.py` — Textual app entry point; sets Windows event loop policy.
- `aisos/config.py` — `.env` + `config.toml` loader (pydantic-settings).
- `aisos/logging_setup.py` — structured JSON logger w/ contextual filters.

### Memory & State (`aisos/memory/`)
- `db.py` — SQLite connection mgr, WAL mode, `sqlite-vec` extension load, schema migrations.
- `short_term.py` — in-mem deque + checkpoint-to-SQLite.
- `semantic.py` — long-term vector store via `sqlite-vec` similarity search.
- `procedural.py` — workflow recipe CRUD.
- `embeddings.py` — Azure OpenAI `text-embedding-3-small` client (1536 dim).
- `*_test.py` — unit tests for each module.

### Intelligence & Routing (`aisos/intelligence/`)
- `base.py` — `BaseLLMProvider` abstract (chat_complete, chat_stream, embed).
- `azure_openai.py` — `AzureOpenAIProvider` using `AsyncAzureOpenAI`.
- `router.py` — capability/cost-based provider+model selection.
- `prompt_manager.py` — modular template assembler.
- `token_controller.py` — tiktoken counting + truncation/summarization.
- `*_test.py` — unit tests + mock provider fixture.

### Orchestration (`aisos/orchestration/`)
- `state.py` — LangGraph Pydantic state model.
- `planner.py` — DAG planner agent.
- `registry.py` — Agent Registry (type, skills, scope).
- `event_bus.py` — in-process asyncio pub/sub.
- `*_test.py` — unit tests.

### Tools (`aisos/tools/` + `tools/`)
- `aisos/tools/base.py` — `BaseTool` ABC (name, description, input_schema, risk_level, run).
- `aisos/tools/registry.py` — auto-discovery scanner for `tools/` dir.
- `aisos/tools/sandbox.py` — subprocess sandbox runtime w/ timeout.
- `tools/echo_tool.py` — `EchoTool` stub.
- `tools/web_search_tool.py` — `WebSearchTool` stub (mock data).
- `*_test.py` — unit tests.

### Security (`aisos/security/`)
- `hitl.py` — risk-level interceptor + TUI approval await.
- `sanitizer.py` — input prompt-injection heuristics + output secret redaction.
- `rbac.py` — agent scope -> tool permission check.
- `*_test.py` — unit tests.

### Observability (`aisos/observability/`)
- `audit_log.py` — append-only JSON log writer.
- `cost_tracker.py` — per-agent/session token + USD accumulator.
- `trace.py` — execution trace event emitter.
- `*_test.py` — unit tests.

### TUI (`aisos/tui/`)
- `app.py` — Textual `App` subclass; main layout (input, output, trace panes).
- `widgets.py` — streaming output renderer, HITL modal, trace graph widget.
- `commands.py` — slash command dispatcher (`/help`, `/status`, `/quit`).

### Tests
- `tests/test_e2e.py` — end-to-end: prompt -> EchoTool -> result; HITL block + approve flow.

### Notes
- Greenfield. No existing code to preserve.
- Unit tests alongside source files (e.g., `store.py` ↔ `store_test.py`).
- Test runner: `uv run pytest`.
- Python 3.11+, Windows-only, `uv`-managed.

## Tasks

- [x] 1.0 Project scaffolding & configuration baseline
  - [x] 1.1 `uv init` project, pin Python 3.11+, create `pyproject.toml` w/ entry script `aisos = "aisos.__main__:main"`.
  - [x] 1.2 Add deps: `openai`, `langgraph`, `textual`, `pydantic>=2`, `pydantic-settings`, `python-dotenv`, `sqlite-vec`, `tiktoken`, `pytest`, `pytest-asyncio`.
  - [x] 1.3 Write `.gitignore` (Python defaults + `.env`, `*.db`, `*.db-journal`, `*.db-wal`, `*.db-shm`, `.venv/`).
  - [x] 1.4 Create `.env.example`: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_DEPLOYMENT_CHAT`, `AZURE_OPENAI_DEPLOYMENT_EMBED`, `AISOS_DB_PATH`.
  - [x] 1.5 Create `config.toml` skeleton: `[routing]`, `[rbac]`, `[cost]` sections.
  - [x] 1.6 Create dir tree under `aisos/` + `tools/` + `tests/` with empty `__init__.py` files.
  - [x] 1.7 `aisos/config.py` — pydantic-settings loader merging `.env` + `config.toml`.
  - [x] 1.8 `aisos/logging_setup.py` — JSON formatter, contextual filter (thread_id, agent_name).
  - [x] 1.9 `aisos/__main__.py` — `main()` sets `WindowsProactorEventLoopPolicy`, launches stub Textual app.
  - [x] 1.10 Smoke test: `uv run aisos` launches empty TUI without error.

- [x] 2.0 Memory & State subsystem (SQLite + `sqlite-vec`)
  - [x] 2.1 `db.py` — `get_connection()` opens path from `AISOS_DB_PATH`, enables WAL, loads `sqlite-vec`.
  - [x] 2.2 Schema migrations: `sessions`, `short_term_snapshots`, `vec_embeddings` (vec0 virtual table, 1536 dim), `recipes`, `audit_log_index` tables.
  - [x] 2.3 `short_term.py` — in-memory `deque[Step]` + `checkpoint()` writes serialized history to SQLite.
  - [x] 2.4 `embeddings.py` — async embed via `AsyncAzureOpenAI.embeddings.create`, batch support.
  - [x] 2.5 `semantic.py` — `add(text, metadata)` embeds + inserts; `search(query, k)` returns top-k by cosine.
  - [x] 2.6 `procedural.py` — `save_recipe(name, plan_json)`, `load_recipe(name)`, `list_recipes()`.
  - [x] 2.7 Unit tests: migration idempotency, snapshot round-trip, similarity search returns ordered results, recipe CRUD.

- [ ] 3.0 Intelligence & Routing layer
  - [ ] 3.1 `intelligence/base.py` — `BaseLLMProvider` ABC: `async chat(messages, **kwargs)`, `async stream(messages, **kwargs) -> AsyncIterator[str]`, `async embed(texts) -> list[list[float]]`.
  - [ ] 3.2 `intelligence/azure_openai.py` — concrete provider using `AsyncAzureOpenAI`; reads endpoint/key/version/deployments from config.
  - [ ] 3.3 `intelligence/router.py` — `route(task_capability)` -> provider+model from `config.toml [routing]` rules.
  - [ ] 3.4 `intelligence/prompt_manager.py` — load templates from `aisos/prompts/*.md`; inject persona, tool catalog, task context.
  - [ ] 3.5 `intelligence/token_controller.py` — `count(text, model)` via tiktoken; `trim(messages, max_tokens)` evicts oldest non-system.
  - [ ] 3.6 Streaming contract: provider `stream()` yields delta strings; router preserves async iteration.
  - [ ] 3.7 Unit tests: mock provider, router selection logic, token trim correctness, prompt template variable substitution.

- [ ] 4.0 Execution, Orchestration & Tool Integration
  - [ ] 4.1 `orchestration/state.py` — Pydantic `AgentState`: `prompt`, `plan: list[StepNode]`, `current_step`, `history`, `results`.
  - [ ] 4.2 `orchestration/planner.py` — LangGraph node: prompts LLM via router for DAG, parses JSON plan via Pydantic.
  - [ ] 4.3 `orchestration/registry.py` — `AgentRegistry`: register/lookup agent specs (name, description, allowed_tool_scopes).
  - [ ] 4.4 `orchestration/event_bus.py` — asyncio-native pub/sub: `publish(event)`, `subscribe(topic) -> AsyncIterator`.
  - [ ] 4.5 Step counter guard: orchestration loop aborts if `current_step > config.max_steps`, raises `LoopGuardError`.
  - [ ] 4.6 `tools/base.py` — `BaseTool` ABC: class attrs `name`, `description`, `input_schema: type[BaseModel]`, `risk_level: Literal["low","medium","high"]`, `required_scope: str`; method `async run(input)`.
  - [ ] 4.7 `tools/registry.py` — scan `tools/` at startup via `importlib`, collect `BaseTool` subclasses lazily.
  - [ ] 4.8 `tools/echo_tool.py` — `EchoTool` returns input verbatim; risk_level=low.
  - [ ] 4.9 `tools/web_search_tool.py` — `WebSearchTool` returns hard-coded mock results; risk_level=low.
  - [ ] 4.10 `tools/sandbox.py` — `run_python(code, timeout_s)` via `subprocess.run` w/ `-I` isolated mode + cwd tempdir + timeout.
  - [ ] 4.11 Unit tests: planner JSON parse, registry lookup, event bus delivery order, loop guard fires, tool discovery scans `tools/`, sandbox timeout kills child.

- [ ] 5.0 Security, Guardrails & Observability
  - [ ] 5.1 `security/hitl.py` — `gate(tool_call)`: if `risk_level=="high"`, publish `hitl.request` event, await `hitl.response`; raises if denied.
  - [ ] 5.2 `security/sanitizer.py` — `screen_input(text)` regex/keyword scan (e.g., "ignore previous", "system:" injection); logs warn.
  - [ ] 5.3 `security/sanitizer.py` — `redact_output(text)` regex redacts `sk-…`, `AZURE…`, GUID-like tokens.
  - [ ] 5.4 `security/rbac.py` — `check(agent_name, tool_scope)`: blocks + logs if scope not in agent's allowed_scopes from `config.toml`.
  - [ ] 5.5 `observability/audit_log.py` — append-only JSONL writer to `aisos.audit.log`; entry: timestamp, agent, action, input_summary, output_summary, tokens, cost_usd.
  - [ ] 5.6 `observability/cost_tracker.py` — `record(model, in_tokens, out_tokens)`; pricing table in `config.toml [cost]`; `summary()` returns per-agent + total USD.
  - [ ] 5.7 `observability/trace.py` — publishes `trace.node` events with state (pending/running/complete/failed) to event bus for TUI consumption.
  - [ ] 5.8 Unit tests: HITL deny path raises, sanitizer redacts secrets, RBAC blocks out-of-scope, cost math correct, audit log append-only (no overwrite).

- [ ] 6.0 Terminal/TUI interface & end-to-end integration
  - [ ] 6.1 `tui/app.py` — Textual `App` w/ Grid layout: top `TracePanel`, middle `OutputPane`, bottom `Input` widget.
  - [ ] 6.2 `tui/widgets.py` — `StreamingOutput`: consumes async iterator of tokens, appends to scrollable buffer.
  - [ ] 6.3 `tui/widgets.py` — `HITLModal`: shows tool call summary + `[APPROVE] [CANCEL]` buttons; emits `hitl.response`.
  - [ ] 6.4 `tui/widgets.py` — `TracePanel`: subscribes to `trace.node` events; renders text-based DAG w/ status glyphs.
  - [ ] 6.5 `tui/commands.py` — dispatch `/help` (lists slash commands + registered tools), `/status` (Agent Registry + session cost), `/quit`.
  - [ ] 6.6 Wire: input text -> sanitizer -> router -> planner -> orchestrator -> tool calls (via HITL+RBAC) -> stream output to TUI.
  - [ ] 6.7 `tests/test_e2e.py` — async test: feed prompt that triggers `EchoTool`, assert tool result rendered in output pane.
  - [ ] 6.8 `tests/test_e2e.py` — async test: tool flagged `risk_level=high` triggers HITLModal; simulate approve -> tool runs; simulate cancel -> tool blocked.
  - [ ] 6.9 Manual smoke: clean Windows machine, fresh `uv sync`, set `.env`, `uv run aisos` -> type prompt -> see end-to-end loop complete.
