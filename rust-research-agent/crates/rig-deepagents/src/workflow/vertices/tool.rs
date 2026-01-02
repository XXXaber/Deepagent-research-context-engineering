//! ToolVertex: Single tool execution vertex for Pregel workflows
//!
//! Executes a single tool with arguments from configuration and/or workflow state.
//! Unlike AgentVertex, this does not involve LLM calls - it's direct tool execution.

use async_trait::async_trait;
use std::sync::Arc;

use crate::middleware::DynTool;
use crate::pregel::error::PregelError;
use crate::pregel::message::WorkflowMessage;
use crate::pregel::state::WorkflowState;
use crate::pregel::vertex::{ComputeContext, ComputeResult, StateUpdate, Vertex, VertexId};
use crate::runtime::ToolRuntime;
use crate::workflow::node::ToolNodeConfig;

/// A vertex that executes a single tool
///
/// Tool arguments are built from:
/// 1. Static arguments in config (`static_args`)
/// 2. Dynamic arguments resolved from workflow state (`state_arg_paths`)
///
/// The result is stored at `config.result_path` in the output message.
pub struct ToolVertex<S: WorkflowState> {
    /// Vertex identifier
    id: VertexId,

    /// Tool configuration
    config: ToolNodeConfig,

    /// The tool to execute
    tool: Arc<DynTool>,

    /// Runtime for tool execution
    runtime: Arc<ToolRuntime>,

    /// Phantom data for state type
    _phantom: std::marker::PhantomData<S>,
}

impl<S: WorkflowState> ToolVertex<S> {
    /// Create a new ToolVertex
    ///
    /// # Arguments
    ///
    /// * `id` - Unique vertex identifier
    /// * `config` - Tool node configuration
    /// * `tool` - The tool to execute
    /// * `runtime` - Runtime for tool execution
    pub fn new(
        id: impl Into<VertexId>,
        config: ToolNodeConfig,
        tool: Arc<DynTool>,
        runtime: Arc<ToolRuntime>,
    ) -> Self {
        Self {
            id: id.into(),
            config,
            tool,
            runtime,
            _phantom: std::marker::PhantomData,
        }
    }

    /// Build arguments by merging static args with state-resolved args
    fn build_arguments(&self, _state: &S) -> serde_json::Value {
        let args = self.config.static_args.clone();

        // TODO: Resolve state_arg_paths from workflow state
        // For now, we only use static args
        // In a full implementation, we would:
        // 1. Parse each state_arg_path (e.g., "research.query")
        // 2. Extract the value from the workflow state
        // 3. Merge it into args

        for (arg_name, _state_path) in &self.config.state_arg_paths {
            // Placeholder: in a real implementation, resolve state_path from state
            // For now, skip dynamic args
            tracing::debug!(
                vertex_id = %self.id,
                arg_name = %arg_name,
                "Skipping state arg (not yet implemented)"
            );
        }

        serde_json::Value::Object(args.into_iter().collect())
    }
}

#[async_trait]
impl<S: WorkflowState> Vertex<S, WorkflowMessage> for ToolVertex<S> {
    fn id(&self) -> &VertexId {
        &self.id
    }

