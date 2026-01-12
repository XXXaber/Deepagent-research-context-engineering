"""자율적 연구 에이전트 팩토리 모듈.

이 모듈은 자체 계획, 반성, 컨텍스트 관리 기능을 갖춘
독립적인 연구 DeepAgent를 생성합니다.

## 에이전트 생성 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│                create_researcher_agent()                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   1. 모델 초기화                                                 │
│      model = ChatOpenAI(model="gpt-4.1")                        │
│                                                                  │
│   2. 깊이 설정 로드                                              │
│      config = get_depth_config(depth)                           │
│                                                                  │
│   3. 깊이별 도구 선택                                            │
│      tools = _get_tools_for_depth(depth)                        │
│      ┌─────────────────────────────────────────────────────────┐│
│      │ QUICK:   think, mgrep, tavily                           ││
│      │ STANDARD: + comprehensive_search                         ││
│      │ DEEP:    + arxiv, github                                 ││
│      │ EXHAUSTIVE: + library_docs                               ││
│      └─────────────────────────────────────────────────────────┘│
│                                                                  │
│   4. 프롬프트 구성                                               │
│      - QUICK/STANDARD: AUTONOMOUS_RESEARCHER_INSTRUCTIONS       │
│      - DEEP/EXHAUSTIVE: build_research_prompt() (Ralph Loop)   │
│                                                                  │
│   5. DeepAgent 생성                                              │
│      return create_deep_agent(model, tools, prompt, backend)    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

v2 업데이트 (2026-01):
- ResearchDepth 기반 동적 깊이 조절
- 다중 검색 도구 (mgrep, arXiv, comprehensive_search)
- Ralph Loop 패턴 지원
"""

from __future__ import annotations

from datetime import datetime

from deepagents import create_deep_agent
from deepagents.backends.protocol import BackendFactory, BackendProtocol
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph

from research_agent.researcher.depth import ResearchDepth, get_depth_config
from research_agent.researcher.prompts import (
    AUTONOMOUS_RESEARCHER_INSTRUCTIONS,
    build_research_prompt,
)
from research_agent.tools import (
    arxiv_search,
    comprehensive_search,
    github_code_search,
    library_docs_search,
    mgrep_search,
    tavily_search,
    think_tool,
)


# ============================================================================
# 도구 선택 헬퍼
# ============================================================================


def _get_tools_for_depth(depth: ResearchDepth) -> list:
    """연구 깊이에 따라 사용할 도구 목록을 반환한다.

    깊이 수준에 따라 다른 도구 세트를 제공합니다:
    - 기본: think_tool (항상 포함)
    - web 소스: mgrep_search, tavily_search
    - arxiv 소스: arxiv_search
    - github 소스: github_code_search
    - docs 소스: library_docs_search
    - 다중 소스 (2개 이상): comprehensive_search

    Args:
        depth: 연구 깊이 (ResearchDepth enum).

    Returns:
        해당 깊이에서 사용 가능한 도구 목록.
    """
    # 깊이 설정 로드
    config = get_depth_config(depth)

    # 기본 도구: 항상 think_tool 포함
    tools = [think_tool]

    # 소스별 도구 추가
    if "web" in config.sources:
        tools.extend([mgrep_search, tavily_search])

    if "arxiv" in config.sources:
        tools.append(arxiv_search)

    if "github" in config.sources:
        tools.append(github_code_search)

    if "docs" in config.sources:
        tools.append(library_docs_search)

    # 다중 소스인 경우 통합 검색 도구 추가
    if len(config.sources) > 1:
        tools.append(comprehensive_search)

    return tools


# ============================================================================
# 에이전트 팩토리
# ============================================================================


