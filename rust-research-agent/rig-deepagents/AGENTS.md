# AGENTS.md - DeepAgents Architecture

> **Component**: `rig-deepagents`
> **Type**: Middleware-Based Agent Runtime
> **Role**: State Management & Enterprise Orchestration

---

## 1. Core Architecture: The Interceptor Pattern

`rig-deepagents` differs from standard Rig agents by implementing a **Middleware Architecture**. Instead of a simple prompt-response loop, every action flows through a stack of interceptors.

### The Executor Loop (`executor.rs`)
The `AgentExecutor` manages the lifecycle of a task. It does *not* directly call the LLM in a simple loop. Instead, it follows this state machine:

1.  **Before Agent**: Middleware can modify initial state (e.g., loading todo lists).
2.  **Loop (`max_iterations`)**:
    *   **Before Model**: Middleware can:
        *   Modify the request (e.g., inject retrieval context).
        *   **Skip** the LLM entirely (cache hit).
        *   **Interrupt** execution (wait for human approval).
    *   **LLM Call**: Executed via the `LLMProvider` trait.
    *   **After Model**: Middleware inspects the response (e.g., logging, safety checks).
    *   **Tool Execution**: Tools are executed, and results are passed back.
3.  **After Agent**: Final cleanup or persistent storage (checkpoints).

### Code Snippet: Control Flow
```rust
// from executor.rs
match before_control {
    ModelControl::Interrupt(i) => return Err(DeepAgentError::Interrupt(i)),
    ModelControl::Skip(resp) => resp.message,
    ModelControl::Continue => llm.complete(...).await?,
}
```

---

## 2. Abstraction Layers

### A. `LLMProvider` Trait
wraps Rig's native `CompletionClient`.
*   **Why?**: Rig's client is final. To add features like **Token Counting**, **Rate Limiting**, or **Mocking** for tests, we need this wrapper.
*   **Key Feature**: Uniform interface for OpenAI, Ollama, and Fake/Mock models.

### B. `Backend` Trait
Abstracts the physical world.
*   `FilesystemBackend`: Real OS operations (production).
*   `MemoryBackend`: HashMap-based generic VFS (testing/sandboxed).
*   *Senior Note*: This allows end-to-end testing of destructive agents (e.g., "delete all files") without risk involved.

---

## 3. Middleware Catalog (`middleware/`)

The power of this crate lies in its composable middleware:

| Middleware | Function | Use Case |
|------------|----------|----------|
| `TodoListMiddleware` | Manages a `todos` list in the state | Long-running task tracking |
| `FilesystemMiddleware` | Injects file contents into context | Coding agents |
| `HumanInTheLoop` | Pauses on critical actions | Safety-critical ops |

---

## 4. Pregel / Graph Runtime (`pregel/`)

This module implements a DAG (Directed Acyclic Graph) runtime inspired by LangGraph.

*   **Nodes**: Individual processing steps (e.g., "Plan", "Execute", "Review").
*   **Edges**: Conditional logic determining the next step.
*   **Checkpointer**: Saves state between node transitions to durable storage (SQLite/Redis).

---

## 5. Engineering Best Practices

1.  **Type-Safe State**: `AgentState` is a struct, not a dynamic Dict. This prevents common "missing key" runtime errors found in Python agents.
2.  **Error Recovery**: The `ToolResultEvictor` automatically removes old/large tool outputs from the context window to prevent "Context Length Exceeded" crashes.
3.  **Async/Await**: The entire runtime is non-blocking, allowing high throughput for web-server usage.
