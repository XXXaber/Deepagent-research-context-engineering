#!/usr/bin/env python3
"""2026 AI 트렌드 키워드 연구 스크립트 (도구 궤적 로깅 포함).

이 스크립트는 다양한 소스에서 2026년 AI 트렌드를 조사하고 보고서를 생성합니다.
각 도구 호출은 TOOL_TRAJECTORY.log 및 TOOL_TRAJECTORY.json에 기록됩니다.

## 스크립트 실행 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│                         main()                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   1. 세션 초기화                                                 │
│      session = ResearchSession(query, session_id)               │
│      trajectory_logger = ToolTrajectoryLogger(session_dir)      │
│                                                                  │
│   2. 다중 소스 검색                                              │
│      ┌─────────────────────────────────────────────────────────┐│
│      │ search_web_sources()    → tavily_search (5회)           ││
│      │ search_github_sources() → github_code_search (3회)       ││
│      │ search_arxiv_sources()  → arxiv_search (3회)            ││
│      └─────────────────────────────────────────────────────────┘│
│                                                                  │
│   3. 키워드 분석                                                 │
│      keywords = extract_keywords(findings)                      │
│                                                                  │
│   4. 결과 저장                                                   │
│      - AI_TREND_REPORT.md                                       │
│      - TOOL_TRAJECTORY.log                                      │
│      - TOOL_TRAJECTORY.json                                     │
│      - SUMMARY.md                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

사용법:
    uv run python scripts/run_ai_trend_research.py
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from research_agent.researcher.ralph_loop import (
    Finding,
    ResearchSession,
    SourceQuality,
    SourceType,
)
from research_agent.tools import (
    arxiv_search,
    github_code_search,
    tavily_search,
)


# ============================================================================
# 콘솔 초기화
# ============================================================================

console = Console()


# ============================================================================
# 도구 궤적 로깅
# ============================================================================


@dataclass
class ToolCallRecord:
    """단일 도구 호출 기록을 나타내는 데이터 클래스.

    Attributes:
        seq: 호출 순서 번호.
        tool_name: 호출된 도구 이름.
        input_args: 도구에 전달된 인자 딕셔너리.
        output_preview: 출력 미리보기 (최대 300자).
        output_length: 전체 출력 길이.
        duration_ms: 호출 소요 시간 (밀리초).
        success: 성공 여부.
        error: 에러 메시지 (실패 시).
        timestamp: 호출 시간 (ISO 8601 형식).
    """

    seq: int  # 호출 순서
    tool_name: str  # 도구 이름
    input_args: dict[str, Any]  # 입력 인자
    output_preview: str  # 출력 미리보기
    output_length: int  # 출력 길이
    duration_ms: float  # 소요 시간 (ms)
    success: bool  # 성공 여부
    error: str | None = None  # 에러 메시지
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ToolTrajectoryLogger:
    """도구 호출 궤적을 로깅하는 클래스.

    각 도구 호출을 기록하고, 세션 종료 시 로그 파일과 JSON 파일로 저장합니다.

    Attributes:
        session_dir: 로그 파일을 저장할 세션 디렉토리.
        calls: 기록된 도구 호출 목록.
        seq: 현재 호출 순서 번호.
    """

    def __init__(self, session_dir: Path):
        """로거를 초기화한다.

        Args:
            session_dir: 로그 파일을 저장할 디렉토리 경로.
        """
        self.session_dir = session_dir
        self.calls: list[ToolCallRecord] = []
        self.seq = 0

    def log_call(
        self,
        tool_name: str,
        input_args: dict[str, Any],
        output: str,
        duration_ms: float,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """도구 호출을 기록한다.

        Args:
            tool_name: 호출된 도구 이름.
            input_args: 도구에 전달된 인자.
            output: 도구 출력 (전체).
            duration_ms: 호출 소요 시간 (밀리초).
            success: 성공 여부 (기본값: True).
            error: 에러 메시지 (선택).
        """
        self.seq += 1
        record = ToolCallRecord(
            seq=self.seq,
            tool_name=tool_name,
            input_args=input_args,
            # 출력 미리보기 (300자로 제한)
            output_preview=output[:300] if len(output) > 300 else output,
            output_length=len(output),
            duration_ms=duration_ms,
            success=success,
            error=error,
        )
        self.calls.append(record)

    def save(self) -> Path:
        """로그를 파일에 저장한다.

        두 가지 형식으로 저장합니다:
        - TOOL_TRAJECTORY.log: 사람이 읽을 수 있는 형식
        - TOOL_TRAJECTORY.json: 프로그래밍적 분석용

        Returns:
            생성된 .log 파일 경로.
        """
        # 텍스트 로그 파일 작성
        log_path = self.session_dir / "TOOL_TRAJECTORY.log"
        with open(log_path, "w") as f:
            # 헤더 작성
            f.write(f"Tool Trajectory Log\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"Total Calls: {len(self.calls)}\n")
            f.write(f"Success: {sum(1 for c in self.calls if c.success)}\n")
            f.write(f"Failed: {sum(1 for c in self.calls if not c.success)}\n")
            f.write("=" * 70 + "\n\n")

            # 각 호출 기록 작성
            for call in self.calls:
                status = "OK" if call.success else f"FAIL: {call.error}"
                f.write(
                    f"[{call.seq}] {call.tool_name} ({status}) [{call.duration_ms:.0f}ms]\n"
                )
                f.write(f"    Timestamp: {call.timestamp}\n")
                f.write(
                    f"    Args: {json.dumps(call.input_args, ensure_ascii=False)}\n"
                )
                f.write(f"    Output Length: {call.output_length} chars\n")
                f.write(f"    Output Preview:\n")
                # 출력 미리보기 (최대 10줄)
                for line in call.output_preview.split("\n")[:10]:
                    f.write(f"      | {line}\n")
                f.write("-" * 70 + "\n\n")

        # JSON 파일 작성
        json_path = self.session_dir / "TOOL_TRAJECTORY.json"
        with open(json_path, "w") as f:
            json.dump([asdict(c) for c in self.calls], f, indent=2, ensure_ascii=False)

        return log_path


# ============================================================================
# 전역 로거 (각 검색 함수에서 사용)
# ============================================================================

trajectory_logger: ToolTrajectoryLogger | None = None


# ============================================================================
# 검색 쿼리 정의
# ============================================================================

# 웹 검색 쿼리 (Tavily)
RESEARCH_QUERIES = [
    "2026 AI trends predictions",
    "AI agent frameworks 2026",
    "context engineering LLM",
    "multimodal AI applications 2026",
    "AI coding assistants trends",
]

# GitHub 코드 검색 쿼리 (리터럴 코드 패턴)
GITHUB_QUERIES = [
    "class Agent(",  # 에이전트 클래스 정의
    "def run_agent(",  # 에이전트 실행 함수
    "context_length =",  # 컨텍스트 길이 설정
]

# arXiv 학술 검색 쿼리
ARXIV_QUERIES = [
    "large language model agents",
    "context window optimization",
    "multimodal foundation models",
]


# ============================================================================
# 소스별 검색 함수
# ============================================================================


def search_web_sources() -> list[Finding]:
    """웹 소스에서 검색을 수행한다.

    RESEARCH_QUERIES의 각 쿼리에 대해 Tavily 검색을 수행하고,
    결과를 Finding 객체로 변환합니다.

    Returns:
        수집된 Finding 객체 목록.
    """
    global trajectory_logger
    findings = []
    console.print("\n[bold cyan]Web Search[/bold cyan]")

    for query in RESEARCH_QUERIES:
        console.print(f"  Searching: {query}...")
        args = {"query": query, "max_results": 2, "topic": "general"}
        start = datetime.now()

        try:
            # Tavily 검색 실행
            result = tavily_search.invoke(args)
            duration = (datetime.now() - start).total_seconds() * 1000

            # 궤적 로깅
            if trajectory_logger:
                trajectory_logger.log_call("tavily_search", args, result, duration)

            # 소스 품질 평가
            quality = SourceQuality.from_source_type(
                SourceType.WEB,
                relevance_score=0.8,
                recency_score=0.9,
            )

            # Finding 객체 생성
            findings.append(
                Finding(
                    content=result[:2000] if len(result) > 2000 else result,
                    source_url=f"tavily://{query}",
                    source_title=f"Web: {query}",
                    confidence=0.7,
                    quality=quality,
                )
            )
            console.print(
                f"    [green]Found results[/green] [dim]({duration:.0f}ms)[/dim]"
            )
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            if trajectory_logger:
                trajectory_logger.log_call(
                    "tavily_search", args, "", duration, success=False, error=str(e)
                )
            console.print(f"    [red]Error: {e}[/red]")

    return findings


def search_github_sources() -> list[Finding]:
    """GitHub 소스에서 코드 검색을 수행한다.

    GITHUB_QUERIES의 각 쿼리에 대해 grep.app API를 통한
    코드 검색을 수행하고, 결과를 Finding 객체로 변환합니다.

    Returns:
        수집된 Finding 객체 목록.
    """
    global trajectory_logger
    findings = []
    console.print("\n[bold cyan]GitHub Code Search[/bold cyan]")

    for query in GITHUB_QUERIES:
        console.print(f"  Searching: {query}...")
        args = {"query": query, "max_results": 5}
        start = datetime.now()

        try:
            # GitHub 코드 검색 실행
            result = github_code_search.invoke(args)
            duration = (datetime.now() - start).total_seconds() * 1000

            # 궤적 로깅
            if trajectory_logger:
                trajectory_logger.log_call("github_code_search", args, result, duration)

            # 소스 품질 평가 (GitHub은 실제 구현 코드이므로 권위도 높음)
            quality = SourceQuality.from_source_type(
                SourceType.GITHUB,
                relevance_score=0.85,
                recency_score=0.7,
            )

            # Finding 객체 생성
            findings.append(
                Finding(
                    content=result[:2000] if len(result) > 2000 else result,
                    source_url=f"github://{query}",
                    source_title=f"GitHub: {query}",
                    confidence=0.75,
                    quality=quality,
                )
            )
            console.print(
                f"    [green]Found results[/green] [dim]({duration:.0f}ms)[/dim]"
            )
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            if trajectory_logger:
                trajectory_logger.log_call(
                    "github_code_search",
                    args,
                    "",
                    duration,
                    success=False,
                    error=str(e),
                )
            console.print(f"    [red]Error: {e}[/red]")

    return findings


def search_arxiv_sources() -> list[Finding]:
    """arXiv 소스에서 학술 논문 검색을 수행한다.

    ARXIV_QUERIES의 각 쿼리에 대해 arXiv API를 통한
    논문 검색을 수행하고, 결과를 Finding 객체로 변환합니다.

    Returns:
        수집된 Finding 객체 목록.
    """
    global trajectory_logger
    findings = []
    console.print("\n[bold cyan]arXiv Academic Search[/bold cyan]")

    for query in ARXIV_QUERIES:
        console.print(f"  Searching: {query}...")
        args = {"query": query, "max_results": 3, "sort_by": "submittedDate"}
        start = datetime.now()

        try:
            # arXiv 검색 실행
            result = arxiv_search.invoke(args)
            duration = (datetime.now() - start).total_seconds() * 1000

            # 궤적 로깅
            if trajectory_logger:
                trajectory_logger.log_call("arxiv_search", args, result, duration)

            # 소스 품질 평가 (학술 논문은 가장 높은 권위도)
            quality = SourceQuality.from_source_type(
                SourceType.ARXIV,
                relevance_score=0.9,
                recency_score=0.85,
            )

            # Finding 객체 생성
            findings.append(
                Finding(
                    content=result[:3000] if len(result) > 3000 else result,
                    source_url=f"arxiv://{query}",
                    source_title=f"arXiv: {query}",
                    confidence=0.9,  # 학술 소스는 높은 신뢰도
                    quality=quality,
                )
            )
            console.print(
                f"    [green]Found results[/green] [dim]({duration:.0f}ms)[/dim]"
            )
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            if trajectory_logger:
                trajectory_logger.log_call(
                    "arxiv_search", args, "", duration, success=False, error=str(e)
                )
            console.print(f"    [red]Error: {e}[/red]")

    return findings


# ============================================================================
# 키워드 분석
# ============================================================================


def extract_keywords(findings: list[Finding]) -> dict[str, int]:
    """발견 항목들에서 AI 관련 키워드를 추출한다.

    사전 정의된 AI 키워드 목록을 기반으로 각 키워드의
    출현 빈도를 계산합니다.

    Args:
        findings: 분석할 Finding 객체 목록.

    Returns:
        키워드 -> 빈도 매핑 (빈도 내림차순 정렬).
    """
    keyword_counts: dict[str, int] = {}

    # AI 관련 키워드 목록
    ai_keywords = [
        # 에이전트 관련
        "agent",
        "agents",
        "agentic",
        # 컨텍스트 관련
        "context",
        "context window",
        "context engineering",
        # 멀티모달 관련
        "multimodal",
        "vision",
        "audio",
        # RAG 및 검색 관련
        "RAG",
        "retrieval",
        "retrieval-augmented",
        # 학습 관련
        "fine-tuning",
        "RLHF",
        "DPO",
        # 추론 관련
        "reasoning",
        "chain-of-thought",
        "CoT",
        # 코딩 관련
        "code generation",
        "coding assistant",
        # 모델 이름
        "GPT",
        "Claude",
        "Gemini",
        "LLaMA",
        "Mistral",
        # 아키텍처 관련
        "transformer",
        "attention",
        "embedding",
        "vector",
        "vectorstore",
        # 프롬프트 관련
        "prompt",
        "prompting",
        "prompt engineering",
        # 도구 사용 관련
        "tool use",
        "function calling",
        # 메모리 관련
        "memory",
        "long-term memory",
        # 안전성 관련
        "safety",
        "alignment",
        "guardrails",
        # 성능 관련
        "inference",
        "latency",
        "optimization",
        # 오픈소스 관련
        "open source",
        "open-source",
        # 평가 관련
        "benchmark",
        "evaluation",
        # 모델 아키텍처
        "MoE",
        "mixture of experts",
        "small language model",
        "SLM",
        # 엣지 AI
        "on-device",
        "edge AI",
    ]

    # 각 발견 항목에서 키워드 카운트
    for finding in findings:
        content_lower = finding.content.lower()
        for kw in ai_keywords:
            if kw.lower() in content_lower:
                count = content_lower.count(kw.lower())
                keyword_counts[kw] = keyword_counts.get(kw, 0) + count

    # 빈도 내림차순 정렬
    return dict(sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True))


# ============================================================================
# 보고서 생성
# ============================================================================


def generate_report(
    session: ResearchSession,
    keywords: dict[str, int],
    output_path: Path,
) -> None:
    """연구 결과 보고서를 Markdown 형식으로 생성한다.

    Args:
        session: 연구 세션 객체.
        keywords: 키워드 -> 빈도 매핑.
        output_path: 보고서 저장 경로.
    """
    # 보고서 헤더
    report_content = f"""# 2026 AI 트렌드 키워드 연구 리포트

