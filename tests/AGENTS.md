# AGENTS.md - Test Suite

> **Component**: `tests/`
> **Type**: pytest Test Suite
> **Role**: Unit and integration tests for all Python modules

---

## 1. Test Organization

```
tests/
  context_engineering/    # Context strategy tests
    test_caching.py       # Cache control marker tests
    test_offloading.py    # Token eviction tests
    test_reduction.py     # Summarization trigger tests
    test_isolation.py     # SubAgent state isolation
    test_retrieval.py     # Selective file loading
    test_integration.py   # Full agent integration
    test_openrouter_models.py  # Multi-provider tests

  researcher/             # Research agent tests
    test_depth.py         # Research depth configuration
    test_ralph_loop.py    # Iterative refinement loop
    test_runner.py        # Agent runner tests
    test_tools.py         # Tool unit tests
    test_integration.py   # End-to-end research flow

  backends/               # Backend implementation tests
    test_docker_sandbox_integration.py
    conftest.py           # Shared fixtures
```

---

## 2. Running Tests

```bash
# All tests
uv run pytest tests/

# Specific module
uv run pytest tests/context_engineering/

# Single test file
uv run pytest tests/researcher/test_depth.py

# With coverage
uv run pytest --cov=research_agent tests/
```

---

## 3. Key Fixtures

Located in `conftest.py` files:
- `mock_model` - Mocked LLM for unit tests
- `temp_workspace` - Temporary filesystem backend
- `docker_sandbox` - Docker container fixture (integration)

---

## 4. Test Categories

| Category | Marker | Speed |
|----------|--------|-------|
| Unit | (default) | Fast |
| Integration | `@pytest.mark.integration` | Slow |
| Docker | `@pytest.mark.docker` | Requires Docker |
| LLM | `@pytest.mark.llm` | Requires API keys |

---

## 5. Environment Variables

For integration tests requiring real APIs:
- `OPENAI_API_KEY` - OpenAI tests
- `TAVILY_API_KEY` - Search tool tests
- `ANTHROPIC_API_KEY` - Caching tests with Claude