def create_researcher_agent(
    model: str | BaseChatModel | None = None,
    backend: BackendProtocol | BackendFactory | None = None,
    depth: ResearchDepth | str = ResearchDepth.STANDARD,
) -> CompiledStateGraph:
    """자율적 연구 DeepAgent를 생성한다.

    이 함수는 주어진 깊이 수준에 맞는 연구 에이전트를 생성합니다.
    에이전트는 자체 계획 수립, 다중 소스 검색, 반성(reflection) 기능을 갖춥니다.

    Args:
        model: 사용할 LLM 모델.
            - None: 기본 gpt-4.1 (temperature=0) 사용
            - str: 모델 이름 (예: "gpt-4o")
            - BaseChatModel: 직접 생성한 모델 인스턴스
        backend: 파일 작업용 백엔드.
            - None: 기본 StateBackend 사용
            - FilesystemBackend, CompositeBackend 등 지정 가능
        depth: 연구 깊이 수준.
            - ResearchDepth enum 또는 문자열 ("quick", "standard", "deep", "exhaustive")
            - 기본값: STANDARD

    Returns:
        CompiledStateGraph: 실행 가능한 자율 연구 에이전트.

    Example:
        >>> # 기본 설정으로 생성
        >>> agent = create_researcher_agent()
        >>>
        >>> # 깊이 지정
        >>> agent = create_researcher_agent(depth="deep")
        >>>
        >>> # 커스텀 모델과 백엔드
        >>> from langchain_openai import ChatOpenAI
        >>> from deepagents.backends import FilesystemBackend
        >>> agent = create_researcher_agent(
        ...     model=ChatOpenAI(model="gpt-4o", temperature=0.2),
        ...     backend=FilesystemBackend(root_dir="./research"),
        ...     depth=ResearchDepth.EXHAUSTIVE,
        ... )
    """
    # 모델이 지정되지 않았으면 기본 모델 사용
    if model is None:
        model = ChatOpenAI(model="gpt-4.1", temperature=0.0)

    # 문자열로 전달된 깊이를 enum으로 변환
    if isinstance(depth, str):
        depth = ResearchDepth(depth)

    # 깊이 설정 로드
    config = get_depth_config(depth)

    # 깊이에 맞는 도구 선택
    tools = _get_tools_for_depth(depth)

    # 현재 날짜 (프롬프트에 포함)
    current_date = datetime.now().strftime("%Y-%m-%d")

    # 깊이에 따른 프롬프트 구성
    if depth in (ResearchDepth.DEEP, ResearchDepth.EXHAUSTIVE):
        # DEEP/EXHAUSTIVE: Ralph Loop 프롬프트 사용
        formatted_prompt = build_research_prompt(
            depth=depth,
            query="{query}",  # 런타임에 치환됨
            max_iterations=config.max_ralph_iterations,
        )
    else:
        # QUICK/STANDARD: 기본 자율 연구 프롬프트 사용
        formatted_prompt = AUTONOMOUS_RESEARCHER_INSTRUCTIONS.format(date=current_date)

    # DeepAgent 생성 및 반환
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=formatted_prompt,
        backend=backend,
    )


# ============================================================================
# SubAgent 통합
# ============================================================================


def get_researcher_subagent(
    model: str | BaseChatModel | None = None,
    backend: BackendProtocol | BackendFactory | None = None,
    depth: ResearchDepth | str = ResearchDepth.STANDARD,
) -> dict:
    """오케스트레이터용 CompiledSubAgent로 연구자를 반환한다.

    이 함수는 메인 에이전트에서 서브에이전트로 호출할 수 있는 형태로
    연구 에이전트를 래핑합니다.

    Args:
        model: 사용할 LLM 모델 (create_researcher_agent과 동일).
        backend: 파일 작업용 백엔드.
        depth: 연구 깊이 수준.

    Returns:
        다음 키를 포함하는 딕셔너리:
        - name: 서브에이전트 이름 ("researcher")
        - description: 서브에이전트 설명 (깊이 정보 포함)
        - runnable: 실행 가능한 에이전트 객체

    Example:
        >>> from deepagents import create_deep_agent
        >>> researcher = get_researcher_subagent(depth="deep")
        >>> main_agent = create_deep_agent(
        ...     subagents=[researcher],
        ...     system_prompt="작업을 researcher에게 위임하세요."
        ... )
    """
    # 연구 에이전트 생성
    researcher = create_researcher_agent(model=model, backend=backend, depth=depth)

    # 깊이를 enum으로 변환
    depth_enum = ResearchDepth(depth) if isinstance(depth, str) else depth
    config = get_depth_config(depth_enum)

    # 설명 문자열 구성
    description = (
        f"Autonomous research agent ({depth_enum.value} mode). "
        f"Max {config.max_ralph_iterations} iterations, "
        f"sources: {', '.join(config.sources)}. "
        "Use for comprehensive topic research with self-planning."
    )

    # SubAgent 형식으로 반환
    return {
        "name": "researcher",
        "description": description,
        "runnable": researcher,
    }
