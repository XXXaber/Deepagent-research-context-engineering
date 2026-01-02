# Repository Guidelines

## Project Structure & Module Organization
- `research_agent/` contains the core Python agents, prompts, tools, and subagent utilities.
- `skills/` holds project-level skills as `SKILL.md` files (YAML frontmatter + instructions).
- `research_workspace/` is the agent’s working filesystem for generated outputs; keep it clean or example-only.
- `deep-agents-ui/` is the Next.js/React UI with source under `deep-agents-ui/src/`.
- `deepagents_sourcecode/` vendors upstream library sources for reference and comparison.
- `rust-research-agent/` is a standalone Rust tutorial agent with its own build/test flow.
- `langgraph.json` defines the LangGraph deployment entrypoint for the research agent.

## Build, Test, and Development Commands
Use the UI commands from `deep-agents-ui/` when working on the frontend:
```bash
cd deep-agents-ui && yarn install   # install deps
cd deep-agents-ui && yarn dev       # run local UI
cd deep-agents-ui && yarn build     # production build
cd deep-agents-ui && yarn lint      # eslint checks
cd deep-agents-ui && yarn format    # prettier format
```
Python tooling is configured in `pyproject.toml` (ruff + mypy):
```bash
uv run ruff format .
uv run ruff check .
uv run mypy .
```

## Coding Style & Naming Conventions
- Python: follow ruff defaults and Google-style docstrings (see `pyproject.toml`); prefer `snake_case` modules and functions.
- TypeScript/React: keep `PascalCase` for components, `camelCase` for hooks/utilities; rely on ESLint + Prettier (Tailwind plugin).
- Skill definitions: keep one skill per directory with a `SKILL.md` entrypoint and clear, task-focused naming.

## Testing Guidelines
- There are no repository-wide tests for `research_agent/` yet; add `pytest` tests when introducing new logic.
- Subprojects have their own suites: see `deepagents_sourcecode/libs/*/Makefile` and `rust-research-agent/README.md` for `make test` or `cargo test`.

## Commit & Pull Request Guidelines
- Git history uses short, descriptive messages in English or Korean with no enforced prefix; keep summaries concise and imperative.
- For PRs, include: a brief summary, testing notes (or “not run”), linked issues, and UI screenshots for frontend changes.

## Configuration & Secrets
- Copy `env.example` to `.env` for API keys; never commit secrets.
- UI-only keys can be set via `NEXT_PUBLIC_LANGSMITH_API_KEY` in `deep-agents-ui/`.
