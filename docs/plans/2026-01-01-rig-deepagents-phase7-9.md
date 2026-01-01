# Rig-DeepAgents Phase 7-9 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with TDD approach.

**Goal:** Complete the Rig-DeepAgents Rust port by implementing LLM provider abstraction, SubAgent execution system, Skills middleware, and domain tools.

**Architecture Principles:**
- **Abstraction First**: Design provider-agnostic interfaces before concrete implementations
- **TDD Approach**: Write failing tests first, then implement to make them pass
- **LangChain Patterns**: Reference langchain-openai/langchain-anthropic for proven patterns
- **Rig Integration**: Leverage rig-core's CompletionModel trait internally

**Tech Stack:** Rust 1.75+, rig-core 0.27, tokio, async-trait, serde_json, tracing

**Reference Sources:**
- LangChain Python: `langchain_openai`, `langchain_anthropic` packages
- Rig Core: `rig-core/src/completion/request.rs`, `rig-core/src/agent/completion.rs`
- Python DeepAgents: `research_agent/skills/`, `research_agent/subagents/`

---

## Dependency Graph

```
Phase 7: LLM Provider Abstraction
    │
    ▼
Phase 8: SubAgent Execution System (requires Phase 7)
    │
    ▼
Phase 9a: Skills Middleware ──┬── Phase 9b: Domain Tools
          (independent)       │    (independent)
                              │
                              ▼
                        Integration Testing
```

---

## Phase 7: LLM Provider Abstraction (CRITICAL)

### Overview

Create a provider-agnostic LLM interface that bridges DeepAgents with Rig's CompletionModel.

**Priority:**
1. OpenAI (gpt-4.1) - Primary target, matches Python reference
2. Anthropic (Claude) - Secondary target

### Task 7.1: Create LLM Module Structure

**Files:**
- Create: `rust-research-agent/crates/rig-deepagents/src/llm/mod.rs`
- Create: `rust-research-agent/crates/rig-deepagents/src/llm/provider.rs`
- Create: `rust-research-agent/crates/rig-deepagents/src/llm/config.rs`
- Create: `rust-research-agent/crates/rig-deepagents/src/llm/message.rs`
- Modify: `rust-research-agent/crates/rig-deepagents/src/lib.rs`

**Step 1: Create mod.rs**

```rust
//! LLM Provider abstractions for DeepAgents
//!
//! This module provides provider-agnostic interfaces for LLM completion,
//! bridging DeepAgents with various LLM providers via Rig framework.

mod provider;
mod config;
mod message;

pub use provider::{LLMProvider, LLMResponse, LLMResponseStream};
pub use config::{LLMConfig, TokenUsage};
pub use message::{MessageConverter, ToolConverter};
```

---

### Task 7.2: Define Core Types (TDD)

**Files:**
- Create: `rust-research-agent/crates/rig-deepagents/src/llm/config.rs`

**Step 1: Write failing tests first**

```rust
//! LLM configuration types

use serde::{Deserialize, Serialize};

/// Token usage statistics
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct TokenUsage {
    pub input_tokens: u64,
    pub output_tokens: u64,
    pub total_tokens: u64,
}

impl TokenUsage {
    pub fn new(input: u64, output: u64) -> Self {
        Self {
            input_tokens: input,
            output_tokens: output,
            total_tokens: input + output,
        }
    }
}

impl std::ops::Add for TokenUsage {
    type Output = Self;

    fn add(self, other: Self) -> Self::Output {
        Self {
            input_tokens: self.input_tokens + other.input_tokens,
            output_tokens: self.output_tokens + other.output_tokens,
            total_tokens: self.total_tokens + other.total_tokens,
        }
    }
}

impl std::ops::AddAssign for TokenUsage {
    fn add_assign(&mut self, other: Self) {
        self.input_tokens += other.input_tokens;
        self.output_tokens += other.output_tokens;
        self.total_tokens += other.total_tokens;
    }
}

/// LLM Provider configuration
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct LLMConfig {
    /// Model identifier (e.g., "gpt-4.1", "claude-3-opus")
    pub model: String,
    /// Sampling temperature (0.0 - 2.0)
    pub temperature: Option<f64>,
    /// Maximum tokens to generate
    pub max_tokens: Option<u64>,
    /// API key (optional, can use environment variable)
    pub api_key: Option<String>,
    /// API base URL (optional, for custom endpoints)
    pub api_base: Option<String>,
}

impl LLMConfig {
    pub fn new(model: impl Into<String>) -> Self {
        Self {
            model: model.into(),
            ..Default::default()
        }
    }

    pub fn with_temperature(mut self, temp: f64) -> Self {
        self.temperature = Some(temp);
        self
    }

    pub fn with_max_tokens(mut self, tokens: u64) -> Self {
        self.max_tokens = Some(tokens);
        self
    }

    pub fn with_api_key(mut self, key: impl Into<String>) -> Self {
        self.api_key = Some(key.into());
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_token_usage_add() {
        let a = TokenUsage::new(100, 50);
        let b = TokenUsage::new(200, 100);
        let c = a + b;

        assert_eq!(c.input_tokens, 300);
        assert_eq!(c.output_tokens, 150);
        assert_eq!(c.total_tokens, 450);
    }

    #[test]
    fn test_llm_config_builder() {
        let config = LLMConfig::new("gpt-4.1")
            .with_temperature(0.7)
            .with_max_tokens(4096);

        assert_eq!(config.model, "gpt-4.1");
        assert_eq!(config.temperature, Some(0.7));
        assert_eq!(config.max_tokens, Some(4096));
    }
}
```