**생성일:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**세션 ID:** {session.session_id}
**총 소스 수:** {len(session.findings)}
**Coverage Score:** {session.ralph_loop.state.coverage_score:.2%}

---

## 핵심 트렌드 키워드 (Top 20)

| 순위 | 키워드 | 빈도 |
|------|--------|------|
"""
    # Top 20 키워드 테이블
    for i, (kw, count) in enumerate(list(keywords.items())[:20], 1):
        report_content += f"| {i} | {kw} | {count} |\n"

    # 주요 발견사항 섹션
    report_content += """
---

## 주요 발견사항

### 1. Agent & Agentic AI
- AI 에이전트 프레임워크가 2026년 핵심 트렌드
- 자율적 작업 수행 및 도구 사용 능력 강조
- Multi-agent 시스템의 부상

### 2. Context Engineering
- 긴 컨텍스트 윈도우 활용 최적화
- 파일시스템 기반 컨텍스트 관리
- 효율적인 정보 검색 및 주입

### 3. Multimodal AI
- 텍스트, 이미지, 오디오, 비디오 통합
- Vision-Language 모델의 발전
- 실시간 멀티모달 처리

### 4. Reasoning & CoT
- Chain-of-Thought 추론 개선
- 복잡한 문제 해결 능력 향상
- Self-reflection 및 자기 개선

