//! Vertex implementations for workflow nodes
//!
//! Each vertex type implements the Vertex trait and corresponds to a NodeKind variant.
//!
//! # Available Vertices
//!
//! - [`agent::AgentVertex`]: LLM-based agent with tool calling
//! - [`subagent::SubAgentVertex`]: Delegates to sub-agents from registry
//! - [`tool::ToolVertex`]: Single tool execution with static/dynamic args

pub mod agent;
pub mod parallel;
pub mod subagent;
// pub mod tool;
// pub mod router;

// Future vertex implementations:
// pub mod parallel;