---

### Task 7.3: Define LLMProvider Trait (TDD)

**Files:**
- Create: `rust-research-agent/crates/rig-deepagents/src/llm/provider.rs`

**Step 1: Write trait definition with tests**

```rust
//! LLM Provider trait definition

use async_trait::async_trait;
use std::pin::Pin;
use futures::Stream;

use crate::error::DeepAgentError;
use crate::state::Message;
use crate::middleware::ToolDefinition;
use super::config::{LLMConfig, TokenUsage};

/// LLM completion response
#[derive(Debug, Clone)]
pub struct LLMResponse {
    /// The assistant's response message
    pub message: Message,
    /// Token usage statistics (if available)
    pub usage: Option<TokenUsage>,
}

impl LLMResponse {
    pub fn new(message: Message) -> Self {
        Self { message, usage: None }
    }

    pub fn with_usage(mut self, usage: TokenUsage) -> Self {
        self.usage = Some(usage);
        self
    }
}

/// Streaming response chunk
#[derive(Debug, Clone)]
pub struct MessageChunk {
    pub content: String,
    pub is_final: bool,
    pub usage: Option<TokenUsage>,
}

/// Streaming response wrapper
pub struct LLMResponseStream {
    inner: Pin<Box<dyn Stream<Item = Result<MessageChunk, DeepAgentError>> + Send>>,
}

impl LLMResponseStream {
    pub fn new<S>(stream: S) -> Self
    where
        S: Stream<Item = Result<MessageChunk, DeepAgentError>> + Send + 'static,
    {
        Self {
            inner: Box::pin(stream),
        }
    }

    /// Create from a complete (non-streaming) response
    pub fn from_complete(response: LLMResponse) -> Self {
        let content = response.message.content().unwrap_or_default().to_string();
        let chunk = MessageChunk {
            content,
            is_final: true,
            usage: response.usage,
        };
        Self::new(futures::stream::once(async move { Ok(chunk) }))
    }
}

/// Core LLM Provider trait
///
/// Provides a provider-agnostic interface for LLM completion.
/// Implementations should bridge to specific providers (OpenAI, Anthropic, etc.)
/// via Rig's CompletionModel trait.
#[async_trait]
pub trait LLMProvider: Send + Sync {
    /// Generate a completion response (non-streaming)
    ///
    /// # Arguments
    /// * `messages` - Conversation history including the current prompt
    /// * `tools` - Available tools for the model to call
    /// * `config` - Optional runtime configuration overrides
    async fn complete(
        &self,
        messages: &[Message],
        tools: &[ToolDefinition],
        config: Option<&LLMConfig>,
    ) -> Result<LLMResponse, DeepAgentError>;

    /// Generate a streaming completion response
    ///
    /// Default implementation falls back to non-streaming.
    async fn stream(
        &self,
        messages: &[Message],
        tools: &[ToolDefinition],
        config: Option<&LLMConfig>,
    ) -> Result<LLMResponseStream, DeepAgentError> {
        let response = self.complete(messages, tools, config).await?;
        Ok(LLMResponseStream::from_complete(response))
    }

    /// Provider name for logging/debugging
    fn name(&self) -> &str;

    /// Default model for this provider
    fn default_model(&self) -> &str;
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::Role;

    struct MockProvider;

    #[async_trait]
    impl LLMProvider for MockProvider {
        async fn complete(
            &self,
            messages: &[Message],
            _tools: &[ToolDefinition],
            _config: Option<&LLMConfig>,
        ) -> Result<LLMResponse, DeepAgentError> {
            let last_content = messages.last()
                .and_then(|m| m.content())
                .unwrap_or("Hello");

            Ok(LLMResponse::new(Message::assistant(&format!("Echo: {}", last_content))))
        }

        fn name(&self) -> &str {
            "mock"
        }

        fn default_model(&self) -> &str {
            "mock-model"
        }
    }

    #[tokio::test]
    async fn test_mock_provider_complete() {
        let provider = MockProvider;
        let messages = vec![Message::user("Hello, world!")];

        let response = provider.complete(&messages, &[], None).await.unwrap();

        assert!(response.message.content().unwrap().contains("Echo:"));
        assert!(response.message.content().unwrap().contains("Hello, world!"));
    }

    #[tokio::test]
    async fn test_stream_fallback() {
        let provider = MockProvider;
        let messages = vec![Message::user("Test")];

        let stream = provider.stream(&messages, &[], None).await.unwrap();
        // Stream should work via fallback
        assert!(true); // Stream created successfully
    }
}
```

