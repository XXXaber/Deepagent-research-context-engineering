"""Deep Research Runner - Ralph Loop 패턴 기반 반복 연구 실행기.

DeepAgents 스타일의 자율 루프 실행. 각 반복은 새로운 컨텍스트로 시작하며,
파일시스템이 메모리 역할을 합니다.

Usage:
    # Python API
    from research_agent.researcher.runner import run_deep_research
    result = await run_deep_research("Context Engineering best practices", depth="deep")

    # CLI
    uv run python -m research_agent.researcher.runner "Your research query" --depth deep
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from research_agent.researcher.agent import create_researcher_agent
from research_agent.researcher.depth import ResearchDepth, get_depth_config
from research_agent.researcher.ralph_loop import ResearchSession

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

console = Console()

# Colors matching DeepAgents CLI
COLORS = {
    "primary": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "dim": "dim",
}


class ResearchRunner:
    """Ralph Loop 패턴 기반 연구 실행기."""

    def __init__(
        self,
        query: str,
        depth: ResearchDepth | str = ResearchDepth.DEEP,
        model: str | None = None,
    ):
        self.query = query
        self.depth = ResearchDepth(depth) if isinstance(depth, str) else depth
        self.config = get_depth_config(self.depth)
        self.model_name = model

        # Session 초기화
        self.session = ResearchSession(query, self.config)
        self.agent: CompiledStateGraph | None = None

    def _create_agent(self) -> CompiledStateGraph:
        """연구 에이전트 생성."""
        return create_researcher_agent(
            model=self.model_name,
            depth=self.depth,
        )

    def _build_iteration_prompt(self, iteration: int) -> str:
        """각 반복에 사용할 프롬프트 생성."""
        max_iter = self.config.max_ralph_iterations
        iter_display = f"{iteration}/{max_iter}" if max_iter > 0 else str(iteration)

        return f"""## Research Iteration {iter_display}

### Query
{self.query}

### Instructions
Your previous work is in the filesystem. Check `research_workspace/session_{self.session.session_id}/` for:
- TODO.md: Progress tracking
- FINDINGS.md: Discovered information

1. Review existing findings
2. Identify knowledge gaps
3. Conduct targeted searches
4. Update research files with new findings
5. Update TODO.md with progress

### Completion
When research is comprehensive (coverage >= {self.config.coverage_threshold:.0%}):
- Output `<promise>RESEARCH_COMPLETE</promise>`
- Only output this when truly complete - DO NOT lie to exit early

### Current Stats
- Iteration: {iteration}
- Findings: {self.session.ralph_loop.state.findings_count}
- Coverage: {self.session.ralph_loop.state.coverage_score:.2%}

