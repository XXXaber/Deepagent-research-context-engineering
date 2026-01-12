#!/usr/bin/env python3
"""Tool Trajectory verification script with detailed logging.

This script verifies the research agent tools work correctly by:
1. Testing each tool individually with logging
2. Verifying the tool call sequence (trajectory)
3. Outputting detailed logs for debugging

Usage:
    uv run python scripts/verify_tool_trajectory.py
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
)
log = logging.getLogger("tool_trajectory")
console = Console()


@dataclass
class ToolCall:
    tool_name: str
    input_args: dict[str, Any]
    output: str
    duration_ms: float
    success: bool
    error: str | None = None


@dataclass
class ToolTrajectory:
    calls: list[ToolCall] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)

    def add_call(self, call: ToolCall) -> None:
        self.calls.append(call)
        log.info(
            f"[{len(self.calls)}] {call.tool_name} "
            f"({'OK' if call.success else 'FAIL'}) "
            f"[{call.duration_ms:.0f}ms]"
        )

    def summary(self) -> str:
        total = len(self.calls)
        success = sum(1 for c in self.calls if c.success)
        return f"Total: {total}, Success: {success}, Failed: {total - success}"


def test_tool(
    trajectory: ToolTrajectory,
    tool_name: str,
    tool_func: Any,
    args: dict[str, Any],
) -> bool:
    log.debug(f"Testing {tool_name} with args: {args}")
    start = datetime.now()

    try:
        result = tool_func.invoke(args)
        duration = (datetime.now() - start).total_seconds() * 1000

        call = ToolCall(
            tool_name=tool_name,
            input_args=args,
            output=result[:500] if len(result) > 500 else result,
            duration_ms=duration,
            success=True,
        )
        trajectory.add_call(call)
        return True

    except Exception as e:
        duration = (datetime.now() - start).total_seconds() * 1000
        call = ToolCall(
            tool_name=tool_name,
            input_args=args,
            output="",
            duration_ms=duration,
            success=False,
            error=str(e),
        )
        trajectory.add_call(call)
        log.error(f"Error in {tool_name}: {e}")
        return False


def main() -> int:
    console.print(
        Panel(
            "[bold cyan]Tool Trajectory Verification[/bold cyan]\n"
            "[dim]Testing research agent tools with detailed logging[/dim]",
            title="Verification Started",
        )
    )

    from research_agent.tools import (
        arxiv_search,
        github_code_search,
        library_docs_search,
        tavily_search,
        think_tool,
    )

    trajectory = ToolTrajectory()

    console.print("\n[bold]Phase 1: Individual Tool Tests[/bold]\n")

    test_cases = [
        ("think_tool", think_tool, {"reflection": "Testing reflection capability"}),
        (
            "tavily_search",
            tavily_search,
            {"query": "context engineering", "max_results": 1},
        ),
        (
            "arxiv_search",
            arxiv_search,
            {"query": "large language model", "max_results": 2},
        ),
        (
            "github_code_search",
            github_code_search,
            {"query": "useState(", "max_results": 2},
        ),
    ]

    for tool_name, tool_func, args in test_cases:
        console.print(f"  Testing: [cyan]{tool_name}[/cyan]...")
        test_tool(trajectory, tool_name, tool_func, args)

    console.print("\n[bold]Phase 2: Tool Trajectory Analysis[/bold]\n")

    table = Table(title="Tool Call Trajectory")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Tool", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Duration", style="blue")
    table.add_column("Output Preview", style="dim", max_width=50)

    for i, call in enumerate(trajectory.calls, 1):
        status = (
            "[green]OK[/green]" if call.success else f"[red]FAIL: {call.error}[/red]"
        )
        output_preview = (
            call.output[:50] + "..." if len(call.output) > 50 else call.output
        )
        output_preview = output_preview.replace("\n", " ")
        table.add_row(
            str(i),
            call.tool_name,
            status,
            f"{call.duration_ms:.0f}ms",
            output_preview,
        )

    console.print(table)

    console.print("\n[bold]Phase 3: Verification Summary[/bold]\n")

    total_calls = len(trajectory.calls)
    success_calls = sum(1 for c in trajectory.calls if c.success)
    failed_calls = total_calls - success_calls

    summary_table = Table(show_header=False)
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value")

    summary_table.add_row("Total Tool Calls", str(total_calls))
    summary_table.add_row("Successful", f"[green]{success_calls}[/green]")
    summary_table.add_row(
        "Failed",
        f"[red]{failed_calls}[/red]" if failed_calls > 0 else "[green]0[/green]",
    )
    summary_table.add_row(
        "Total Duration",
        f"{sum(c.duration_ms for c in trajectory.calls):.0f}ms",
    )

    console.print(summary_table)

    log_path = Path("research_workspace") / "tool_trajectory.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w") as f:
        f.write(f"Tool Trajectory Log - {datetime.now().isoformat()}\n")
        f.write("=" * 60 + "\n\n")
        for i, call in enumerate(trajectory.calls, 1):
            f.write(f"[{i}] {call.tool_name}\n")
            f.write(f"    Args: {call.input_args}\n")
            f.write(f"    Success: {call.success}\n")
            f.write(f"    Duration: {call.duration_ms:.0f}ms\n")
            if call.error:
                f.write(f"    Error: {call.error}\n")
            f.write(f"    Output:\n{call.output}\n")
            f.write("-" * 40 + "\n")

    console.print(f"\n[dim]Log saved to: {log_path}[/dim]")

    if failed_calls > 0:
        console.print(
            Panel(
                f"[red]Verification FAILED[/red]\n"
                f"{failed_calls} tool(s) failed. Check logs above.",
                border_style="red",
            )
        )
        return 1

    console.print(
        Panel(
            "[green]Verification PASSED[/green]\n"
            "All tools executed successfully with correct trajectory.",
            border_style="green",
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