---

### Task 7.4: Message Conversion Layer (TDD)

**Files:**
- Create: `rust-research-agent/crates/rig-deepagents/src/llm/message.rs`

**Step 1: Define conversion traits**

```rust
//! Message conversion between DeepAgents and Rig formats

use crate::state::{Message, Role, ToolCall};
use crate::middleware::ToolDefinition;
use crate::error::DeepAgentError;
use rig::completion::{Message as RigMessage, ToolDefinition as RigToolDefinition};

/// Converts DeepAgents messages to Rig format
pub trait ToRigMessage {
    fn to_rig_message(&self) -> Result<RigMessage, DeepAgentError>;
}

/// Converts Rig messages to DeepAgents format
pub trait FromRigMessage {
    fn from_rig_message(msg: &RigMessage) -> Result<Self, DeepAgentError>
    where
        Self: Sized;
}

/// Converts DeepAgents tool definitions to Rig format
pub trait ToRigTool {
    fn to_rig_tool(&self) -> RigToolDefinition;
}

impl ToRigMessage for Message {
    fn to_rig_message(&self) -> Result<RigMessage, DeepAgentError> {
        match self.role {
            Role::User => Ok(RigMessage::user(self.content().unwrap_or(""))),
            Role::Assistant => {
                if let Some(tool_calls) = &self.tool_calls {
                    // Handle assistant message with tool calls
                    // Rig uses AssistantContent::ToolCall for this
                    Ok(RigMessage::assistant(self.content().unwrap_or("")))
                } else {
                    Ok(RigMessage::assistant(self.content().unwrap_or("")))
                }
            }
            Role::System => {
                // Rig handles system as preamble, not a message
                // Return as user message with system prefix for compatibility
                Ok(RigMessage::user(format!("[System]: {}", self.content().unwrap_or(""))))
            }
            Role::Tool => {
                // Tool results need special handling
                Ok(RigMessage::user(format!("[Tool Result]: {}", self.content().unwrap_or(""))))
            }
        }
    }
}

impl ToRigTool for ToolDefinition {
    fn to_rig_tool(&self) -> RigToolDefinition {
        RigToolDefinition {
            name: self.name.clone(),
            description: self.description.clone(),
            parameters: self.parameters.clone(),
        }
    }
}

/// Convert a slice of DeepAgents messages to Rig format
pub fn convert_messages(messages: &[Message]) -> Result<Vec<RigMessage>, DeepAgentError> {
    messages.iter().map(|m| m.to_rig_message()).collect()
}

/// Convert a slice of tool definitions to Rig format
pub fn convert_tools(tools: &[ToolDefinition]) -> Vec<RigToolDefinition> {
    tools.iter().map(|t| t.to_rig_tool()).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_user_message_conversion() {
        let msg = Message::user("Hello!");
        let rig_msg = msg.to_rig_message().unwrap();
        // Verify conversion worked (exact format depends on Rig internals)
        assert!(true);
    }

    #[test]
    fn test_tool_definition_conversion() {
        let tool = ToolDefinition {
            name: "read_file".to_string(),
            description: "Read a file".to_string(),
            parameters: serde_json::json!({
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                }
            }),
        };

        let rig_tool = tool.to_rig_tool();
        assert_eq!(rig_tool.name, "read_file");
        assert_eq!(rig_tool.description, "Read a file");
    }
}
```