    async fn compute(
        &self,
        ctx: &mut ComputeContext<'_, S, WorkflowMessage>,
    ) -> Result<ComputeResult<S::Update>, PregelError> {
        tracing::info!(
            vertex_id = %self.id,
            tool_name = %self.config.tool_name,
            superstep = ctx.superstep,
            "ToolVertex compute starting"
        );

        // Build arguments from config and state
        let args = self.build_arguments(ctx.state);

        // Execute the tool
        let result_str = self
            .tool
            .execute(args, &self.runtime)
            .await
            .map_err(|e| PregelError::vertex_error(self.id.clone(), format!("Tool execution failed: {}", e)))?;

        tracing::info!(
            vertex_id = %self.id,
            tool_name = %self.config.tool_name,
            "Tool execution completed"
        );

        // Try to parse result as JSON, fallback to string
        let result_value = serde_json::from_str(&result_str)
            .unwrap_or_else(|_| serde_json::Value::String(result_str));

        // Build output key based on result_path or default
        let output_key = self
            .config
            .result_path
            .clone()
            .unwrap_or_else(|| format!("{}_result", self.config.tool_name));

        // Send result as output message
        ctx.send_message(
            "output",
            WorkflowMessage::Data {
                key: output_key,
                value: result_value,
            },
        );

        // Tool vertices complete after single execution
        Ok(ComputeResult::halt(S::Update::empty()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backends::MemoryBackend;
    use crate::error::MiddlewareError;
    use crate::middleware::ToolDefinition;
    use crate::pregel::state::UnitState;
    use crate::state::AgentState;
    use std::collections::HashMap;

    // Mock tool for testing
    struct MockTool {
        name: String,
        response: String,
    }

    impl MockTool {
        fn new(name: &str, response: serde_json::Value) -> Self {
            Self {
                name: name.to_string(),
                response: serde_json::to_string(&response).unwrap(),
            }
        }
    }

    #[async_trait]
    impl crate::middleware::Tool for MockTool {
        fn definition(&self) -> ToolDefinition {
            ToolDefinition {
                name: self.name.clone(),
                description: "Mock tool for testing".to_string(),
                parameters: serde_json::json!({
                    "type": "object",
                    "properties": {}
                }),
            }
        }

        async fn execute(
            &self,
            _args: serde_json::Value,
            _runtime: &ToolRuntime,
        ) -> Result<String, MiddlewareError> {
            Ok(self.response.clone())
        }
    }

    fn create_test_runtime() -> Arc<ToolRuntime> {
        let backend = Arc::new(MemoryBackend::new());
        Arc::new(ToolRuntime::new(AgentState::new(), backend))
    }

    #[test]
    fn test_tool_vertex_creation() {
        let mock_tool: Arc<DynTool> = Arc::new(MockTool::new("test_tool", serde_json::json!({"result": "ok"})));
        let runtime = create_test_runtime();

        let config = ToolNodeConfig {
            tool_name: "test_tool".to_string(),
            ..Default::default()
        };

        let vertex: ToolVertex<UnitState> = ToolVertex::new("tool_node", config, mock_tool, runtime);

        assert_eq!(vertex.id().as_str(), "tool_node");
    }

    #[tokio::test]
    async fn test_tool_vertex_execute_with_static_args() {
        let mock_tool: Arc<DynTool> = Arc::new(MockTool::new(
            "search",
            serde_json::json!({"results": ["item1", "item2"]}),
        ));
        let runtime = create_test_runtime();

        let mut static_args = HashMap::new();
        static_args.insert("query".to_string(), serde_json::json!("test query"));
        static_args.insert("limit".to_string(), serde_json::json!(10));

        let config = ToolNodeConfig {
            tool_name: "search".to_string(),
            static_args,
            result_path: Some("search_results".to_string()),
            ..Default::default()
        };

        let vertex: ToolVertex<UnitState> = ToolVertex::new("search_node", config, mock_tool, runtime);

        let mut ctx = ComputeContext::<UnitState, WorkflowMessage>::new(
            "search_node".into(),
            &[],
            0,
            &UnitState,
        );

        let result = vertex.compute(&mut ctx).await.unwrap();

        // Should halt after execution
        assert!(result.state.is_halted());

        // Should have sent output message
        let outbox = ctx.into_outbox();
        assert!(outbox.contains_key(&VertexId::new("output")));

        let messages = outbox.get(&VertexId::new("output")).unwrap();
        assert_eq!(messages.len(), 1);

        match &messages[0] {
            WorkflowMessage::Data { key, value } => {
                assert_eq!(key, "search_results");
                assert_eq!(value, &serde_json::json!({"results": ["item1", "item2"]}));
            }
            _ => panic!("Expected Data message"),
        }
    }

    #[test]
    fn test_tool_vertex_build_arguments() {
        let mock_tool: Arc<DynTool> = Arc::new(MockTool::new("tool", serde_json::json!({})));
        let runtime = create_test_runtime();

        let mut static_args = HashMap::new();
        static_args.insert("key1".to_string(), serde_json::json!("value1"));
        static_args.insert("key2".to_string(), serde_json::json!(42));

        let config = ToolNodeConfig {
            tool_name: "tool".to_string(),
            static_args,
            ..Default::default()
        };

        let vertex: ToolVertex<UnitState> = ToolVertex::new("test", config, mock_tool, runtime);

        let args = vertex.build_arguments(&UnitState);

        assert!(args.is_object());
        let obj = args.as_object().unwrap();
        assert_eq!(obj.get("key1"), Some(&serde_json::json!("value1")));
        assert_eq!(obj.get("key2"), Some(&serde_json::json!(42)));
    }

    #[tokio::test]
    async fn test_tool_vertex_default_result_path() {
        let mock_tool: Arc<DynTool> = Arc::new(MockTool::new("my_tool", serde_json::json!("done")));
        let runtime = create_test_runtime();

        // No result_path set - should default to "{tool_name}_result"
        let config = ToolNodeConfig {
            tool_name: "my_tool".to_string(),
            result_path: None,
            ..Default::default()
        };

        let vertex: ToolVertex<UnitState> = ToolVertex::new("test", config, mock_tool, runtime);

        let mut ctx = ComputeContext::<UnitState, WorkflowMessage>::new(
            "test".into(),
            &[],
            0,
            &UnitState,
        );

        let _ = vertex.compute(&mut ctx).await.unwrap();

        let outbox = ctx.into_outbox();
        let messages = outbox.get(&VertexId::new("output")).unwrap();

        match &messages[0] {
            WorkflowMessage::Data { key, .. } => {
                assert_eq!(key, "my_tool_result");
            }
            _ => panic!("Expected Data message"),
        }
    }
}
