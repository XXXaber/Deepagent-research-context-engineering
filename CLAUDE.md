# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A multi-agent research system demonstrating **FileSystem-based Context Engineering** using LangChain's DeepAgents framework. The system includes:
- **Python DeepAgents**: LangChain-based multi-agent orchestration with web research capabilities
- **Rust `rig-deepagents`**: A port/reimagining using the Rig framework with Pregel-inspired graph execution

The system enables agents to conduct web research, delegate tasks to sub-agents, and generate comprehensive reports with persistent filesystem state.

## Development Commands

### Python Backend

```bash
# Install dependencies (uses uv package manager)
uv sync

# Start LangGraph development server (API on localhost:2024)
langgraph dev

# Linting and formatting
ruff check research_agent/
ruff format research_agent/

# Type checking
mypy research_agent/
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

### Interactive Notebook Development

```bash
# Open Jupyter for interactive agent testing
jupyter notebook DeepAgent_research.ipynb
```

The `research_agent/utils.py` module provides Rich-formatted display helpers for notebooks:
- `format_messages(messages)` - Renders messages with colored panels (Human=blue, AI=green, Tool=yellow)
- `show_prompt(text, title)` - Displays prompts with XML/header syntax highlighting

### Rust `rig-deepagents` Crate

```bash
cd rust-research-agent/crates/rig-deepagents

# Run all tests (159 tests)
cargo test

# Run tests for a specific module
cargo test pregel::          # Pregel runtime tests
cargo test workflow::        # Workflow node tests
cargo test middleware::      # Middleware tests

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
- `OPENAI_API_KEY` - For gpt-4.1 model
- `TAVILY_API_KEY` - For web search functionality
- `LANGSMITH_API_KEY` - Optional, format `lsv2_pt_...` for tracing
- `LANGSMITH_TRACING` / `LANGSMITH_PROJECT` - Optional tracing config

## Architecture

### Multi-SubAgent System

The system uses a three-tier agent hierarchy with two distinct SubAgent types:

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

### Core Components

**`research_agent/agent.py`** - Orchestrator configuration:
- LLM: `ChatOpenAI(model="gpt-4.1", temperature=0.0)`
- Creates researcher via `get_researcher_subagent()` (CompiledSubAgent)
- Defines `explorer_agent`, `synthesizer_agent` (Simple SubAgents)
- Assembles `ALL_SUBAGENTS = [researcher_subagent, *SIMPLE_SUBAGENTS]`

**`research_agent/researcher/`** - Autonomous researcher module:
- `agent.py`: `create_researcher_agent()` factory and `get_researcher_subagent()` wrapper
- `prompts.py`: `AUTONOMOUS_RESEARCHER_INSTRUCTIONS` with three-phase workflow (Exploratory → Directed → Synthesis)

**Backend Factory Pattern** - The `backend_factory(rt: ToolRuntime)` function demonstrates the recommended pattern:
```python
CompositeBackend(
    default=StateBackend(rt),      # In-memory state (temporary files)
    routes={"/": fs_backend}       # Route "/" paths to FilesystemBackend
)
```
This enables routing: paths starting with "/" go to persistent local filesystem (`research_workspace/`), others use ephemeral state.

**`research_agent/prompts.py`** - Prompt templates:
- `RESEARCH_WORKFLOW_INSTRUCTIONS` - Main workflow (plan → save → delegate → synthesize → write → verify)
- `SUBAGENT_DELEGATION_INSTRUCTIONS` - When to parallelize (comparisons) vs single agent (overviews)
- `EXPLORER_INSTRUCTIONS` - Fast read-only exploration with filesystem tools
- `SYNTHESIZER_INSTRUCTIONS` - Multi-source integration with confidence levels

**`research_agent/tools.py`** - Research tools:
- `tavily_search(query, max_results, topic)` - Searches web, fetches full page content, converts to markdown
- `think_tool(reflection)` - Explicit reflection step for deliberate research

**`langgraph.json`** - Deployment config pointing to `./research_agent/agent.py:agent`

### Context Engineering Pattern

The filesystem acts as long-term memory:
1. Agent reads/writes files in virtual `research_workspace/`
2. Structured outputs: reports, TODOs, request files
3. Middleware auto-injects filesystem and sub-agent tools
4. Automatic context summarization for token efficiency

### DeepAgents Auto-Injected Tools

The `create_deep_agent()` function automatically adds these tools via middleware:
- **TodoListMiddleware**: `write_todos` - Task planning and progress tracking
- **FilesystemMiddleware**: `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep` - File operations
- **SubAgentMiddleware**: `task` - Delegate work to sub-agents
- **SkillsMiddleware**: Progressive skill disclosure via `skills/` directory

Custom tools (`tavily_search`, `think_tool`) are added explicitly in `agent.py`.

### Skills System

Project-level skills are located in `PROJECT_ROOT/skills/`:
- `academic-search/` - arXiv paper search with structured output
- `data-synthesis/` - Multi-source data integration and analysis
- `report-writing/` - Structured report generation
- `skill-creator/` - Meta-skill for creating new skills