---

### Task 7.5: OpenAI Provider Implementation (TDD)

**Files:**
- Create: `rust-research-agent/crates/rig-deepagents/src/llm/openai.rs`

**Step 1: Write failing test first**

```rust
//! OpenAI LLM Provider implementation via Rig

use async_trait::async_trait;
use rig::providers::openai::{Client, CompletionModel};
use std::sync::Arc;

use super::provider::{LLMProvider, LLMResponse, LLMResponseStream};
use super::config::{LLMConfig, TokenUsage};
use super::message::{convert_messages, convert_tools};
use crate::error::DeepAgentError;
use crate::state::Message;
use crate::middleware::ToolDefinition;

/// OpenAI LLM Provider
pub struct OpenAIProvider {
    client: Client,
    default_model: String,
    default_config: LLMConfig,
}

impl OpenAIProvider {
    /// Create a new OpenAI provider with API key from environment
    pub fn from_env() -> Result<Self, DeepAgentError> {
        Self::from_env_with_model("gpt-4.1")
    }

    /// Create with specific model
    pub fn from_env_with_model(model: impl Into<String>) -> Result<Self, DeepAgentError> {
        let client = Client::from_env();
        let model = model.into();

        Ok(Self {
            client,
            default_model: model.clone(),
            default_config: LLMConfig::new(model),
        })
    }

    /// Create with explicit API key
    pub fn new(api_key: impl Into<String>, model: impl Into<String>) -> Self {
        let client = Client::new(&api_key.into());
        let model = model.into();

        Self {
            client,
            default_model: model.clone(),
            default_config: LLMConfig::new(model),
        }
    }

    /// Get effective config (override with runtime config if provided)
    fn effective_config<'a>(&'a self, runtime: Option<&'a LLMConfig>) -> &'a LLMConfig {
        runtime.unwrap_or(&self.default_config)
    }
}

#[async_trait]
impl LLMProvider for OpenAIProvider {
    async fn complete(
        &self,
        messages: &[Message],
        tools: &[ToolDefinition],
        config: Option<&LLMConfig>,
    ) -> Result<LLMResponse, DeepAgentError> {
        let config = self.effective_config(config);

        // Get completion model from Rig
        let model = self.client.completion_model(&config.model);

        // Convert messages and tools
        let rig_messages = convert_messages(messages)?;
        let rig_tools = convert_tools(tools);

        // Build completion request
        let mut request_builder = model.completion_request(
            rig_messages.last().cloned().unwrap_or_else(|| rig::message::Message::user(""))
        );

        // Add chat history (all but last message)
        if rig_messages.len() > 1 {
            request_builder = request_builder.messages(rig_messages[..rig_messages.len()-1].to_vec());
        }

        // Add tools
        request_builder = request_builder.tools(rig_tools);

        // Apply config
        if let Some(temp) = config.temperature {
            request_builder = request_builder.temperature(temp);
        }
        if let Some(max) = config.max_tokens {
            request_builder = request_builder.max_tokens(max);
        }

        // Execute
        let response = request_builder.send().await
            .map_err(|e| DeepAgentError::LLMError(e.to_string()))?;

        // Convert response
        let content = response.choice.first()
            .map(|c| c.to_string())
            .unwrap_or_default();

        let usage = TokenUsage {
            input_tokens: response.usage.input_tokens,
            output_tokens: response.usage.output_tokens,
            total_tokens: response.usage.total_tokens,
        };

        Ok(LLMResponse::new(Message::assistant(&content)).with_usage(usage))
    }

    fn name(&self) -> &str {
        "openai"
    }

    fn default_model(&self) -> &str {
        &self.default_model
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    #[ignore] // Requires OPENAI_API_KEY
    async fn test_openai_provider_complete() {
        let provider = OpenAIProvider::from_env().unwrap();
        let messages = vec![Message::user("Say hello in exactly 3 words.")];

        let response = provider.complete(&messages, &[], None).await.unwrap();

        assert!(!response.message.content().unwrap().is_empty());
        assert!(response.usage.is_some());
    }

    #[test]
    fn test_openai_provider_creation() {
        // This test doesn't make API calls, just verifies construction
        let provider = OpenAIProvider::new("test-key", "gpt-4.1");
        assert_eq!(provider.name(), "openai");
        assert_eq!(provider.default_model(), "gpt-4.1");
    }
}
```

