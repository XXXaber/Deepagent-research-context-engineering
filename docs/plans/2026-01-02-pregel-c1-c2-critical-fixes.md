# Pregel Runtime Critical Fixes (C1 & C2) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the two critical issues preventing LangGraph parity: (C1) entry-point execution model and (C2) edge-driven message routing.

**Architecture:** Introduce `ExecutionMode` enum with `MessageBased` (backward-compatible default) and `EdgeDriven` (LangGraph-style) modes. Modify vertex initialization and message routing based on mode.

**Tech Stack:** Rust, tokio, async-trait, serde

---

## Executive Summary

### Issues Being Fixed

| ID | Issue | Impact | Root Cause |
|----|-------|--------|------------|
| **C1** | All vertices start Active | Non-entry vertices compute in superstep 0 | `add_vertex()` sets `VertexState::Active` unconditionally |
| **C2** | Graph edges stored but unused | `add_edge()` has no effect on execution | `route_messages()` ignores `edges` field |

### Solution Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  ExecutionMode::MessageBased (default)                          │
│  - All vertices start Active (current behavior)                 │
│  - Edges are metadata only                                      │
│  - Preserves backward compatibility                             │
├─────────────────────────────────────────────────────────────────┤
│  ExecutionMode::EdgeDriven (LangGraph-style)                    │
│  - Only entry vertex starts Active                              │
│  - Other vertices start Halted                                  │
│  - Halted vertices auto-activate via edge messages              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Task 1: Add ExecutionMode Enum to Config

**Files:**
- Modify: `src/pregel/config.rs:1-15`
- Test: `src/pregel/config.rs` (existing test module)

**Step 1.1: Write the failing test**

Add to `src/pregel/config.rs` test module (after line 180):

```rust
#[test]
fn test_execution_mode_default_is_message_based() {
    let config = PregelConfig::default();
    assert_eq!(config.execution_mode, ExecutionMode::MessageBased);
}

#[test]
fn test_execution_mode_builder() {
    let config = PregelConfig::default()
        .with_execution_mode(ExecutionMode::EdgeDriven);
    assert_eq!(config.execution_mode, ExecutionMode::EdgeDriven);
}
```

**Step 1.2: Run test to verify it fails**

Run: `cargo test config::tests::test_execution_mode --no-run 2>&1`
Expected: Compilation error - `ExecutionMode` not defined

**Step 1.3: Add ExecutionMode enum**

Insert after line 8 (after imports) in `src/pregel/config.rs`:

```rust
/// Execution mode for the Pregel runtime
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub enum ExecutionMode {
    /// All vertices start Active. Vertices must explicitly send messages.
    /// Edges are stored but not used for automatic routing.
    /// This is the legacy behavior for backward compatibility.
    #[default]
    MessageBased,

    /// Only the entry vertex starts Active. Other vertices start Halted.
    /// When a vertex halts, Activate messages are automatically sent to edge targets.
    /// This matches LangGraph's execution model.
    EdgeDriven,
}
```

**Step 1.4: Add field to PregelConfig**

Modify `PregelConfig` struct (around line 25) to add:

```rust
/// Execution mode controlling vertex activation and edge routing
pub execution_mode: ExecutionMode,
```

**Step 1.5: Add default initialization**

In the `Default` impl (around line 53), add:

```rust
execution_mode: ExecutionMode::default(),
```

**Step 1.6: Add builder method**

After `with_retry_policy` method (around line 100), add:

```rust
/// Set the execution mode
pub fn with_execution_mode(mut self, mode: ExecutionMode) -> Self {
    self.execution_mode = mode;
    self
}
```

**Step 1.7: Export ExecutionMode in mod.rs**

In `src/pregel/mod.rs` line 41, add to re-exports:

```rust
pub use config::{PregelConfig, RetryPolicy, ExecutionMode};
```

**Step 1.8: Run tests to verify they pass**

Run: `cargo test config::tests::test_execution_mode`
Expected: PASS

**Step 1.9: Commit**

```bash
git add src/pregel/config.rs src/pregel/mod.rs
git commit -m "feat(pregel): add ExecutionMode enum for LangGraph-style execution"
```

