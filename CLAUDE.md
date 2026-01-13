# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A multi-agent research system demonstrating **FileSystem-based Context Engineering** using LangChain's DeepAgents framework. The system includes:
- **Python DeepAgents**: LangChain-based multi-agent orchestration with web research capabilities
- **Context Engineering Module**: Experimental platform with 5 context optimization strategies
- **Rust `rig-deepagents`**: Pregel-inspired graph execution runtime using Rig framework

## Development Commands

### Python Backend

```bash
# Install dependencies (uses uv package manager)
uv sync

# Start LangGraph development server (API on localhost:2024)
langgraph dev

# Linting and formatting
uv run ruff check .
uv run ruff format .

# Type checking
uv run mypy .

# Run tests
uv run pytest tests/                      # All tests
uv run pytest tests/test_agent.py -v      # Single file
uv run pytest -k "test_researcher" -v     # Pattern match
```

### Frontend UI (deep-agents-ui/)

```bash
cd deep-agents-ui
yarn install
yarn dev          # Dev server on localhost:3000
yarn build        # Production build
yarn lint         # ESLint
yarn format       # Prettier
```

### Rust `rig-deepagents`

```bash
cd rust-research-agent/rig-deepagents

# Run all tests
cargo test

# Run tests for a specific module
cargo test pregel::          # Pregel runtime tests
cargo test workflow::        # Workflow node tests
cargo test middleware::      # Middleware tests
cargo test checkpointing     # Checkpointing tests

# Linting (strict, treats warnings as errors)
cargo clippy -- -D warnings

# Build with optional features
cargo build --features checkpointer-sqlite
cargo build --features checkpointer-redis
cargo build --features checkpointer-postgres
```

### Running the Full Stack

1. Start backend: `langgraph dev` (port 2024)
2. Start frontend: `cd deep-agents-ui && yarn dev` (port 3000)
3. Configure UI with Deployment URL (`http://127.0.0.1:2024`) and Assistant ID (`research`)

## Required Environment Variables

Copy `env.example` to `.env`:

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | gpt-4.1 model |
| `TAVILY_API_KEY` | Yes | Web search |
| `ANTHROPIC_API_KEY` | No | Claude models + prompt caching |
| `LANGSMITH_API_KEY` | No | Tracing (`lsv2_pt_...`) |

## Architecture

### Multi-SubAgent System

```
Main Orchestrator Agent (agent.py)
    │
    ├── FilesystemBackend (../research_workspace)
    │   └── Persistent state via virtual filesystem
    │
    └── SubAgents
        ├── researcher (CompiledSubAgent) ─ Autonomous DeepAgent
        │   └── "Breadth-first, then depth" research pattern
        ├── explorer (Simple SubAgent) ─ Fast read-only exploration
        └── synthesizer (Simple SubAgent) ─ Research result integration
```

**CompiledSubAgent vs Simple SubAgent:**

| Type | Definition | Execution | Use Case |
|------|------------|-----------|----------|
| CompiledSubAgent | `{"runnable": CompiledStateGraph}` | Multi-turn autonomous | Complex research with self-planning |
| Simple SubAgent | `{"system_prompt": str}` | Single response | Quick tasks, file ops |

### Context Engineering Strategies (context_engineering_research_agent/)

Five strategies for optimizing LLM context window usage:

| Strategy | File | Trigger |
|----------|------|---------|
| **Offloading** | `context_strategies/offloading.py` | Tool result > 20,000 tokens |
| **Reduction** | `context_strategies/reduction.py` | Context usage > 85% |
| **Retrieval** | grep/glob/read_file tools | Always available |
| **Isolation** | SubAgent `task()` tool | Complex subtasks |
| **Caching** | `context_strategies/caching.py` | Anthropic provider |

Middleware stack order matters: Offloading → Reduction → Caching → Telemetry

### Backend Factory Pattern

The `backend_factory(rt: ToolRuntime)` function demonstrates the recommended pattern:
```python
CompositeBackend(
    default=StateBackend(rt),      # In-memory state (temporary files)
    routes={"/": fs_backend}       # Route "/" paths to FilesystemBackend
)
```
Paths starting with "/" go to persistent local filesystem (`research_workspace/`), others use ephemeral state.

### DeepAgents Auto-Injected Tools

The `create_deep_agent()` function automatically adds these tools via middleware:
- **TodoListMiddleware**: `write_todos` - Task planning and progress tracking
- **FilesystemMiddleware**: `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`
- **SubAgentMiddleware**: `task` - Delegate work to sub-agents
- **SkillsMiddleware**: Progressive skill disclosure via `skills/` directory

Custom tools (`tavily_search`, `think_tool`) are added explicitly in `agent.py`.

### Skills System

Project-level skills in `skills/`:
- `academic-search/` - arXiv paper search
- `data-synthesis/` - Multi-source data integration
- `report-writing/` - Structured report generation
- `skill-creator/` - Meta-skill for creating new skills

Each skill has `SKILL.md` with YAML frontmatter. SkillsMiddleware uses Progressive Disclosure: only metadata injected at session start, full content read on-demand.

## Rust `rig-deepagents` Architecture

Pregel-inspired graph execution runtime for agent workflows.

### Module Structure