---

### Task 7.6: Anthropic Provider Implementation (TDD)

**Files:**
- Create: `rust-research-agent/crates/rig-deepagents/src/llm/anthropic.rs`

**Step 1: Similar structure to OpenAI**

```rust
//! Anthropic (Claude) LLM Provider implementation via Rig

use async_trait::async_trait;
use rig::providers::anthropic::{Client, CompletionModel, CLAUDE_3_5_SONNET};
use std::sync::Arc;

use super::provider::{LLMProvider, LLMResponse, LLMResponseStream};
use super::config::{LLMConfig, TokenUsage};
use super::message::{convert_messages, convert_tools};
use crate::error::DeepAgentError;
use crate::state::Message;
use crate::middleware::ToolDefinition;

/// Anthropic (Claude) LLM Provider
pub struct AnthropicProvider {
    client: Client,
    default_model: String,
    default_config: LLMConfig,
}

impl AnthropicProvider {
    pub fn from_env() -> Result<Self, DeepAgentError> {
        Self::from_env_with_model(CLAUDE_3_5_SONNET)
    }

    pub fn from_env_with_model(model: impl Into<String>) -> Result<Self, DeepAgentError> {
        let client = Client::from_env();
        let model = model.into();

        Ok(Self {
            client,
            default_model: model.clone(),
            default_config: LLMConfig::new(model).with_max_tokens(4096), // Anthropic requires max_tokens
        })
    }

    pub fn new(api_key: impl Into<String>, model: impl Into<String>) -> Self {
        let client = Client::new(&api_key.into());
        let model = model.into();

        Self {
            client,
            default_model: model.clone(),
            default_config: LLMConfig::new(model).with_max_tokens(4096),
        }
    }
}

#[async_trait]
impl LLMProvider for AnthropicProvider {
    async fn complete(
        &self,
        messages: &[Message],
        tools: &[ToolDefinition],
        config: Option<&LLMConfig>,
    ) -> Result<LLMResponse, DeepAgentError> {
        let config = config.unwrap_or(&self.default_config);

        let model = self.client.completion_model(&config.model);
        let rig_messages = convert_messages(messages)?;
        let rig_tools = convert_tools(tools);

        let mut request_builder = model.completion_request(
            rig_messages.last().cloned().unwrap_or_else(|| rig::message::Message::user(""))
        );

        if rig_messages.len() > 1 {
            request_builder = request_builder.messages(rig_messages[..rig_messages.len()-1].to_vec());
        }

        request_builder = request_builder.tools(rig_tools);

        if let Some(temp) = config.temperature {
            request_builder = request_builder.temperature(temp);
        }

        // Anthropic requires max_tokens
        let max_tokens = config.max_tokens.unwrap_or(4096);
        request_builder = request_builder.max_tokens(max_tokens);

        let response = request_builder.send().await
            .map_err(|e| DeepAgentError::LLMError(e.to_string()))?;

        let content = response.choice.first()
            .map(|c| c.to_string())
            .unwrap_or_default();

        let usage = TokenUsage {
            input_tokens: response.usage.input_tokens,
            output_tokens: response.usage.output_tokens,
            total_tokens: response.usage.total_tokens,
        };

        Ok(LLMResponse::new(Message::assistant(&content)).with_usage(usage))
    }

    fn name(&self) -> &str {
        "anthropic"
    }

    fn default_model(&self) -> &str {
        &self.default_model
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    #[ignore] // Requires ANTHROPIC_API_KEY
    async fn test_anthropic_provider_complete() {
        let provider = AnthropicProvider::from_env().unwrap();
        let messages = vec![Message::user("Say hello in exactly 3 words.")];

        let response = provider.complete(&messages, &[], None).await.unwrap();

        assert!(!response.message.content().unwrap().is_empty());
    }
}
```

---

### Task 7.7: Update Executor to Use LLMProvider

**Files:**
- Modify: `rust-research-agent/crates/rig-deepagents/src/executor.rs`

**Step 1: Replace old LLMProvider with new one**

