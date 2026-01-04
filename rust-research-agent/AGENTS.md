# AGENTS.md - Senior Engineering Architecture Analysis

> **Author**: Senior AI Systems Architect / Rust Specialist
> **Scope**: Full Repository Analysis (`src`, `rig-deepagents`, `rig-rlm`)
> **Focus**: System Patterns, Framework Extension, & Architectural Trade-offs

---

## 1. Executive Summary: Three Tiers of Agency

This repository is not merely a single agent implementation but a **progressive laboratory of AI architectures**, evolving from simple scripts to complex, enterprise-grade systems.

| Component | Architecture | Rig Usage | Key Characteristic |
|-----------|--------------|-----------|---------------------|
| **`src/`** (Root Agent) | **Script-based ReAct** | Native Client | Zero-dependency, pure Rust, educational. |
| **`rig-deepagents`** | **Middleware / Pregel** | Extends `LLMProvider` | Enterprise-grade, stateful, widely extensible. |
| **`rig-rlm`** | **Recursive REPL** | Native + Tool Loop | Hybrid Runtime (Rust + Python via PyO3). |

---

## 2. Deep Dive: `rig-deepagents` (The Enterprise Core)

This is the most sophisticated component, effectively implementing a **Rust version of LangGraph**.

### A. The Middleware Pattern (`src/middleware/`)
Instead of a monolithic loops, the agent uses an **Interceptor Chain** pattern.
*   **Architecture**: `AgentExecutor` runs a loop but delegates control to a `MiddlewareStack`.
*   **Hooks**: `before_agent` -> `before_model` -> `after_model` -> `after_agent`.
*   **Power**: This allows "Human-in-the-Loop" (HITL) without dirtying the core logic. The executor respects a `ModelControl::Interrupt` signal, allowing the agent to "pause" execution for user approval—a critical feature for production safety.

### B. "Pregel" Graph Runtime (`src/pregel/`)
The presence of a `pregel` module suggests a **Graph-Based State Machine**.
*   **Concept**: Modeling agent flows as a graph (nodes = steps, edges = transitions) allows for cyclic workflows (ReAct) and acyclic ones (DAGs) in a single runtime.
*   **Checkpointing**: The `checkpoint` module (supporting SQLite, Redis, Postgres via feature flags) indicates "Time-Travel" debugging or durable state recovery, essential for long-running research tasks.

### C. Abstraction Layers
*   **`LLMProvider` Trait**: It wraps Rig's native client. This might seem redundant but is necessary to inject custom logic (like token counting or response synthetic modification) *before* the framework sees it.
*   **`Backend` Trait**: Abstracts the filesystem (`FilesystemBackend` vs `MemoryBackend`). This makes the entire agent unit-testable without mocking `std::fs`.

---

## 3. Deep Dive: `rig-rlm` (The Hybrid Runtime)

"RLM" likely stands for **Recursive Language Model**. It represents a paradigm shift from "Tool Use" to "Code Execution".

### A. The "Code as Thought" Pattern
Instead of JSON tool calls, this agent "thinks" in Python.
*   **Mechanism**: The System Prompt (`llm.rs`) teaches the model to write Python code blocks labeled ` ```repl `.
*   **Rust-Python Bridge**: It uses **PyO3** to embed a Python interpreter inside the Rust binary. This gives the agent access to the entire PyPI ecosystem (Pandas, Numpy) *in-process*, with zero network latency.

### B. Recursive Reasoning
The most fascinating pattern is the **Recursive Context Chunking**:
```python
# From system prompt example
chunk = context[:10000]
answer = llm_query(f"What is... {chunk}")
```
The agent allows the LLM to call *itself* (sub-LLMs) via the REPL. This handles "Infinite Context" problems by manually implementing Map-Reduce strategies in Python code generated on the fly.

---

## 4. Deep Dive: Root Agent (`src/`) ( Reference Implementation)

This serves as the "Baseline".
*   **Design**: Safe, standard Rust.
*   **Pattern**: Direct `impl Tool for WebSearchTool`. simple `loop { model.prompt() }`.
*   **Strength**: No external runtime overhead. Perfect for CLI tools that need to "just work".

---

## 5. Comparative Engineering Analysis

### 1. Error Handling Philosophy
*   **Root Agent**: `anyhow` for simplicity. "Crash and report".
*   **DeepAgents**: `thiserror` + Custom Enums (`DeepAgentError`). "Catch and Recover". Middleware can inspect *why* a tool failed and attempt a fix strategy.

### 2. State Management
*   **Root Agent**: In-memory `Vec<Message>`. Transient.
*   **DeepAgents**: Serializable `AgentState` struct. Durable. Can survive process restarts (if checkpointing is enabled).

### 3. Tooling Strategy
*   **Root Agent**: Static dispatch. Tools are known at compile time.
*   **DeepAgents**: Dynamic dispatch (`DynTool`). Plugins can be loaded at runtime.
*   **RLM**: "God Tool" (REPL). The agent invents its own tools by defining Python functions.

---

## 6. Senior Recommendations

1.  **Unify the Tool Interface**: Currently `rig-deepagents` defines its own `Tool` trait that mirrors Rig's. As Rig matures, `rig-deepagents` should try to use Rig's traits directly to allow sharing tools with the community.
2.  **Security Sandboxing (RLM)**: `rig-rlm` executes generated Python code in-process. This is a **Remote Code Execution (RCE)** vulnerability by design. For production, the generic `PyO3Executor` should be replaced with a WASM runtime or a Firecracker microVM.
3.  **Observability**: `rig-deepagents` has `tracing`, but the complex middleware stack makes debugging hard. Implementing **OpenTelemetry Spans** for each middleware layer would visualize the "Latency tax" of the interceptor chain.

---

## 7. Conclusion

This repository is a high-quality reference for "The 3 Stages of Rust Agents":
1.  **Stage 1 (`src`)**: The embedded helper.
2.  **Stage 2 (`rig-rlm`)**: The data analyst (Code Interpreter).
3.  **Stage 3 (`rig-deepagents`)**: The autonomous employee (Long-running, Stateful).