Each skill has a `SKILL.md` file with YAML frontmatter (name, description) and detailed instructions. The SkillsMiddleware uses Progressive Disclosure: only skill metadata is injected into the system prompt at session start; full skill content is read on-demand when needed.

### Research Workflow

**Orchestrator workflow:**
```
Plan → Save Request → Delegate to Sub-agents → Synthesize → Write Report → Verify
```

**Autonomous Researcher workflow (breadth-first, then depth):**
```
Phase 1: Exploratory Search (1-2 searches) → Identify directions
Phase 2: Directed Research (1-2 searches per direction) → Deep dive
Phase 3: Synthesis → Combine findings with source agreement analysis
```

Sub-agents operate with token budgets (5-6 max searches) and explicit reflection loops (Search → think_tool → Decide → Repeat).

## Rust `rig-deepagents` Architecture

The Rust crate provides a Pregel-inspired graph execution runtime for agent workflows.

### Module Structure

```
rust-research-agent/crates/rig-deepagents/src/
├── lib.rs              # Library entry point and re-exports
├── pregel/             # Pregel Runtime (graph execution engine)
│   ├── runtime.rs      # Superstep orchestration, workflow timeout, retry policies
│   ├── vertex.rs       # Vertex trait and compute context
│   ├── message.rs      # Inter-vertex message passing
│   ├── config.rs       # PregelConfig, RetryPolicy
│   ├── checkpoint/     # Fault tolerance via checkpointing
│   │   ├── mod.rs      # Checkpointer trait and factory
│   │   └── file.rs     # FileCheckpointer implementation
│   └── state.rs        # WorkflowState trait, UnitState
├── workflow/           # Workflow Builder DSL
│   ├── node.rs         # NodeKind (Agent, Tool, Router, SubAgent, FanOut/FanIn)
│   └── mod.rs          # WorkflowGraph builder API
├── middleware/         # AgentMiddleware trait and MiddlewareStack
├── backends/           # Backend trait (Memory, Filesystem, Composite)
├── llm/                # LLMProvider abstraction (OpenAI, Anthropic)
└── tools/              # Tool implementations (read_file, write_file, grep, etc.)
```

### Pregel Execution Model

The runtime executes workflows using synchronized supersteps:

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
- **Checkpointing**: Fault tolerance via periodic state snapshots
- **Retry Policy**: Exponential backoff with configurable max retries

### Key Types

| Type | Purpose |
|------|---------|
| `PregelRuntime<S, M>` | Executes workflow graph with state S and message M |
| `Vertex<S, M>` | Trait for computation nodes |
| `WorkflowState` | Trait for workflow state (must be serializable) |
| `PregelConfig` | Runtime configuration (max supersteps, parallelism, timeout) |
| `Checkpointer` | Trait for state persistence (Memory, File, SQLite, Redis, Postgres) |

### Design Documents

- `docs/plans/2026-01-02-rig-deepagents-pregel-design.md` - Comprehensive Pregel runtime design
- `docs/plans/2026-01-02-rig-deepagents-implementation-tasks.md` - Implementation task breakdown

## Key Files for Understanding the System

**Python DeepAgents:**
1. `research_agent/agent.py` - Orchestrator creation and SubAgent assembly
2. `research_agent/researcher/agent.py` - Autonomous researcher factory (CompiledSubAgent pattern)
3. `research_agent/researcher/prompts.py` - Three-phase autonomous workflow
4. `research_agent/prompts.py` - Orchestrator and Simple SubAgent prompts
5. `research_agent/tools.py` - Tool implementations
6. `research_agent/skills/middleware.py` - SkillsMiddleware with progressive disclosure

**Rust rig-deepagents:**
7. `rust-research-agent/crates/rig-deepagents/src/pregel/runtime.rs` - Pregel execution engine
8. `rust-research-agent/crates/rig-deepagents/src/pregel/vertex.rs` - Vertex abstraction
9. `rust-research-agent/crates/rig-deepagents/src/workflow/node.rs` - Node type definitions
10. `rust-research-agent/crates/rig-deepagents/src/llm/provider.rs` - LLMProvider trait

**Documentation:**
11. `DeepAgents_Technical_Guide.md` - Python DeepAgents reference (Korean)
12. `docs/plans/2026-01-02-rig-deepagents-pregel-design.md` - Rust Pregel design

## Tech Stack

- **Python 3.13**: deepagents, langchain-openai, langgraph-cli, tavily-python
- **Rust**: rig-core 0.27, tokio, serde, async-trait, thiserror
- **Frontend**: Next.js 16, React, TailwindCSS, Radix UI
- **Package managers**: uv (Python), Yarn (Node.js), Cargo (Rust)

## External Resources

- [LangChain DeepAgent Docs](https://docs.langchain.com/oss/python/deepagents/overview)
- [LangGraph CLI Docs](https://docs.langchain.com/langsmith/cli#configuration-file)
- [DeepAgent UI](https://github.com/langchain-ai/deep-agents-ui)