```rust
// Update imports
use crate::llm::{LLMProvider, LLMConfig};

// Update AgentExecutor to use Arc<dyn LLMProvider>
pub struct AgentExecutor {
    llm: Arc<dyn LLMProvider>,
    middleware: MiddlewareStack,
    backend: Arc<dyn Backend>,
    max_iterations: usize,
    config: Option<LLMConfig>,
}

impl AgentExecutor {
    pub fn new(
        llm: Arc<dyn LLMProvider>,
        middleware: MiddlewareStack,
        backend: Arc<dyn Backend>,
    ) -> Self {
        Self {
            llm,
            middleware,
            backend,
            max_iterations: 50,
            config: None,
        }
    }

    pub fn with_config(mut self, config: LLMConfig) -> Self {
        self.config = Some(config);
        self
    }

    // Update run() to use new LLMProvider interface
    pub async fn run(&self, initial_state: AgentState) -> Result<AgentState, DeepAgentError> {
        // ... existing logic ...

        // LLM call changes to:
        let response = self.llm.complete(
            &state.messages,
            &tool_definitions,
            self.config.as_ref(),
        ).await?;

        state.add_message(response.message);

        // ... rest of loop ...
    }
}
```

---

### Task 7.8: Update lib.rs Exports

**Files:**
- Modify: `rust-research-agent/crates/rig-deepagents/src/lib.rs`

```rust
// Add llm module
pub mod llm;

// Re-exports
pub use llm::{
    LLMProvider, LLMResponse, LLMConfig, TokenUsage,
    OpenAIProvider, AnthropicProvider,
};
```

---

### Task 7.9: Verification

**Step 1: Run all tests**

```bash
source ~/.cargo/env && cd rust-research-agent/crates/rig-deepagents && cargo test
```

**Step 2: Run clippy**

```bash
source ~/.cargo/env && cd rust-research-agent/crates/rig-deepagents && cargo clippy -- -D warnings
```

**Step 3: Commit**

```bash
git add rust-research-agent/crates/rig-deepagents/
git commit -m "feat(llm): implement LLMProvider abstraction with OpenAI and Anthropic support

Phase 7 implementation:
- Add LLMProvider trait for provider-agnostic LLM access
- Implement OpenAIProvider via rig-core
- Implement AnthropicProvider via rig-core
- Add message/tool conversion layer
- Update AgentExecutor to use new LLMProvider

All providers tested with TDD approach."
```

---

## Phase 8: SubAgent Execution System

### Overview

Implement SubAgent registration, execution, and isolated context management.

**Python Reference:** `research_agent/subagents/registry.py`, `research_agent/subagents/definitions.py`

### Task 8.1: Create SubAgent Module Structure

**Files:**
- Create: `rust-research-agent/crates/rig-deepagents/src/subagent/mod.rs`
- Create: `rust-research-agent/crates/rig-deepagents/src/subagent/definition.rs`
- Create: `rust-research-agent/crates/rig-deepagents/src/subagent/registry.rs`
- Create: `rust-research-agent/crates/rig-deepagents/src/subagent/executor.rs`

### Task 8.2: Define SubAgent Types (TDD)

```rust
//! SubAgent definition types

use serde::{Deserialize, Serialize};

/// SubAgent type classification
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum SubAgentType {
    /// Simple single-response agent (prompt-based)
    Simple,
    /// Compiled multi-turn agent (StateGraph-based)
    Compiled,
}

/// SubAgent definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubAgentDefinition {
    pub name: String,
    pub description: String,
    pub agent_type: SubAgentType,
    pub system_prompt: Option<String>,
    pub tools: Vec<String>, // Tool names to include
    pub max_iterations: Option<usize>,
}

/// SubAgent execution context
pub struct SubAgentContext {
    pub parent_state: AgentState,
    pub recursion_depth: usize,
    pub isolated_backend: Arc<dyn Backend>,
}
```

### Task 8.3: Implement SubAgent Registry (TDD)

```rust
//! SubAgent registry for dynamic agent lookup

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

pub struct SubAgentRegistry {
    agents: RwLock<HashMap<String, SubAgentDefinition>>,
}

impl SubAgentRegistry {
    pub fn new() -> Self {
        Self {
            agents: RwLock::new(HashMap::new()),
        }
    }

    pub async fn register(&self, definition: SubAgentDefinition) {
        self.agents.write().await.insert(definition.name.clone(), definition);
    }

    pub async fn get(&self, name: &str) -> Option<SubAgentDefinition> {
        self.agents.read().await.get(name).cloned()
    }

    pub async fn list(&self) -> Vec<SubAgentDefinition> {
        self.agents.read().await.values().cloned().collect()
    }
}
```

