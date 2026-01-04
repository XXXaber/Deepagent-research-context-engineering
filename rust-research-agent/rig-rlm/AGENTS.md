# AGENTS.md - Recursive Language Model (RLM) Architecture

> **Component**: `rig-rlm`
> **Type**: Hybrid (Rust + Python) Recursive Agent
> **Role**: Advanced Reasoning & Data Analysis

---

## 1. Core Concept: "The Agent as a REPL"

`rig-rlm` is a radical departure from traditional "tool-use" agents. Instead of calling predefined functions, the agent **writes and executes Python code** to solve problems.

### The Hybrid Runtime
The application is a single binary that fuses two runtimes:
1.  **Rust (Host)**: Handles networking (HTTP), LLM orchestration (Rig), and high-performance logic.
2.  **Python (Guest)**: Embedded via **PyO3**. Acts as the "Thinking Sandbox".

---

## 2. Key Components

### A. `RigRlm` Struct (`llm.rs`)
The main entry point. It wraps a Rig Agent but manages a persistence layer (`message_history`) and a `REPL` environment.
*   **Preamble Strategy**: The system prompt (`PREAMBLE`) explicitly instructs the LLM to output code blocks labeled ` ```repl `.
*   **Recursive Loop**:
    1.  User Query -> LLM.
    2.  LLM outputs Python Code.
    3.  Rust captures code -> PyO3 Executor runs it.
    4.  Output (stdout/return) is fed back to LLM.
    5.  Repeat until `FINAL <answer>`.

### B. `Pyo3Executor` (`exec.rs`)
This is the bridge. It lets the Rust host execute Python code strings.
*   **Context Injection**: The executor injects variables (like `context`) into the Python scope *before* execution.
*   **Sub-Agent Capability**: Crucially, the Python environment includes a `query_llm()` function. **This allows the Python code to call back into the Rust LLM host.**

---

## 3. The Recursion Pattern

This architecture enables **Map-Reduce** reasoning strategies that are impossible in standard agents.

**Scenario**: Analyze a 100MB text file.

**Standard Agent**: Fails (Context window exceeded).

**RLM Agent**:
1.  Writes Python to split the text into 50 chunks.
2.  Loops over chunks in Python.
3.  For each chunk, calls `query_llm("Summarize this...", chunk)`.
4.  Aggregates the 50 summaries in Python.
5.  Calls `query_llm("Final answer...", aggregated_summaries)`.

This "Programmatic Reasoning" delegates the complexity of state management to the Python interpreter, which is far better at loops and variable storage than an LLM's attention mechanism.

---

## 4. Engineering Trade-offs

### Strengths
*   **Infinite Flexibility**: The agent can import `pandas`, `numpy`, or `re` to handle data tasks no tool designer anticipated.
*   **Performance**: Heavy data processing happens in local Python (fast), not in the LLM (slow/expensive).

### Risks
*   **Security**: Providing a full Python REPL is dangerous. The current implementation trusts the LLM not to `import os; os.system("rm -rf /")`. To productionize this, the Python executor must be sandboxed (e.g., WebAssembly or gVisor).
*   **Complexity**: Debugging stack traces that jump between Rust threads and the Python Global Interpreter Lock (GIL) is non-trivial.