```
rust-research-agent/rig-deepagents/src/
├── lib.rs              # Library entry point and re-exports
├── pregel/             # Pregel Runtime (graph execution engine)
│   ├── runtime.rs      # Superstep orchestration, CheckpointingRuntime
│   ├── vertex.rs       # Vertex trait and compute context
│   ├── message.rs      # Inter-vertex message passing
│   ├── config.rs       # PregelConfig, RetryPolicy
│   ├── checkpoint/     # Fault tolerance via checkpointing
│   │   ├── mod.rs      # Checkpointer trait
│   │   ├── file.rs     # FileCheckpointer
│   │   ├── sqlite.rs   # SQLiteCheckpointer
│   │   ├── redis.rs    # RedisCheckpointer
│   │   └── postgres.rs # PostgresCheckpointer
│   └── state.rs        # WorkflowState trait
├── workflow/           # Workflow Builder DSL
│   ├── compiled.rs     # CompiledWorkflow with checkpoint support
│   ├── graph.rs        # WorkflowGraph builder API
│   └── vertices/       # Node implementations (Agent, Tool, Router, etc.)
├── compat/             # Rig Framework Compatibility Layer
│   ├── rig_agent_adapter.rs  # RigAgentAdapter (primary LLM integration)
│   └── rig_tool_adapter.rs   # RigToolAdapter for Rig Tool compatibility
├── middleware/         # AgentMiddleware trait and MiddlewareStack
│   └── summarization/  # Token counting and context summarization
├── backends/           # Backend trait (Memory, Filesystem, Composite)
├── llm/                # LLMProvider abstraction (uses RigAgentAdapter)
└── tools/              # Tool implementations (read_file, write_file, etc.)
```

### LLM Integration

**Use `RigAgentAdapter`** to wrap Rig's native providers (OpenAI, Anthropic, etc.):

```rust
use rig::providers::openai::Client;
use rig_deepagents::{RigAgentAdapter, AgentExecutor};

let client = Client::from_env();
let agent = client.agent("gpt-4").build();
let provider = RigAgentAdapter::new(agent);
```

Legacy `OpenAIProvider` and `AnthropicProvider` have been removed.

### Pregel Execution Model

```
┌─────────────────────────────────────────────────────────────┐
│                    PregelRuntime                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                     │
│  │Superstep│→ │Superstep│→ │Superstep│→ ...                │
│  │    0    │  │    1    │  │    2    │                     │
│  └─────────┘  └─────────┘  └─────────┘                     │
│       │            │            │                           │
│       ▼            ▼            ▼                           │
│  Per-Superstep: Deliver → Compute → Collect → Route        │
└─────────────────────────────────────────────────────────────┘
```

- **Vertex**: Computation unit with `compute()` method (Agent, Tool, Router)
- **Message**: Communication between vertices across supersteps
- **Checkpointing**: Fault tolerance via periodic state snapshots (File, SQLite, Redis, Postgres)
- **Retry Policy**: Exponential backoff with configurable max retries

### Key Types

| Type | Purpose |
|------|---------|
| `PregelRuntime<S, M>` | Executes workflow graph with state S and message M |
| `CheckpointingRuntime<S, M>` | PregelRuntime with checkpoint/resume support |
| `RigAgentAdapter` | Wraps any Rig Agent for LLMProvider compatibility |
| `CompiledWorkflow` | Builder result with optional checkpointing |

## Key Files for Understanding the System

**Python DeepAgents:**
1. `research_agent/agent.py` - Orchestrator creation and SubAgent assembly
2. `research_agent/researcher/agent.py` - Autonomous researcher factory (CompiledSubAgent pattern)
3. `research_agent/researcher/prompts.py` - Three-phase autonomous workflow
4. `research_agent/prompts.py` - Orchestrator and Simple SubAgent prompts

**Context Engineering:**
5. `context_engineering_research_agent/agent.py` - Context-aware agent factory
6. `context_engineering_research_agent/context_strategies/` - 5 optimization strategies

**Rust rig-deepagents:**
7. `rust-research-agent/rig-deepagents/src/pregel/runtime.rs` - Pregel + Checkpointing
8. `rust-research-agent/rig-deepagents/src/compat/rig_agent_adapter.rs` - LLM integration
9. `rust-research-agent/rig-deepagents/src/workflow/compiled.rs` - Workflow compilation

## Critical Patterns

### SubAgent Creation

Always use factory functions, never instantiate directly:
```python
# Correct
researcher_subagent = get_researcher_subagent()

# Wrong - bypasses middleware setup
researcher = create_researcher_agent()
```

### File Path Routing

Paths starting with "/" persist to `research_workspace/`, others are in-memory:
```python
write_file("/reports/summary.md", content)  # Persists
write_file("temp/scratch.txt", content)     # Ephemeral
```

### Reflection Loop

Always use `think_tool()` between web searches - explicit reflection is required:
```
Search → think_tool() → Decide → Search → think_tool() → Synthesize
```

## Tech Stack

- **Python 3.13**: deepagents, langchain-openai, langgraph-cli, tavily-python
- **Rust**: rig-core 0.27, tokio, serde, async-trait, thiserror
- **Frontend**: Next.js 16, React, TailwindCSS, Radix UI
- **Package managers**: uv (Python), Yarn (Node.js), Cargo (Rust)

## External Resources

- [LangChain DeepAgent Docs](https://docs.langchain.com/oss/python/deepagents/overview)
- [LangGraph CLI Docs](https://docs.langchain.com/langsmith/cli#configuration-file)
- [DeepAgent UI](https://github.com/langchain-ai/deep-agents-ui)
