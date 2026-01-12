"""Ralph Loop 연구 패턴 모듈.

이 모듈은 반복적 연구 패턴(Ralph Loop)을 구현합니다.
에이전트가 연구 → 반성 → 갱신 사이클을 통해 점진적으로
연구 커버리지를 높여가는 방식을 지원합니다.

## Ralph Loop 동작 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│                      Ralph Loop 사이클                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│   │   Plan   │───▶│  Search  │───▶│ Extract  │───▶│ Validate │ │
│   │ (계획)   │    │ (검색)   │    │ (추출)   │    │ (검증)   │ │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│        ▲                                               │        │
│        │                                               ▼        │
│   ┌──────────┐                                   ┌──────────┐  │
│   │ Continue │◀──────────────────────────────────│  Update  │  │
│   │ (계속?)  │                                   │(커버리지)│  │
│   └──────────┘                                   └──────────┘  │
│        │                                                        │
│        ▼                                                        │
│   ┌──────────┐                                                  │
│   │ Complete │  coverage >= threshold OR max iterations        │
│   │  (완료)  │                                                  │
│   └──────────┘                                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

v2 업데이트 (2026-01):
- RalphLoopState 상태 관리 클래스
- SourceQuality 소스 품질 평가
- Finding 발견 항목 데이터 클래스
- ResearchSession 세션 관리
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .depth import DepthConfig


# ============================================================================
# Ralph Loop 상태 관리
# ============================================================================


@dataclass
class RalphLoopState:
    """Ralph Loop의 현재 상태를 추적하는 데이터 클래스.

    Attributes:
        iteration: 현재 반복 횟수 (1부터 시작).
        max_iterations: 최대 허용 반복 횟수 (0이면 무제한).
        completion_promise: 완료 시 출력할 약속 태그.
        started_at: 루프 시작 시간 (ISO 8601 형식).
        findings_count: 현재까지 수집된 발견 항목 수.
        coverage_score: 현재 커버리지 점수 (0.0 ~ 1.0).
    """

    iteration: int = 1  # 현재 반복 횟수
    max_iterations: int = 0  # 최대 반복 (0 = 무제한)
    completion_promise: str = "RESEARCH_COMPLETE"  # 완료 태그
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    findings_count: int = 0  # 발견 항목 수
    coverage_score: float = 0.0  # 커버리지 점수

    def is_max_reached(self) -> bool:
        """최대 반복 횟수에 도달했는지 확인한다.

        Returns:
            max_iterations > 0이고 현재 반복이 최대 이상이면 True.
        """
        return self.max_iterations > 0 and self.iteration >= self.max_iterations


# ============================================================================
# 소스 유형 및 품질
# ============================================================================


class SourceType:
    """소스 유형을 나타내는 상수 클래스.

    각 소스 유형은 다른 권위도(authority) 점수를 갖습니다:
    - ARXIV: 0.9 (학술 논문, 가장 높은 권위)
    - DOCS: 0.85 (공식 문서)
    - GITHUB: 0.7 (실제 구현 코드)
    - LOCAL: 0.6 (로컬 코드베이스)
    - WEB: 0.5 (일반 웹 검색, 가장 낮은 권위)
    """

    WEB = "web"  # 웹 검색 결과
    ARXIV = "arxiv"  # arXiv 논문
    GITHUB = "github"  # GitHub 코드
    DOCS = "docs"  # 공식 문서
    LOCAL = "local"  # 로컬 코드베이스


@dataclass
class SourceQuality:
    """소스의 품질을 평가하는 데이터 클래스.

    품질 점수는 세 가지 요소의 가중 평균으로 계산됩니다:
    - recency (최신성): 20%
    - authority (권위도): 40%
    - relevance (관련성): 40%

    추가로 검증 횟수에 따른 보너스가 적용됩니다 (최대 15%).

    Attributes:
        source_type: 소스 유형 (SourceType 상수).
        recency_score: 최신성 점수 (0.0 ~ 1.0).
        authority_score: 권위도 점수 (0.0 ~ 1.0).
        relevance_score: 관련성 점수 (0.0 ~ 1.0).
        verification_count: 다른 소스에 의한 검증 횟수.
    """

    source_type: str  # 소스 유형
    recency_score: float = 0.0  # 최신성 (0.0 ~ 1.0)
    authority_score: float = 0.0  # 권위도 (0.0 ~ 1.0)
    relevance_score: float = 0.0  # 관련성 (0.0 ~ 1.0)
    verification_count: int = 0  # 검증 횟수

    @property
    def overall_score(self) -> float:
        """전체 품질 점수를 계산한다.

        가중 평균 + 검증 보너스로 계산됩니다.

        Returns:
            0.0 ~ 1.0 범위의 전체 품질 점수.
        """
        # 가중 평균 계산 (recency 20%, authority 40%, relevance 40%)
        base_score = (
            self.recency_score * 0.2
            + self.authority_score * 0.4
            + self.relevance_score * 0.4
        )
        # 검증 보너스 (검증당 5%, 최대 15%)
        verification_bonus = min(self.verification_count * 0.05, 0.15)
        # 최대 1.0으로 제한
        return min(base_score + verification_bonus, 1.0)

    @classmethod
    def from_source_type(cls, source_type: str, **kwargs) -> "SourceQuality":
        """소스 유형에서 SourceQuality 객체를 생성한다.

        소스 유형에 따른 기본 권위도 점수가 자동으로 적용됩니다.

        Args:
            source_type: SourceType 상수 중 하나.
            **kwargs: 추가 점수 값 (recency_score, relevance_score 등).

        Returns:
            생성된 SourceQuality 객체.
        """
        # 소스 유형별 기본 권위도 점수
        authority_defaults = {
            SourceType.ARXIV: 0.9,  # 학술 논문 - 최고 권위
            SourceType.DOCS: 0.85,  # 공식 문서
            SourceType.GITHUB: 0.7,  # 실제 구현
            SourceType.WEB: 0.5,  # 일반 웹
            SourceType.LOCAL: 0.6,  # 로컬 코드
        }
        return cls(
            source_type=source_type,
            authority_score=kwargs.get(
                "authority_score", authority_defaults.get(source_type, 0.5)
            ),
            recency_score=kwargs.get("recency_score", 0.5),
            relevance_score=kwargs.get("relevance_score", 0.5),
            verification_count=kwargs.get("verification_count", 0),
        )


# ============================================================================
# 연구 발견 항목
# ============================================================================


@dataclass
class Finding:
    """연구에서 발견된 항목을 나타내는 데이터 클래스.

    Attributes:
        content: 발견 내용 (텍스트).
        source_url: 소스 URL.
        source_title: 소스 제목.
        confidence: 신뢰도 점수 (0.0 ~ 1.0).
        verified_by: 이 발견을 검증한 다른 소스 URL 목록.
        quality: 소스 품질 정보 (선택).
    """

    content: str  # 발견 내용
    source_url: str  # 소스 URL
    source_title: str  # 소스 제목
    confidence: float  # 신뢰도 (0.0 ~ 1.0)
    verified_by: list[str] = field(default_factory=list)  # 검증 소스
    quality: SourceQuality | None = None  # 소스 품질

    @property
    def weighted_confidence(self) -> float:
        """품질 가중 신뢰도를 계산한다.

        소스 품질이 있으면 신뢰도에 품질 점수를 곱합니다.

        Returns:
            품질 가중치가 적용된 신뢰도 점수.
        """
        if self.quality is None:
            return self.confidence
        return self.confidence * self.quality.overall_score


# ============================================================================
# Ralph Loop 관리자
# ============================================================================


class ResearchRalphLoop:
    """Ralph Loop 연구 패턴을 관리하는 클래스.

    상태를 파일에 저장/로드하고, 연구 진행 상황을 추적합니다.

    Attributes:
        STATE_FILE: 상태 파일 경로 (.claude/research-ralph-loop.local.md).
        query: 연구 쿼리.
        max_iterations: 최대 반복 횟수.
        coverage_threshold: 완료 판정 커버리지 임계값.
        sources: 사용 가능한 소스 목록.
        state: 현재 Ralph Loop 상태.
    """

    STATE_FILE = Path(".claude/research-ralph-loop.local.md")

    def __init__(
        self,
        query: str,
        depth_config: DepthConfig | None = None,
        max_iterations: int = 10,
        coverage_threshold: float = 0.85,
    ):
        """Ralph Loop를 초기화한다.

        Args:
            query: 연구 쿼리 문자열.
            depth_config: 깊이 설정 (있으면 이 값이 우선).
            max_iterations: 기본 최대 반복 횟수.
            coverage_threshold: 기본 커버리지 임계값.
        """
        self.query = query

        # depth_config가 있으면 해당 값 사용, 없으면 기본값 사용
        self.max_iterations = (
            depth_config.max_ralph_iterations if depth_config else max_iterations
        )
        self.coverage_threshold = (
            depth_config.coverage_threshold if depth_config else coverage_threshold
        )
        self.sources = depth_config.sources if depth_config else ("web",)

        # 초기 상태 생성
        self.state = RalphLoopState(max_iterations=self.max_iterations)

    def create_research_prompt(self) -> str:
        """현재 반복에 대한 연구 프롬프트를 생성한다.

        Returns:
            에이전트에게 전달할 Markdown 형식의 연구 프롬프트.
        """
        sources_str = ", ".join(self.sources)
        return f"""## Research Iteration {self.state.iteration}/{self.max_iterations or "∞"}

