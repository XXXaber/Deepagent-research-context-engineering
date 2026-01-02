//! Pregel Runtime for Graph-Based Agent Orchestration
//!
//! This module implements a Pregel-inspired runtime for executing agent workflows.
//! Key concepts:
//!
//! - **Vertex**: Computation unit (Agent, Tool, Router, etc.)
//! - **Edge**: Connection between vertices (Direct, Conditional)
//! - **Superstep**: Synchronized execution phase
//! - **Message**: Communication between vertices
//!
//! # Architecture
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────┐
//! │                    PregelRuntime                             │
//! │  ┌─────────┐  ┌─────────┐  ┌─────────┐                     │
//! │  │Superstep│→ │Superstep│→ │Superstep│→ ...                │
//! │  │    0    │  │    1    │  │    2    │                     │
//! │  └─────────┘  └─────────┘  └─────────┘                     │
//! │       │            │            │                           │
//! │       ▼            ▼            ▼                           │
//! │  ┌─────────────────────────────────────────────────────┐   │
//! │  │ Per-Superstep: Deliver → Compute → Collect → Route  │   │
//! │  └─────────────────────────────────────────────────────┘   │
//! └─────────────────────────────────────────────────────────────┘
//! ```

pub mod vertex;
pub mod message;
pub mod config;
pub mod error;
pub mod state;
pub mod runtime;
pub mod checkpoint;

// Re-exports
pub use vertex::{
    BoxedVertex, ComputeContext, ComputeResult, StateUpdate, Vertex, VertexId, VertexState,
};
pub use message::{Priority, Source, VertexMessage, WorkflowMessage};
pub use config::{PregelConfig, RetryPolicy};
pub use error::PregelError;
pub use state::{UnitState, UnitUpdate, WorkflowState};
pub use runtime::{PregelRuntime, WorkflowResult};
pub use checkpoint::{Checkpoint, Checkpointer, CheckpointerConfig, MemoryCheckpointer, FileCheckpointer, create_checkpointer};