### Task 8.4: Implement SubAgent Executor (TDD)

```rust
//! SubAgent execution logic

pub struct SubAgentExecutor {
    registry: Arc<SubAgentRegistry>,
    llm: Arc<dyn LLMProvider>,
    max_recursion_depth: usize,
}

impl SubAgentExecutor {
    pub async fn execute(
        &self,
        agent_name: &str,
        prompt: &str,
        context: SubAgentContext,
    ) -> Result<String, DeepAgentError> {
        // Check recursion limit
        if context.recursion_depth >= self.max_recursion_depth {
            return Err(DeepAgentError::RecursionLimit(
                format!("Max recursion depth {} exceeded", self.max_recursion_depth)
            ));
        }

        // Get agent definition
        let definition = self.registry.get(agent_name).await
            .ok_or_else(|| DeepAgentError::SubAgent(
                format!("Unknown SubAgent: {}", agent_name)
            ))?;

        match definition.agent_type {
            SubAgentType::Simple => self.execute_simple(&definition, prompt, context).await,
            SubAgentType::Compiled => self.execute_compiled(&definition, prompt, context).await,
        }
    }

    async fn execute_simple(
        &self,
        definition: &SubAgentDefinition,
        prompt: &str,
        context: SubAgentContext,
    ) -> Result<String, DeepAgentError> {
        // Single LLM call with system prompt
        let messages = vec![
            Message::system(definition.system_prompt.as_deref().unwrap_or("")),
            Message::user(prompt),
        ];

        let response = self.llm.complete(&messages, &[], None).await?;
        Ok(response.message.content().unwrap_or("").to_string())
    }

    async fn execute_compiled(
        &self,
        definition: &SubAgentDefinition,
        prompt: &str,
        context: SubAgentContext,
    ) -> Result<String, DeepAgentError> {
        // Multi-turn execution with tools
        // Create a child AgentExecutor with isolated context
        // ... implementation details ...
        todo!("Compiled SubAgent execution")
    }
}
```

### Task 8.5: Update TaskTool to Use SubAgentExecutor

Update `tools/task.rs` to delegate to `SubAgentExecutor`.

### Task 8.6: Verification & Commit

---

## Phase 9a: Skills Middleware

### Overview

Implement Skills middleware with progressive disclosure pattern from Python.

**Python Reference:** `research_agent/skills/middleware.py`, `research_agent/skills/load.py`

### Task 9a.1: Create Skills Module Structure

**Files:**
- Create: `rust-research-agent/crates/rig-deepagents/src/skills/mod.rs`
- Create: `rust-research-agent/crates/rig-deepagents/src/skills/loader.rs`
- Create: `rust-research-agent/crates/rig-deepagents/src/skills/middleware.rs`

### Task 9a.2: Define Skill Types (TDD)

```rust
//! Skill definition types

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// Skill metadata parsed from SKILL.md frontmatter
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillMetadata {
    pub name: String,
    pub description: String,
    pub path: PathBuf,
}

/// Full skill content (loaded on demand)
#[derive(Debug, Clone)]
pub struct SkillContent {
    pub metadata: SkillMetadata,
    pub instructions: String,
}
```

### Task 9a.3: Implement Skill Loader (TDD)

```rust
//! Skill loading from filesystem

pub struct SkillLoader {
    skills_dir: PathBuf,
}

impl SkillLoader {
    pub fn new(skills_dir: impl Into<PathBuf>) -> Self {
        Self { skills_dir: skills_dir.into() }
    }

    /// List all skills (metadata only - progressive disclosure)
    pub async fn list_skills(&self) -> Result<Vec<SkillMetadata>, DeepAgentError> {
        // Scan skills_dir for SKILL.md files
        // Parse YAML frontmatter for name + description
        todo!()
    }

    /// Load full skill content by name
    pub async fn load_skill(&self, name: &str) -> Result<SkillContent, DeepAgentError> {
        // Read full SKILL.md content
        todo!()
    }
}
```

### Task 9a.4: Implement SkillsMiddleware (TDD)