---

## Task 2: Add activation_message() to VertexMessage Trait

**Files:**
- Modify: `src/pregel/message.rs:9-12`
- Modify: `src/pregel/message.rs:79-82` (WorkflowMessage impl)

**Step 2.1: Write the failing test**

Add to `src/pregel/message.rs` test module:

```rust
#[test]
fn test_activation_message() {
    let msg = WorkflowMessage::activation_message();
    assert!(matches!(msg, WorkflowMessage::Activate));
}
```

**Step 2.2: Run test to verify it fails**

Run: `cargo test message::tests::test_activation_message --no-run 2>&1`
Expected: Compilation error - `activation_message` not defined

**Step 2.3: Modify VertexMessage trait**

Change line 10 from:

```rust
pub trait VertexMessage: Clone + Send + Sync + 'static {}
```

To:

```rust
/// Trait bound for vertex messages
pub trait VertexMessage: Clone + Send + Sync + 'static {
    /// Create an activation message for edge-driven routing
    fn activation_message() -> Self;
}
```

**Step 2.4: Implement for WorkflowMessage**

After line 79 (after `impl VertexMessage for WorkflowMessage {}`), replace with:

```rust
impl VertexMessage for WorkflowMessage {
    fn activation_message() -> Self {
        WorkflowMessage::Activate
    }
}
```

**Step 2.5: Run test to verify it passes**

Run: `cargo test message::tests::test_activation_message`
Expected: PASS

**Step 2.6: Commit**

```bash
git add src/pregel/message.rs
git commit -m "feat(pregel): add activation_message() to VertexMessage trait"
```

---

## Task 3: Fix C1 - Entry Point Execution Model

**Files:**
- Modify: `src/pregel/runtime.rs:51` (add entry_vertex field)
- Modify: `src/pregel/runtime.rs:71` (initialize entry_vertex)
- Modify: `src/pregel/runtime.rs:76-82` (add_vertex)
- Modify: `src/pregel/runtime.rs:93-99` (set_entry)

**Step 3.1: Write failing tests**

Add to `src/pregel/runtime.rs` test module (after line 870):

```rust
#[tokio::test]
async fn test_edge_driven_only_entry_active() {
    use super::super::config::ExecutionMode;

    let config = PregelConfig::default()
        .with_execution_mode(ExecutionMode::EdgeDriven);
    let mut runtime: PregelRuntime<TestState, WorkflowMessage> =
        PregelRuntime::with_config(config);

    runtime
        .add_vertex(Arc::new(IncrementVertex { id: VertexId::new("a"), increment: 1 }))
        .add_vertex(Arc::new(IncrementVertex { id: VertexId::new("b"), increment: 1 }))
        .add_vertex(Arc::new(IncrementVertex { id: VertexId::new("c"), increment: 1 }))
        .set_entry("a");

    // Only "a" should be Active
    assert!(runtime.vertex_states.get(&VertexId::new("a")).unwrap().is_active(),
        "Entry vertex 'a' should be Active");
    assert!(runtime.vertex_states.get(&VertexId::new("b")).unwrap().is_halted(),
        "Non-entry vertex 'b' should be Halted");
    assert!(runtime.vertex_states.get(&VertexId::new("c")).unwrap().is_halted(),
        "Non-entry vertex 'c' should be Halted");
}

#[tokio::test]
async fn test_message_based_all_active_backward_compat() {
    use super::super::config::ExecutionMode;

    let config = PregelConfig::default()
        .with_execution_mode(ExecutionMode::MessageBased);
    let mut runtime: PregelRuntime<TestState, WorkflowMessage> =
        PregelRuntime::with_config(config);

    runtime
        .add_vertex(Arc::new(IncrementVertex { id: VertexId::new("a"), increment: 1 }))
        .add_vertex(Arc::new(IncrementVertex { id: VertexId::new("b"), increment: 1 }));

    // Both should be Active (backward compatible)
    assert!(runtime.vertex_states.get(&VertexId::new("a")).unwrap().is_active());
    assert!(runtime.vertex_states.get(&VertexId::new("b")).unwrap().is_active());
}
```

