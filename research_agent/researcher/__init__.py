"""자율적 연구 SubAgent 모듈.

이 모듈은 "넓게 탐색 → 깊게 파기" 방법론을 따르는
자체 계획 및 자체 반성 연구 에이전트를 제공한다.

사용법:
    from research_agent.researcher import get_researcher_subagent

    researcher = get_researcher_subagent(model=model, backend=backend)
    # create_deep_agent(subagents=[...])에 사용할 CompiledSubAgent 반환
"""

from research_agent.researcher.agent import (
    create_researcher_agent,
    get_researcher_subagent,
)
from research_agent.researcher.depth import (
    DEPTH_CONFIGS,
    DepthConfig,
    ResearchDepth,
    get_depth_config,
    infer_research_depth,
)
from research_agent.researcher.prompts import (
    AUTONOMOUS_RESEARCHER_INSTRUCTIONS,
    DEPTH_PROMPTS,
    build_research_prompt,
    get_depth_prompt,
)
from research_agent.researcher.ralph_loop import (
    Finding,
    RalphLoopState,
    ResearchRalphLoop,
    ResearchSession,
    SourceQuality,
    SourceType,
)
from research_agent.researcher.runner import (
    ResearchRunner,
    run_deep_research,
)

__all__ = [
    "create_researcher_agent",
    "get_researcher_subagent",
    "AUTONOMOUS_RESEARCHER_INSTRUCTIONS",
    "DEPTH_PROMPTS",
    "get_depth_prompt",
    "build_research_prompt",
    "ResearchDepth",
    "DepthConfig",
    "DEPTH_CONFIGS",
    "infer_research_depth",
    "get_depth_config",
    "ResearchRalphLoop",
    "ResearchSession",
    "RalphLoopState",
    "Finding",
    "SourceQuality",
    "SourceType",
    "ResearchRunner",
    "run_deep_research",
]