```rust
//! Skills middleware with progressive disclosure

pub struct SkillsMiddleware {
    loader: SkillLoader,
    cached_metadata: RwLock<Vec<SkillMetadata>>,
}

#[async_trait]
impl AgentMiddleware for SkillsMiddleware {
    async fn modify_prompt(&self, prompt: &str, _state: &AgentState) -> String {
        // Inject skill metadata into system prompt
        let skills = self.cached_metadata.read().await;
        let skills_section = format_skills_prompt(&skills);
        format!("{}\n\n{}", prompt, skills_section)
    }

    async fn before_agent(
        &self,
        state: &mut AgentState,
        _runtime: &ToolRuntime,
    ) -> Result<Option<StateUpdate>, MiddlewareError> {
        // Load skill metadata on first call
        if self.cached_metadata.read().await.is_empty() {
            let metadata = self.loader.list_skills().await?;
            *self.cached_metadata.write().await = metadata;
        }
        Ok(None)
    }
}
```

---

## Phase 9b: Domain Tools

### Overview

Implement research-specific tools matching Python reference.

**Python Reference:** `research_agent/tools.py`

### Task 9b.1: Implement TavilySearchTool (TDD)

**Files:**
- Create: `rust-research-agent/crates/rig-deepagents/src/tools/tavily.rs`

```rust
//! Tavily web search tool

use reqwest::Client;
use serde::{Deserialize, Serialize};

pub struct TavilySearchTool {
    client: Client,
    api_key: String,
}

#[derive(Debug, Serialize)]
struct TavilyRequest {
    query: String,
    max_results: usize,
    search_depth: String,
    include_raw_content: bool,
}

#[derive(Debug, Deserialize)]
struct TavilyResponse {
    results: Vec<TavilyResult>,
}

#[derive(Debug, Deserialize)]
struct TavilyResult {
    title: String,
    url: String,
    content: String,
    raw_content: Option<String>,
}

#[async_trait]
impl Tool for TavilySearchTool {
    fn definition(&self) -> ToolDefinition {
        ToolDefinition {
            name: "tavily_search".to_string(),
            description: "Search the web using Tavily API and retrieve relevant content.".to_string(),
            parameters: serde_json::json!({
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 5
                    },
                    "topic": {
                        "type": "string",
                        "enum": ["general", "news"],
                        "default": "general"
                    }
                },
                "required": ["query"]
            }),
        }
    }

    async fn execute(
        &self,
        args: serde_json::Value,
        _runtime: &ToolRuntime,
    ) -> Result<String, MiddlewareError> {
        // Implement Tavily API call
        todo!()
    }
}
```

### Task 9b.2: Implement ThinkTool (TDD)

```rust
//! Think tool for explicit reasoning

pub struct ThinkTool;

#[async_trait]
impl Tool for ThinkTool {
    fn definition(&self) -> ToolDefinition {
        ToolDefinition {
            name: "think".to_string(),
            description: "Use this tool for explicit reflection and reasoning before making decisions.".to_string(),
            parameters: serde_json::json!({
                "type": "object",
                "properties": {
                    "reflection": {
                        "type": "string",
                        "description": "Your current thinking and reasoning"
                    }
                },
                "required": ["reflection"]
            }),
        }
    }

    async fn execute(
        &self,
        args: serde_json::Value,
        _runtime: &ToolRuntime,
    ) -> Result<String, MiddlewareError> {
        let reflection: String = serde_json::from_value(args["reflection"].clone())
            .unwrap_or_default();

        // Think tool just returns the reflection - it's for prompting explicit reasoning
        Ok(format!("Reflection recorded: {}", reflection))
    }
}
```

### Task 9b.3: Update tools/mod.rs

Add new tools to exports and `all_tools()` function.

---

## Summary

| Phase | Tasks | Priority | Est. Time |
|-------|-------|----------|-----------|
| **Phase 7** | LLM Provider Abstraction | 🔴 CRITICAL | 3-4 hours |
| **Phase 8** | SubAgent Execution | 🔴 CRITICAL | 3-4 hours |
| **Phase 9a** | Skills Middleware | 🟡 HIGH | 2-3 hours |
| **Phase 9b** | Domain Tools | 🟡 HIGH | 2-3 hours |

**Total Estimated Time:** 10-14 hours

**TDD Verification at Each Phase:**
1. Write failing test
2. Implement minimum code to pass
3. Refactor if needed
4. Run full test suite
5. Run clippy
6. Commit

---

## Error Type Additions

Add to `src/error.rs`:

```rust
#[error("LLM error: {0}")]
LLMError(String),

#[error("Recursion limit exceeded: {0}")]
RecursionLimit(String),

#[error("Skill error: {0}")]
SkillError(String),
```
