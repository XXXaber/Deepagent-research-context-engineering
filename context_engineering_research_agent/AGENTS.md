# AGENTS.md - Context Engineering Research Agent

> **Component**: `context_engineering_research_agent/`
> **Type**: Extended DeepAgent with Context Strategies
> **Role**: Experimental platform for 5 Context Engineering patterns

---

## 1. Module Purpose

This module extends the base research agent with explicit **Context Engineering** strategies. It serves as a research testbed for optimizing LLM context window usage.

---

## 2. The 5 Context Engineering Strategies

| Strategy | Implementation | Trigger |
|----------|----------------|---------|
| **Offloading** | `context_strategies/offloading.py` | Tool result > 20,000 tokens |
| **Reduction** | `context_strategies/reduction.py` | Context usage > 85% |
| **Retrieval** | grep/glob/read_file tools | Always available |
| **Isolation** | SubAgent `task()` tool | Complex subtasks |
| **Caching** | `context_strategies/caching.py` | Anthropic provider |

---

## 3. Key Files

| File | Purpose |
|------|---------|
| `agent.py` | Main factory: `create_context_aware_agent()` |
| `context_strategies/__init__.py` | Re-exports all strategy classes |
| `context_strategies/offloading.py` | `ContextOffloadingStrategy` middleware |
| `context_strategies/reduction.py` | `ContextReductionStrategy` middleware |
| `context_strategies/caching.py` | `ContextCachingStrategy` + provider detection |
| `context_strategies/caching_telemetry.py` | `PromptCachingTelemetryMiddleware` |
| `context_strategies/isolation.py` | State isolation utilities for SubAgents |
| `context_strategies/retrieval.py` | Selective file loading patterns |
| `backends/docker_sandbox.py` | Sandboxed execution backend |
| `backends/pyodide_sandbox.py` | Browser-based Python sandbox |

---

## 4. Agent Factory Pattern

```python
# Simple usage (defaults)
agent = get_agent()

# Customized configuration
agent = create_context_aware_agent(
    model="anthropic/claude-sonnet-4",
    enable_offloading=True,
    enable_reduction=True,
    enable_caching=True,
    offloading_token_limit=20000,
    reduction_threshold=0.85,
)
```

---

## 5. Multi-Provider Support

Provider detection is automatic via `detect_provider(model)`:

| Provider | Features |
|----------|----------|
| Anthropic | Full cache_control markers |
| OpenAI | Standard caching |
| OpenRouter | Pass `openrouter_model_name` for specific routing |
| Gemini | Standard caching |

---

## 6. Middleware Stack Order

Middlewares execute in registration order. The recommended stack:

```python
middleware=[
    ContextOffloadingStrategy,   # 1. Evict large results FIRST
    ContextReductionStrategy,    # 2. Compress if still too large
    ContextCachingStrategy,      # 3. Mark cacheable sections
    PromptCachingTelemetryMiddleware,  # 4. Collect metrics
]
```

**Order matters:** Offloading before reduction prevents unnecessary summarization.

---

## 7. Sandbox Backends

For secure code execution:

| Backend | Environment | Isolation Level |
|---------|-------------|-----------------|
| `DockerSandbox` | Container | High (network isolated) |
| `PyodideSandbox` | WASM | Medium (browser-like) |
| `DockerSession` | Persistent container | High + state persistence |

---

## 8. Testing

Tests are in `tests/context_engineering/`:
- `test_caching.py` - Cache strategy unit tests
- `test_offloading.py` - Eviction threshold tests
- `test_reduction.py` - Summarization trigger tests
- `test_integration.py` - Full agent integration tests