### Original Query
{self.query}

### Previous Work
Check `research_workspace/` for previous findings.
Read TODO.md for tracked progress.

### Instructions
1. Review existing findings
2. Identify knowledge gaps
3. Conduct targeted searches using: {sources_str}
4. Update research files with new findings
5. Update TODO.md with progress

### Completion Criteria
Output `<promise>{self.state.completion_promise}</promise>` ONLY when:
- Coverage score >= {self.coverage_threshold} (current: {self.state.coverage_score:.2f})
- All major aspects addressed
- Findings cross-validated with 2+ sources
- DO NOT lie to exit

### Current Stats
- Iteration: {self.state.iteration}
- Findings: {self.state.findings_count}
- Coverage: {self.state.coverage_score:.2%}
"""

    def save_state(self) -> None:
        """현재 상태를 파일에 저장한다."""
        # 디렉토리 생성
        self.STATE_FILE.parent.mkdir(exist_ok=True)

        # YAML frontmatter 형식으로 저장
        promise_yaml = f'"{self.state.completion_promise}"'
        content = f"""---
active: true
iteration: {self.state.iteration}
max_iterations: {self.state.max_iterations}
completion_promise: {promise_yaml}
started_at: "{self.state.started_at}"
findings_count: {self.state.findings_count}
coverage_score: {self.state.coverage_score}
---

