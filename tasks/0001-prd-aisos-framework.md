# PRD: AISOS Framework Shell — v1.0

## Introduction / Overview

AISOS (Artificial Intelligence Sick Operating System) is a local, Python-based agentic desktop system. It provides a structured runtime for orchestrating multiple LLM-powered agents that can plan, reason, remember, and execute tools in coordinated workflows.

Version 1 delivers the **framework shell** — all six architectural layers wired together with a working end-to-end agent loop, a Terminal/TUI interface, and a pluggable tool system. No production-grade tool integrations ship in v1; the goal is a solid foundation that any future integration (e.g., Microsoft Defender XDR, browser automation) can be dropped into without rearchitecting.

---

## Goals

1. Implement all six architectural layers (Intelligence, Memory, Orchestration, Tool Integration, Security/Guardrails, Observability) as interoperable Python modules.
2. Deliver an end-to-end agent loop: user prompt → planner → agent graph → tool call → result displayed in TUI.
3. Support API-only LLM access via a configurable router. **Azure OpenAI is the primary provider for v1**; the router architecture must allow additional providers (e.g., Anthropic, native OpenAI) to plug in without core changes.
4. Provide a pluggable tool interface so new integrations can be registered without modifying core framework code.
5. Run reliably on a single Windows machine with no external infrastructure dependencies (no Docker, no hosted databases required for v1).

---

## User Stories

- As a **cybersecurity analyst**, I want to type a natural-language threat hunting request and have AISOS autonomously plan and execute the investigation steps, so I can focus on decision-making rather than manual query construction.
- As a **developer**, I want to register a new tool integration in one file and have the agent router discover and use it automatically, so I can extend the OS without touching framework internals.
- As a **SOC team member**, I want every agent action logged with a timestamp and agent identity, so I can audit what the system did during an incident response.
- As any user, I want the system to pause and ask for my explicit approval before any action flagged as high-risk, so destructive operations never happen without my consent.

---

## Functional Requirements

