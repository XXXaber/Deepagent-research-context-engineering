"""연구 깊이 설정 모듈.

이 모듈은 연구 에이전트의 깊이(depth) 수준을 정의하고 관리합니다.
각 깊이 수준은 검색 횟수, 반복 횟수, 사용 가능한 소스 등을 결정합니다.

## 깊이 수준 비교

```
┌──────────────┬─────────┬───────────┬────────────────────────────────┐
│   깊이       │ 검색 수 │ 반복 횟수 │             소스                │
├──────────────┼─────────┼───────────┼────────────────────────────────┤
│ QUICK        │    3    │     1     │ web                            │
│ STANDARD     │   10    │     2     │ web, local                     │
│ DEEP         │   25    │     5     │ web, local, github, arxiv      │
│ EXHAUSTIVE   │   50    │    10     │ web, local, github, arxiv, docs│
└──────────────┴─────────┴───────────┴────────────────────────────────┘
```

v2 업데이트 (2026-01):
- ResearchDepth enum 도입
- DepthConfig dataclass로 구성 관리
- 쿼리 기반 깊이 추론 (infer_research_depth)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ResearchDepth(Enum):
    """연구 깊이 수준을 나타내는 열거형.

    각 깊이 수준은 다른 검색 전략과 리소스 사용량을 의미합니다:

    - QUICK: 빠른 답변이 필요할 때. 최소 검색, 단일 반복.
    - STANDARD: 균형 잡힌 조사. 웹 + 로컬 소스 사용.
    - DEEP: 심층 분석. 교차 검증 필요, GitHub/arXiv 포함.
    - EXHAUSTIVE: 학술적 완성도. 공식 문서까지 포함, 최대 검증.
    """

    QUICK = "quick"  # 빠른 조사 (최대 3회 검색)
    STANDARD = "standard"  # 표준 조사 (최대 10회 검색)
    DEEP = "deep"  # 심층 조사 (최대 25회 검색, Ralph Loop)
    EXHAUSTIVE = "exhaustive"  # 철저한 조사 (최대 50회 검색, 확장 Ralph Loop)


@dataclass(frozen=True)
class DepthConfig:
    """연구 깊이별 설정을 담는 불변 데이터 클래스.

    Attributes:
        max_searches: 허용된 최대 검색 횟수.
        max_ralph_iterations: Ralph Loop 최대 반복 횟수.
        sources: 사용 가능한 검색 소스 튜플 (예: ("web", "arxiv")).
        require_cross_validation: 교차 검증 필수 여부.
        min_sources_for_claim: 주장당 필요한 최소 소스 수.
        coverage_threshold: 완료 판정 기준 커버리지 점수 (0.0 ~ 1.0).
    """

    max_searches: int  # 최대 검색 횟수
    max_ralph_iterations: int  # Ralph Loop 최대 반복
    sources: tuple[str, ...]  # 사용 가능한 소스
    require_cross_validation: bool  # 교차 검증 필요 여부
    min_sources_for_claim: int  # 주장당 최소 소스 수
    coverage_threshold: float  # 커버리지 임계값


# ============================================================================
# 깊이별 기본 설정
# ============================================================================

DEPTH_CONFIGS: dict[ResearchDepth, DepthConfig] = {
    # QUICK: 빠른 답변용
    # - 최대 3회 검색
    # - 단일 반복 (Ralph Loop 없음)
    # - 웹 소스만 사용
    # - 교차 검증 없음
    ResearchDepth.QUICK: DepthConfig(
        max_searches=3,
        max_ralph_iterations=1,
        sources=("web",),
        require_cross_validation=False,
        min_sources_for_claim=1,
        coverage_threshold=0.5,
    ),
    # STANDARD: 균형 잡힌 조사
    # - 최대 10회 검색
    # - 2회 반복
    # - 웹 + 로컬 소스
    # - 교차 검증 없음
    ResearchDepth.STANDARD: DepthConfig(
        max_searches=10,
        max_ralph_iterations=2,
        sources=("web", "local"),
        require_cross_validation=False,
        min_sources_for_claim=1,
        coverage_threshold=0.7,
    ),
    # DEEP: 심층 분석 (Ralph Loop 활성화)
    # - 최대 25회 검색
    # - 5회 반복
    # - 웹 + 로컬 + GitHub + arXiv
    # - 교차 검증 필수 (주장당 최소 2개 소스)
    ResearchDepth.DEEP: DepthConfig(
        max_searches=25,
        max_ralph_iterations=5,
        sources=("web", "local", "github", "arxiv"),
        require_cross_validation=True,
        min_sources_for_claim=2,
        coverage_threshold=0.85,
    ),
    # EXHAUSTIVE: 학술적 완성도 (확장 Ralph Loop)
    # - 최대 50회 검색
    # - 10회 반복
    # - 모든 소스 사용 (docs 포함)
    # - 교차 검증 필수 (주장당 최소 3개 소스)
    ResearchDepth.EXHAUSTIVE: DepthConfig(
        max_searches=50,
        max_ralph_iterations=10,
        sources=("web", "local", "github", "arxiv", "docs"),
        require_cross_validation=True,
        min_sources_for_claim=3,
        coverage_threshold=0.95,
    ),
}


# ============================================================================
# 깊이 추론용 키워드 세트
# ============================================================================

# EXHAUSTIVE 트리거 키워드
_EXHAUSTIVE_KEYWORDS = frozenset(
    ["comprehensive", "thorough", "academic", "literature review", "exhaustive"]
)

# DEEP 트리거 키워드
_DEEP_KEYWORDS = frozenset(
    ["analyze", "compare", "investigate", "deep dive", "in-depth"]
)

# QUICK 트리거 키워드
_QUICK_KEYWORDS = frozenset(["quick", "brief", "summary", "what is", "simple"])


# ============================================================================
# 유틸리티 함수
# ============================================================================


def infer_research_depth(query: str) -> ResearchDepth:
    """쿼리 문자열에서 적절한 연구 깊이를 추론한다.

    쿼리에 포함된 키워드를 기반으로 연구 깊이를 결정합니다.
    키워드 매칭 우선순위: EXHAUSTIVE > DEEP > QUICK > STANDARD(기본값).

    Args:
        query: 사용자의 연구 쿼리 문자열.

    Returns:
        추론된 ResearchDepth 열거형 값.
        매칭되는 키워드가 없으면 STANDARD 반환.

    Example:
        >>> infer_research_depth("quick summary of AI trends")
        ResearchDepth.QUICK
        >>> infer_research_depth("analyze different RAG strategies")
        ResearchDepth.DEEP
        >>> infer_research_depth("comprehensive literature review on transformers")
        ResearchDepth.EXHAUSTIVE
    """
    query_lower = query.lower()

    # 키워드 우선순위대로 검사
    if any(kw in query_lower for kw in _EXHAUSTIVE_KEYWORDS):
        return ResearchDepth.EXHAUSTIVE
    if any(kw in query_lower for kw in _DEEP_KEYWORDS):
        return ResearchDepth.DEEP
    if any(kw in query_lower for kw in _QUICK_KEYWORDS):
        return ResearchDepth.QUICK

    # 기본값: STANDARD
    return ResearchDepth.STANDARD


def get_depth_config(depth: ResearchDepth) -> DepthConfig:
    """연구 깊이에 해당하는 설정을 반환한다.

    Args:
        depth: ResearchDepth 열거형 값.

    Returns:
        해당 깊이의 DepthConfig 객체.

    Example:
        >>> config = get_depth_config(ResearchDepth.DEEP)
        >>> config.max_searches
        25
        >>> config.sources
        ('web', 'local', 'github', 'arxiv')
    """
    return DEPTH_CONFIGS[depth]