{self.create_research_prompt()}
"""
        self.STATE_FILE.write_text(content)

    def load_state(self) -> bool:
        """파일에서 상태를 로드한다.

        Returns:
            상태 파일이 존재하고 성공적으로 로드되면 True.
        """
        if not self.STATE_FILE.exists():
            return False

        content = self.STATE_FILE.read_text()
        lines = content.split("\n")

        # YAML frontmatter 파싱
        in_frontmatter = False
        for line in lines:
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                continue
            if not in_frontmatter:
                continue

            # 각 필드 파싱
            if line.startswith("iteration:"):
                self.state.iteration = int(line.split(":")[1].strip())
            elif line.startswith("findings_count:"):
                self.state.findings_count = int(line.split(":")[1].strip())
            elif line.startswith("coverage_score:"):
                self.state.coverage_score = float(line.split(":")[1].strip())

        return True

    def increment_iteration(self) -> None:
        """반복 횟수를 증가시키고 상태를 저장한다."""
        self.state.iteration += 1
        self.save_state()

    def update_coverage(self, findings_count: int, coverage_score: float) -> None:
        """커버리지 정보를 갱신하고 상태를 저장한다.

        Args:
            findings_count: 새로운 발견 항목 수.
            coverage_score: 새로운 커버리지 점수.
        """
        self.state.findings_count = findings_count
        self.state.coverage_score = coverage_score
        self.save_state()

    def is_complete(self) -> bool:
        """연구가 완료되었는지 확인한다.

        Returns:
            최대 반복에 도달했거나 커버리지 임계값을 넘으면 True.
        """
        # 최대 반복 도달 확인
        if self.state.is_max_reached():
            return True
        # 커버리지 임계값 확인
        return self.state.coverage_score >= self.coverage_threshold

    def cleanup(self) -> None:
        """상태 파일을 삭제한다."""
        if self.STATE_FILE.exists():
            self.STATE_FILE.unlink()


# ============================================================================
# 연구 세션 관리
# ============================================================================


class ResearchSession:
    """연구 세션을 관리하는 클래스.

    세션별 디렉토리를 생성하고, 발견 항목을 기록하며,
    Ralph Loop를 통해 진행 상황을 추적합니다.

    Attributes:
        WORKSPACE: 연구 작업 공간 루트 디렉토리.
        query: 연구 쿼리.
        session_id: 세션 고유 식별자.
        session_dir: 세션 디렉토리 경로.
        ralph_loop: Ralph Loop 관리자.
        findings: 수집된 발견 항목 목록.
    """

    WORKSPACE = Path("research_workspace")

    def __init__(
        self,
        query: str,
        depth_config: DepthConfig | None = None,
        session_id: str | None = None,
    ):
        """연구 세션을 초기화한다.

        Args:
            query: 연구 쿼리 문자열.
            depth_config: 깊이 설정 (선택).
            session_id: 세션 ID (없으면 현재 시간으로 생성).
        """
        self.query = query
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.WORKSPACE / f"session_{self.session_id}"
        self.ralph_loop = ResearchRalphLoop(query, depth_config)
        self.findings: list[Finding] = []

    def initialize(self) -> None:
        """세션 디렉토리와 초기 파일들을 생성한다."""
        # 세션 디렉토리 생성
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # TODO.md 초기 파일 생성
        todo_content = f"""# Research TODO

## Query
{self.query}