**Step 3.2: Run tests to verify they fail**

Run: `cargo test runtime::tests::test_edge_driven_only_entry_active`
Expected: FAIL - vertex 'b' is Active when it should be Halted

**Step 3.3: Add entry_vertex field to PregelRuntime**

After line 50 (after `retry_counts` field), add:

```rust
    /// Entry vertex ID (for EdgeDriven mode reference)
    entry_vertex: Option<VertexId>,
```

**Step 3.4: Initialize entry_vertex in with_config**

In `with_config()` (around line 71), add to struct initialization:

```rust
            entry_vertex: None,
```

**Step 3.5: Modify add_vertex for execution mode**

Replace lines 76-82 with:

```rust
    /// Add a vertex to the runtime
    pub fn add_vertex(&mut self, vertex: BoxedVertex<S, M>) -> &mut Self {
        let id = vertex.id().clone();
        // C1 Fix: Initial state depends on execution mode
        let initial_state = match self.config.execution_mode {
            ExecutionMode::MessageBased => VertexState::Active,
            ExecutionMode::EdgeDriven => VertexState::Halted,
        };
        self.vertex_states.insert(id.clone(), initial_state);
        self.message_queues.insert(id.clone(), Vec::new());
        self.vertices.insert(id, vertex);
        self
    }
```

**Step 3.6: Add ExecutionMode import**

At top of `runtime.rs` (around line 11), add:

```rust
use super::config::ExecutionMode;
```

**Step 3.7: Modify set_entry for execution mode**

Replace lines 93-99 with:

```rust
    /// Set the entry point (activate this vertex on start)
    pub fn set_entry(&mut self, entry: impl Into<VertexId>) -> &mut Self {
        let entry_id = entry.into();
        // C1 Fix: In EdgeDriven mode, ensure only entry is Active
        if self.config.execution_mode == ExecutionMode::EdgeDriven {
            // First, set all vertices to Halted
            for state in self.vertex_states.values_mut() {
                if state.is_active() {
                    *state = VertexState::Halted;
                }
            }
        }
        // Activate the entry vertex
        if let Some(state) = self.vertex_states.get_mut(&entry_id) {
            *state = VertexState::Active;
        }
        self.entry_vertex = Some(entry_id);
        self
    }
```

**Step 3.8: Run tests to verify they pass**

Run: `cargo test runtime::tests::test_edge_driven_only_entry_active`
Run: `cargo test runtime::tests::test_message_based_all_active_backward_compat`
Expected: PASS

**Step 3.9: Run all existing tests**

Run: `cargo test`
Expected: All 162+ tests pass (backward compatibility preserved)

**Step 3.10: Commit**

```bash
git add src/pregel/runtime.rs
git commit -m "fix(pregel): C1 - entry-only execution in EdgeDriven mode"
```

---

## Task 4: Fix C2 - Edge-Driven Message Routing

**Files:**
- Modify: `src/pregel/runtime.rs:172-201` (execute_superstep)
- Modify: `src/pregel/runtime.rs:217-341` (compute_vertices return type)
- Add: `src/pregel/runtime.rs:353+` (route_edge_messages method)

**Step 4.1: Write failing test**

Add to `src/pregel/runtime.rs` test module:

```rust
#[tokio::test]
async fn test_edge_driven_auto_activation() {
    use super::super::config::ExecutionMode;
    use std::sync::atomic::{AtomicBool, Ordering};

    // Vertex that halts immediately without sending messages
    struct HaltImmediatelyVertex {
        id: VertexId,
    }

    #[async_trait]
    impl Vertex<TestState, WorkflowMessage> for HaltImmediatelyVertex {
        fn id(&self) -> &VertexId {
            &self.id
        }

        async fn compute(
            &self,
            _ctx: &mut ComputeContext<'_, TestState, WorkflowMessage>,
        ) -> Result<ComputeResult<TestUpdate>, PregelError> {
            Ok(ComputeResult::halt(TestUpdate::empty()))
        }
    }

    // Vertex that records if it was activated
    struct RecordActivationVertex {
        id: VertexId,
        activated: Arc<AtomicBool>,
    }

    #[async_trait]
    impl Vertex<TestState, WorkflowMessage> for RecordActivationVertex {
        fn id(&self) -> &VertexId {
            &self.id
        }

        async fn compute(
            &self,
            ctx: &mut ComputeContext<'_, TestState, WorkflowMessage>,
        ) -> Result<ComputeResult<TestUpdate>, PregelError> {
            if ctx.has_messages() {
                self.activated.store(true, Ordering::SeqCst);
            }
            Ok(ComputeResult::halt(TestUpdate::empty()))
        }
    }

    let activated = Arc::new(AtomicBool::new(false));

    let config = PregelConfig::default()
        .with_execution_mode(ExecutionMode::EdgeDriven);
    let mut runtime: PregelRuntime<TestState, WorkflowMessage> =
        PregelRuntime::with_config(config);

    runtime
        .add_vertex(Arc::new(HaltImmediatelyVertex { id: VertexId::new("entry") }))
        .add_vertex(Arc::new(RecordActivationVertex {
            id: VertexId::new("target"),
            activated: Arc::clone(&activated),
        }))
        .set_entry("entry")
        .add_edge("entry", "target");

    let result = runtime.run(TestState::default()).await;
    assert!(result.is_ok(), "Workflow should complete successfully");

    // Target should have been activated via edge
    assert!(activated.load(Ordering::SeqCst),
        "Target vertex was not activated via edge - C2 fix not working");
}

#[tokio::test]
async fn test_edge_driven_chain_execution() {
    use super::super::config::ExecutionMode;
    use std::sync::atomic::{AtomicUsize, Ordering};

    static EXECUTION_ORDER: AtomicUsize = AtomicUsize::new(0);

    struct OrderedVertex {
        id: VertexId,
        expected_order: usize,
    }

    #[async_trait]
    impl Vertex<TestState, WorkflowMessage> for OrderedVertex {
        fn id(&self) -> &VertexId {
            &self.id
        }

        async fn compute(
            &self,
            _ctx: &mut ComputeContext<'_, TestState, WorkflowMessage>,
        ) -> Result<ComputeResult<TestUpdate>, PregelError> {
            let order = EXECUTION_ORDER.fetch_add(1, Ordering::SeqCst);
            assert_eq!(order, self.expected_order,
                "Vertex {} executed out of order", self.id);
            Ok(ComputeResult::halt(TestUpdate::empty()))
        }
    }

    EXECUTION_ORDER.store(0, Ordering::SeqCst);

    let config = PregelConfig::default()
        .with_execution_mode(ExecutionMode::EdgeDriven);
    let mut runtime: PregelRuntime<TestState, WorkflowMessage> =
        PregelRuntime::with_config(config);

    // Create chain: A -> B -> C
    runtime
        .add_vertex(Arc::new(OrderedVertex { id: VertexId::new("a"), expected_order: 0 }))
        .add_vertex(Arc::new(OrderedVertex { id: VertexId::new("b"), expected_order: 1 }))
        .add_vertex(Arc::new(OrderedVertex { id: VertexId::new("c"), expected_order: 2 }))
        .set_entry("a")
        .add_edge("a", "b")
        .add_edge("b", "c");

    let result = runtime.run(TestState::default()).await;
    assert!(result.is_ok());
    assert_eq!(EXECUTION_ORDER.load(Ordering::SeqCst), 3, "All 3 vertices should execute");
}
```

**Step 4.2: Run tests to verify they fail**

Run: `cargo test runtime::tests::test_edge_driven_auto_activation`
Expected: FAIL - target vertex never activated

**Step 4.3: Add route_edge_messages method**

After `route_messages` method (after line 352), add:

```rust
    /// Route automatic activation messages when vertices halt (EdgeDriven mode only)
    fn route_edge_messages(&mut self, newly_halted: &[VertexId]) {
        if self.config.execution_mode != ExecutionMode::EdgeDriven {
            return;
        }

        for source_id in newly_halted {
            // Get edge targets for this source
            if let Some(targets) = self.edges.get(source_id) {
                for target_id in targets {
                    // Send Activate message to each edge target
                    if let Some(queue) = self.message_queues.get_mut(target_id) {
                        queue.push(M::activation_message());
                    }
                }
            }
        }
    }
```

