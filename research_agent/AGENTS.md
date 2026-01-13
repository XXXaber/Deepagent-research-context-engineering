# AGENTS.md - Research Agent Module

> **Component**: `research_agent/`
> **Type**: Python DeepAgent Orchestrator
> **Role**: Multi-SubAgent Research System with Skills Integration

---

## 1. Module Purpose

This module implements the main research orchestrator using LangChain's DeepAgents framework. It coordinates three specialized SubAgents and integrates a project-level skills system.

---

## 2. Architecture: Three-Tier SubAgent System

```
Orchestrator (agent.py)
    |
    +-- researcher (CompiledSubAgent)
    |       Autonomous, self-planning DeepAgent
    |       "Breadth-first, then depth" research pattern
    |
    +-- explorer (Simple SubAgent)
    |       Fast read-only filesystem exploration
    |
    +-- synthesizer (Simple SubAgent)
            Multi-source result integration
```

### SubAgent Types

| Type | Definition | Execution | Use Case |
|------|------------|-----------|----------|
| CompiledSubAgent | `{"runnable": CompiledStateGraph}` | Multi-turn autonomous | Complex research |
| Simple SubAgent | `{"system_prompt": str}` | Single response | Quick tasks |

---

## 3. Key Files

| File | Purpose |
|------|---------|
| `agent.py` | Orchestrator assembly: model, backend, SubAgents, middleware |
| `prompts.py` | Orchestrator prompts: workflow, delegation, explorer, synthesizer |
| `tools.py` | `tavily_search()`, `think_tool()` implementations |
| `researcher/agent.py` | `get_researcher_subagent()` factory for CompiledSubAgent |
| `researcher/prompts.py` | Three-phase autonomous workflow (Exploratory -> Directed -> Synthesis) |
| `researcher/depth.py` | Research depth configuration (shallow/medium/deep) |
| `researcher/ralph_loop.py` | Iterative refinement loop pattern |
| `skills/middleware.py` | SkillsMiddleware with Progressive Disclosure |

---

## 4. Backend Configuration

The module uses a **CompositeBackend** pattern:

```python
CompositeBackend(
    default=StateBackend(rt),       # In-memory (temporary files)
    routes={"/": fs_backend}        # "/" paths -> research_workspace/
)
```

- Paths starting with "/" persist to `research_workspace/`
- Other paths use ephemeral in-memory state

---

## 5. Skills System

Skills are loaded from `PROJECT_ROOT/skills/` via `SkillsMiddleware`.

**Progressive Disclosure Pattern:**
1. Session start: Only skill metadata injected
2. Agent request: Full SKILL.md content loaded on-demand
3. Token efficiency: ~90% reduction in initial context

---

## 6. Anti-Patterns

- **DO NOT** directly instantiate researcher - use `get_researcher_subagent()`
- **DO NOT** skip `think_tool()` between searches - explicit reflection required
- **DO NOT** modify `backend_factory` signature - middleware depends on it

---

## 7. Extension Points

| Task | Where to Modify |
|------|-----------------|
| Add new SubAgent | Define in `agent.py`, add to `SIMPLE_SUBAGENTS` or `ALL_SUBAGENTS` |
| New research tool | Add to `tools.py`, include in `create_deep_agent(tools=[...])` |
| Custom middleware | Create in `skills/`, add to middleware list in `agent.py` |
| Modify researcher behavior | Edit `researcher/prompts.py` |