## Progress
- [ ] Initial exploration (iteration 1)
- [ ] Deep dive into key topics
- [ ] Cross-validation of findings
- [ ] Final synthesis

## Findings
(Updated during research)
"""
        (self.session_dir / "TODO.md").write_text(todo_content)

        # FINDINGS.md 초기 파일 생성
        findings_content = f"""# Research Findings

## Query: {self.query}

## Sources
(Updated during research)

## Key Findings
(Updated during research)
"""
        (self.session_dir / "FINDINGS.md").write_text(findings_content)

        # Ralph Loop 상태 저장
        self.ralph_loop.save_state()

    def get_current_prompt(self) -> str:
        """현재 연구 프롬프트를 반환한다.

        Returns:
            Ralph Loop의 현재 연구 프롬프트.
        """
        return self.ralph_loop.create_research_prompt()

    def add_finding(self, finding: Finding) -> None:
        """발견 항목을 추가하고 관련 파일들을 갱신한다.

        Args:
            finding: 추가할 Finding 객체.
        """
        self.findings.append(finding)
        self._update_findings_file()
        self._recalculate_coverage()

    def _update_findings_file(self) -> None:
        """FINDINGS.md 파일을 현재 발견 항목으로 갱신한다."""
        findings_path = self.session_dir / "FINDINGS.md"
        content = f"""# Research Findings

## Query: {self.query}

## Sources ({len(self.findings)})
"""
        # 각 발견 항목을 Markdown으로 추가
        for i, f in enumerate(self.findings, 1):
            content += f"\n### Source {i}: {f.source_title}\n"
            content += f"- URL: {f.source_url}\n"
            content += f"- Confidence: {f.confidence:.0%}\n"
            if f.verified_by:
                content += f"- Verified by: {', '.join(f.verified_by)}\n"
            if f.quality:
                content += f"- Quality Score: {f.quality.overall_score:.2f}\n"
                content += f"- Source Type: {f.quality.source_type}\n"
            content += f"\n{f.content}\n"

        findings_path.write_text(content)

    def _recalculate_coverage(self) -> None:
        """현재 발견 항목들을 기반으로 커버리지를 재계산한다."""
        if not self.findings:
            coverage = 0.0
        else:
            # 품질 가중 신뢰도의 평균 계산
            weighted_scores = [f.weighted_confidence for f in self.findings]
            avg_weighted = sum(weighted_scores) / len(weighted_scores)

            # 수량 요소 (최대 10개까지 선형 증가)
            quantity_factor = min(len(self.findings) / 10, 1.0)

            # 소스 다양성 요소
            source_diversity = self._calculate_source_diversity()

            # 최종 커버리지 계산
            coverage = avg_weighted * quantity_factor * (0.8 + 0.2 * source_diversity)

        # Ralph Loop 상태 갱신
        self.ralph_loop.update_coverage(len(self.findings), coverage)

    def _calculate_source_diversity(self) -> float:
        """소스 유형의 다양성을 계산한다.

        Returns:
            0.0 ~ 1.0 범위의 다양성 점수 (4종류 이상이면 1.0).
        """
        if not self.findings:
            return 0.0

        # 고유한 소스 유형 수집
        source_types = set()
        for f in self.findings:
            if f.quality:
                source_types.add(f.quality.source_type)
            else:
                source_types.add("unknown")

        # 4종류를 기준으로 다양성 점수 계산
        return min(len(source_types) / 4, 1.0)

    def complete_iteration(self) -> bool:
        """현재 반복을 완료하고 다음 반복으로 진행한다.

        Returns:
            연구가 완전히 완료되면 True.
        """
        # 완료 여부 확인
        if self.ralph_loop.is_complete():
            return True

        # 다음 반복으로 진행
        self.ralph_loop.increment_iteration()
        return False

    def finalize(self) -> Path:
        """세션을 종료하고 요약 파일을 생성한다.

        Returns:
            생성된 SUMMARY.md 파일 경로.
        """
        # Ralph Loop 상태 파일 정리
        self.ralph_loop.cleanup()

        # SUMMARY.md 생성
        summary_path = self.session_dir / "SUMMARY.md"
        summary_content = f"""# Research Summary

## Query
{self.query}

## Statistics
- Total Iterations: {self.ralph_loop.state.iteration}
- Total Findings: {len(self.findings)}
- Final Coverage: {self.ralph_loop.state.coverage_score:.2%}

## Session
- ID: {self.session_id}
- Started: {self.ralph_loop.state.started_at}
- Completed: {datetime.now(timezone.utc).isoformat()}

## Output Files
- TODO.md: Progress tracking
- FINDINGS.md: Detailed findings
- SUMMARY.md: This file
"""
        summary_path.write_text(summary_content)

        return summary_path