Make progress. You'll be called again if not complete.
"""

    async def _execute_iteration(self, iteration: int) -> dict:
        """단일 반복 실행."""
        if self.agent is None:
            self.agent = self._create_agent()

        prompt = self._build_iteration_prompt(iteration)

        # 에이전트 실행
        result = await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}]}
        )

        return result

    def _check_completion(self, result: dict) -> bool:
        """완료 여부 확인."""
        # 메시지에서 완료 promise 체크
        messages = result.get("messages", [])
        for msg in messages:
            content = getattr(msg, "content", str(msg))
            if isinstance(content, str):
                if "<promise>RESEARCH_COMPLETE</promise>" in content:
                    return True
                if "RESEARCH_COMPLETE" in content:
                    # 좀 더 느슨한 체크
                    return True

        # Coverage 기반 체크
        return self.session.ralph_loop.is_complete()

    async def run(self) -> Path:
        """연구 실행 및 결과 반환."""
        console.print(
            Panel(
                f"[bold {COLORS['primary']}]Deep Research Mode[/bold {COLORS['primary']}]\n"
                f"[dim]Query: {self.query}[/dim]\n"
                f"[dim]Depth: {self.depth.value}[/dim]\n"
                f"[dim]Max iterations: {self.config.max_ralph_iterations or 'unlimited'}[/dim]",
                title="Research Session Started",
                border_style=COLORS["primary"],
            )
        )

        # 세션 초기화
        self.session.initialize()
        console.print(
            f"[dim]Session ID: {self.session.session_id}[/dim]\n"
            f"[dim]Workspace: {self.session.session_dir}[/dim]\n"
        )

        iteration = 1
        max_iterations = self.config.max_ralph_iterations or 100  # Safety limit

        try:
            while iteration <= max_iterations:
                console.print(
                    f"\n[bold {COLORS['primary']}]{'=' * 60}[/bold {COLORS['primary']}]"
                )
                console.print(
                    f"[bold {COLORS['primary']}]ITERATION {iteration}[/bold {COLORS['primary']}]"
                )
                console.print(
                    f"[bold {COLORS['primary']}]{'=' * 60}[/bold {COLORS['primary']}]\n"
                )

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Researching...", total=None)

                    result = await self._execute_iteration(iteration)

                    progress.update(task, description="Checking completion...")

                # 완료 체크
                if self._check_completion(result):
                    console.print(
                        f"\n[bold {COLORS['success']}]Research complete![/bold {COLORS['success']}]"
                    )
                    break

                # 다음 반복 준비
                is_done = self.session.complete_iteration()
                if is_done:
                    console.print(
                        f"\n[bold {COLORS['success']}]Coverage threshold reached![/bold {COLORS['success']}]"
                    )
                    break

                console.print(f"[dim]...continuing to iteration {iteration + 1}[/dim]")
                iteration += 1

        except KeyboardInterrupt:
            console.print(
                f"\n[bold {COLORS['warning']}]Stopped after {iteration} iterations[/bold {COLORS['warning']}]"
            )

        # 최종 결과 생성
        summary_path = self.session.finalize()

        # 결과 표시
        console.print(
            Panel(
                f"[bold]Research Summary[/bold]\n"
                f"Total Iterations: {iteration}\n"
                f"Findings: {self.session.ralph_loop.state.findings_count}\n"
                f"Coverage: {self.session.ralph_loop.state.coverage_score:.2%}\n"
                f"\n[dim]Output: {summary_path}[/dim]",
                title="Research Complete",
                border_style=COLORS["success"],
            )
        )

        # 생성된 파일 목록
        console.print(f"\n[bold]Files created in {self.session.session_dir}:[/bold]")
        for f in sorted(self.session.session_dir.rglob("*")):
            if f.is_file():
                console.print(
                    f"  {f.relative_to(self.session.session_dir)}", style="dim"
                )

        return summary_path


async def run_deep_research(
    query: str,
    depth: ResearchDepth | str = ResearchDepth.DEEP,
    model: str | None = None,
) -> Path:
    """Deep Research 실행 (async API).

    Args:
        query: 연구 주제
        depth: 연구 깊이 (quick, standard, deep, exhaustive)
        model: 사용할 LLM 모델명

    Returns:
        Path: 연구 결과 요약 파일 경로
    """
    runner = ResearchRunner(query, depth, model)
    return await runner.run()


def main() -> None:
    """CLI 엔트리포인트."""
    parser = argparse.ArgumentParser(
        description="Deep Research - Ralph Loop 패턴 기반 자율 연구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m research_agent.researcher.runner "Context Engineering 전략 분석"
  python -m research_agent.researcher.runner "LLM Agent 아키텍처" --depth deep
  python -m research_agent.researcher.runner "RAG 시스템 비교" --depth exhaustive --model gpt-4.1
        """,
    )
    parser.add_argument("query", help="연구 주제 (무엇을 연구할지)")
    parser.add_argument(
        "--depth",
        choices=["quick", "standard", "deep", "exhaustive"],
        default="deep",
        help="연구 깊이 (기본: deep)",
    )
    parser.add_argument(
        "--model",
        help="사용할 LLM 모델 (예: gpt-4.1, claude-sonnet-4-20250514)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            run_deep_research(
                query=args.query,
                depth=args.depth,
                model=args.model,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted by user[/dim]")


if __name__ == "__main__":
    main()