### 1. Intelligence & Routing Layer
1.1 The system must implement a `BaseLLMProvider` abstract interface so multiple LLM backends can be plugged in. **Azure OpenAI must be the first concrete provider implemented in v1** (using the `openai` SDK's `AzureOpenAI` / `AsyncAzureOpenAI` client).  
1.2 The Azure OpenAI provider must read the following from `.env`: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, and per-model deployment names (e.g., `AZURE_OPENAI_DEPLOYMENT_CHAT`, `AZURE_OPENAI_DEPLOYMENT_EMBED`).  
1.3 An LLM Router must select the appropriate model per agent task based on a configurable capability/cost profile defined in `config.toml`. v1 routes all requests to the Azure OpenAI provider but the routing layer must not assume a single provider.  
1.4 A Prompt Manager must assemble system prompts from modular templates, injecting agent persona, task context, and available tool descriptions automatically.  
1.5 A Token Controller must truncate or summarize context when the token count approaches the configured model's context limit.  
1.6 LLM responses must stream token-by-token via the async streaming API of the Azure OpenAI SDK.  

### 2. Memory & State Subsystem
2.1 Short-term memory must persist the current task's step history and conversational context within a running session using an in-memory structure, with snapshot persistence to SQLite at session checkpoints.  
2.2 Long-term semantic memory must store and retrieve text chunks using **SQLite** as the sole storage engine. Vector similarity search must use the `sqlite-vec` extension (loadable via `sqlite3.enable_load_extension`).  
2.3 Procedural memory must persist named workflow recipes in a dedicated SQLite table (`recipes`) so successful agent plans can be reused across sessions.  
2.4 All Memory & State Subsystem data (short-term snapshots, embeddings, recipes, audit references) must live in a single SQLite database file. Path resolved from `AISOS_DB_PATH` env var; default `./aisos.db` at project root.  
2.5 Vector embeddings stored in `sqlite-vec` must be 1536-dimensional, generated via the Azure OpenAI deployment of `text-embedding-3-small`.  

### 3. Execution & Orchestration Engine
3.1 A Planner agent must decompose a user request into a Directed Acyclic Graph (DAG) of micro-tasks using LangGraph.  
3.2 An Agent Registry must maintain a list of available agent types, their descriptions, and their assigned tools.  
3.3 An Event Bus must allow agents to emit and subscribe to named events using an in-process pub/sub mechanism (no external broker required in v1).  
3.4 The orchestration engine must detect and break infinite loops by enforcing a configurable maximum step count per workflow.  

### 4. Tool Integration Layer
4.1 A Tool Interface must define a standard abstract base class (`BaseTool`) with `name`, `description`, `input_schema`, and `run(input) -> output` contract.  
4.2 A Tool Registry must auto-discover and register any class implementing `BaseTool` found in the `tools/` directory at startup.  
4.3 v1 must ship two built-in stub tools: `EchoTool` (returns its input, for testing) and `WebSearchTool` (stub that returns mock data).  
4.4 A Sandbox Runtime must execute arbitrary Python code snippets in a restricted subprocess environment with a configurable timeout.  

### 5. Security, Guardrails & Governance
5.1 A HITL (Human-in-the-Loop) Gatekeeper must intercept any tool call tagged `risk_level: high` and display an approval prompt in the TUI before execution.  
5.2 Input sanitization must screen incoming user prompts for prompt-injection patterns (basic keyword and structural heuristics) and log a warning if detected.  
5.3 Output sanitization must redact strings matching common secret patterns (API keys, tokens) before displaying agent output.  
5.4 An RBAC module must associate each agent type with a permission scope list; tool calls outside that scope must be blocked and logged.  

### 6. Observability, Logging & Auditing
6.1 All agent actions must be logged as structured JSON to a local log file, including: timestamp, agent name, action type, input summary, output summary, and token cost.  
6.2 A Cost Tracker must accumulate token usage per agent per session and display a session summary on exit.  
6.3 An Execution Trace Visualizer must render a live, text-based step graph in the TUI showing the current workflow state (pending, running, complete, failed nodes).  
6.4 Logs must be append-only and must not be modified or deleted by any agent action.  

### 7. Terminal / TUI Interface
7.1 The TUI must present a persistent chat input at the bottom of the screen and a scrollable output pane above it (using `Textual` or `Rich`).  
7.2 HITL approval prompts must render as modal overlays with `[APPROVE]` and `[CANCEL]` options navigable by keyboard.  
7.3 The execution trace graph (Requirement 6.3) must update in real time within a dedicated TUI panel.  
7.4 A `/help` command must list all available slash commands and registered tools.  
7.5 A `/status` command must display the Agent Registry contents and current session cost.  

---

## Non-Goals (Out of Scope for v1)

- No production Microsoft Defender XDR, Playwright, or external API integrations.
- No graphical (GUI) desktop application — TUI only.
- No multi-user or networked deployment — single local machine.
- No local LLM support (Ollama, llama.cpp) — API-only in v1.
- No cloud sync, remote logging, or external observability platforms (Datadog, etc.).
- No macOS or Linux support — Windows only.

---

## Design Considerations

- Use **LangGraph** as the orchestration graph engine.
- Use **SQLite** (via `sqlite3` stdlib + `sqlite-vec` extension) as the single storage backend for all memory layers — short-term snapshots, vector embeddings, procedural recipes, and audit trail references.
- Use **Azure OpenAI** as the primary LLM provider via the official `openai` Python SDK (`AsyncAzureOpenAI` client). Chat completions and embeddings both route through Azure OpenAI deployments in v1.
- Use **Pydantic v2** for all agent input/output schema validation.
- Use **Textual** for the TUI framework.
- Use **python-dotenv** to load API keys and secrets from a `.env` file at the project root. `.env` must be listed in `.gitignore`.
- Non-secret configuration (model routing rules, cost profiles, RBAC scopes) lives in `config.toml`.
- LLM responses must stream token-by-token from provider SDK into the TUI output pane via `asyncio` async generators.
- All modules should be importable independently so they can be unit-tested in isolation.

---

## Technical Considerations

- Python 3.11+ required (uses `tomllib` stdlib, match statements, `asyncio` task groups).
- Project managed with **`uv`** for dependency isolation (`uv.lock` committed, `uv run` for entrypoints).
- All async I/O should use `asyncio`; no mixing of threading and async event loops.
- The `tools/` directory must be scannable at startup without importing all modules eagerly — use lazy imports to avoid slow startup.
- Windows-specific: use `WindowsProactorEventLoopPolicy` for asyncio subprocess compatibility.
- Embeddings generated via Azure OpenAI deployment of `text-embedding-3-small` (1536 dim). `sqlite-vec` vector tables sized accordingly.
- `aisos.db` path resolved from `AISOS_DB_PATH` env var, defaulting to `./aisos.db` at project root.

---

## Success Metrics

- A user can type a natural-language prompt and receive a structured agent response with at least one tool call result displayed in the TUI.
- The HITL gatekeeper fires and blocks execution on at least one test workflow containing a `risk_level: high` tool.
- The structured JSON audit log is written to disk and contains entries for every agent action in the session.
- A new tool can be added by a developer by creating a single file in `tools/` with no changes to any other file.
- All unit tests pass on a clean Windows machine with `uv run pytest`.

---

## Resolved Decisions

1. **Streaming:** LLM Router streams token-by-token to the TUI in v1.
2. **Memory backend:** SQLite only (with `sqlite-vec` extension for vector similarity). ChromaDB removed from scope.
3. **API keys:** Stored in `.env` file at project root, loaded via `python-dotenv`. `.env` is gitignored.
4. **TUI framework:** Textual.
5. **Primary LLM provider:** Azure OpenAI (`AsyncAzureOpenAI` from `openai` SDK). Router architecture remains provider-agnostic for future Anthropic/OpenAI/Voyage plug-ins.
6. **Embedding model:** Azure OpenAI deployment of `text-embedding-3-small` (1536 dim).
7. **DB path:** `AISOS_DB_PATH` env var, default `./aisos.db`.
8. **Package manager:** `uv` (lockfile committed).

## Open Questions

None — all resolved.