### 5. Code & Development
- AI 코딩 어시스턴트의 고도화
- 전체 개발 워크플로우 자동화
- 코드 리뷰 및 디버깅 지원

---

## 소스 분석

"""
    # 소스 유형별 통계
    source_types = {}
    for f in session.findings:
        if f.quality:
            st = f.quality.source_type
            source_types[st] = source_types.get(st, 0) + 1

    for st, count in source_types.items():
        report_content += f"- **{st}**: {count}개 소스\n"

    # 상세 소스 목록
    report_content += f"""
---

## 상세 소스 목록

"""
    for i, f in enumerate(session.findings, 1):
        quality_score = f.quality.overall_score if f.quality else 0
        report_content += f"""### 소스 {i}: {f.source_title}
- **신뢰도:** {f.confidence:.0%}
- **품질 점수:** {quality_score:.2f}
- **URL:** {f.source_url}

<details>
<summary>내용 미리보기</summary>

{f.content[:500]}...

</details>

---

"""

    # 파일 저장
    output_path.write_text(report_content)


# ============================================================================
# 메인 함수
# ============================================================================


def main() -> None:
    """스크립트 메인 함수.

    1. 세션 초기화 및 로거 설정
    2. 다중 소스 검색 수행
    3. 키워드 분석
    4. 보고서 및 로그 생성
    """
    global trajectory_logger

    # 시작 배너 출력
    console.print(
        Panel(
            "[bold cyan]2026 AI Trend Keyword Research[/bold cyan]\n"
            "[dim]Collecting and analyzing data from multiple sources[/dim]",
            title="Research Started",
        )
    )

    # 세션 초기화
    session = ResearchSession(
        query="2026 AI Trends and Keywords",
        session_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
    )
    session.initialize()

    # 도구 궤적 로거 초기화
    trajectory_logger = ToolTrajectoryLogger(session.session_dir)

    # 세션 정보 출력
    console.print(f"\n[dim]Session: {session.session_id}[/dim]")
    console.print(f"[dim]Workspace: {session.session_dir}[/dim]\n")

    # 프로그레스 표시와 함께 데이터 수집
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Collecting data...", total=None)

        # 웹 소스 검색
        web_findings = search_web_sources()
        for f in web_findings:
            session.add_finding(f)

        # GitHub 소스 검색
        github_findings = search_github_sources()
        for f in github_findings:
            session.add_finding(f)

        # arXiv 소스 검색
        arxiv_findings = search_arxiv_sources()
        for f in arxiv_findings:
            session.add_finding(f)

        progress.update(task, description="Analyzing keywords...")

    # 키워드 분석
    keywords = extract_keywords(session.findings)

    # Top 10 키워드 테이블 출력
    table = Table(title="Top 10 AI 트렌드 키워드")
    table.add_column("순위", style="cyan")
    table.add_column("키워드", style="green")
    table.add_column("빈도", style="yellow")

    for i, (kw, count) in enumerate(list(keywords.items())[:10], 1):
        table.add_row(str(i), kw, str(count))

    console.print("\n")
    console.print(table)

    # 보고서 생성
    report_path = session.session_dir / "AI_TREND_REPORT.md"
    generate_report(session, keywords, report_path)

    # 궤적 로그 저장
    trajectory_log_path = trajectory_logger.save() if trajectory_logger else None

    # 세션 마무리
    summary_path = session.finalize()

    # 완료 배너 출력
    console.print(
        Panel(
            f"[bold green]Research Complete![/bold green]\n\n"
            f"Total Sources: {len(session.findings)}\n"
            f"Coverage: {session.ralph_loop.state.coverage_score:.2%}\n"
            f"Keywords Found: {len(keywords)}\n"
            f"Tool Calls: {len(trajectory_logger.calls) if trajectory_logger else 0}\n\n"
            f"[dim]Report: {report_path}[/dim]\n"
            f"[dim]Summary: {summary_path}[/dim]\n"
            f"[dim]Tool Trajectory: {trajectory_log_path}[/dim]",
            title="Research Complete",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