**Step 4.4: Modify compute_vertices to track newly halted**

Change the return type of `compute_vertices` (around line 217) from:

```rust
    ) -> Result<(Vec<S::Update>, HashMap<VertexId, HashMap<VertexId, Vec<M>>>), PregelError> {
```

To:

```rust
    ) -> Result<(Vec<S::Update>, HashMap<VertexId, HashMap<VertexId, Vec<M>>>, Vec<VertexId>), PregelError> {
```

**Step 4.5: Track newly halted vertices in compute_vertices**

After the `new_vertex_states` HashMap creation (around line 276), add tracking:

```rust
        let mut newly_halted = Vec::new();
```

In the success case (around line 292), after `new_vertex_states.insert(vid.clone(), compute_result.state);`, add:

```rust
                    if compute_result.state.is_halted() {
                        newly_halted.push(vid.clone());
                    }
```

**Step 4.6: Update return statement of compute_vertices**

Change the return (around line 340) from:

```rust
        Ok((final_updates, final_outboxes))
```

To:

```rust
        Ok((final_updates, final_outboxes, newly_halted))
```

**Step 4.7: Modify execute_superstep to use edge routing**

Replace line 195-198 with:

```rust
        // 3. Compute active vertices in parallel
        let (updates, outboxes, newly_halted) = self.compute_vertices(superstep, state, &inboxes).await?;

        // 4. Route explicit messages from vertex outboxes
        self.route_messages(outboxes);

        // 5. C2 Fix: Route automatic edge messages for newly halted vertices
        self.route_edge_messages(&newly_halted);
```

**Step 4.8: Run tests to verify they pass**

Run: `cargo test runtime::tests::test_edge_driven_auto_activation`
Run: `cargo test runtime::tests::test_edge_driven_chain_execution`
Expected: PASS

**Step 4.9: Run full test suite**

Run: `cargo test`
Expected: All tests pass

**Step 4.10: Run clippy**

Run: `cargo clippy -- -D warnings`
Expected: No warnings

**Step 4.11: Commit**

```bash
git add src/pregel/runtime.rs
git commit -m "fix(pregel): C2 - edge-driven message routing in EdgeDriven mode"
```

---

## Task 5: Final Verification and Documentation

**Files:**
- Verify: All test files
- Update: `src/pregel/mod.rs` (doc comments)

**Step 5.1: Run complete test suite**

Run: `cargo test`
Expected: All 170+ tests pass

**Step 5.2: Run clippy**

Run: `cargo clippy -- -D warnings`
Expected: No warnings

**Step 5.3: Update module documentation**

In `src/pregel/mod.rs`, update the module doc comment to include:

```rust
//! ## Execution Modes
//!
//! The runtime supports two execution modes:
//!
//! - `ExecutionMode::MessageBased` (default): All vertices start Active.
//!   Vertices must explicitly send messages. Backward compatible.
//!
//! - `ExecutionMode::EdgeDriven`: Only entry vertex starts Active.
//!   When vertices halt, activation messages are sent to edge targets.
//!   Matches LangGraph's execution model.
```

**Step 5.4: Final commit**

```bash
git add .
git commit -m "docs(pregel): add ExecutionMode documentation"
```

---

## Verification Checklist

- [ ] All new tests pass: `cargo test`
- [ ] No warnings: `cargo clippy -- -D warnings`
- [ ] Backward compatibility: Existing tests pass with `MessageBased` mode
- [ ] C1 verified: EdgeDriven mode only activates entry vertex
- [ ] C2 verified: Halted vertices trigger edge targets
- [ ] Chain execution works: A→B→C executes in order

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing tests | `MessageBased` is default, preserving current behavior |
| Performance impact | Edge routing is O(E) per superstep, negligible |
| Infinite loops | Protected by existing `max_supersteps` limit |
| Message type compatibility | `activation_message()` uses existing `Activate` variant |

---

*Plan generated 2026-01-02 via SubAgent collaboration (Plan + Explore + Research agents)*
