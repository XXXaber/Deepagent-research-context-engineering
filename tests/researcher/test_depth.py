from __future__ import annotations

import pytest

from research_agent.researcher.depth import (
    DEPTH_CONFIGS,
    DepthConfig,
    ResearchDepth,
    get_depth_config,
    infer_research_depth,
)


class TestResearchDepth:
    def test_enum_values(self):
        assert ResearchDepth.QUICK.value == "quick"
        assert ResearchDepth.STANDARD.value == "standard"
        assert ResearchDepth.DEEP.value == "deep"
        assert ResearchDepth.EXHAUSTIVE.value == "exhaustive"

    def test_all_depths_have_configs(self):
        for depth in ResearchDepth:
            assert depth in DEPTH_CONFIGS


class TestDepthConfig:
    def test_quick_config(self):
        config = DEPTH_CONFIGS[ResearchDepth.QUICK]

        assert config.max_searches == 3
        assert config.max_ralph_iterations == 1
        assert config.sources == ("web",)
        assert config.require_cross_validation is False
        assert config.min_sources_for_claim == 1
        assert config.coverage_threshold == 0.5

    def test_standard_config(self):
        config = DEPTH_CONFIGS[ResearchDepth.STANDARD]

        assert config.max_searches == 10
        assert config.max_ralph_iterations == 2
        assert "web" in config.sources
        assert "local" in config.sources

    def test_deep_config(self):
        config = DEPTH_CONFIGS[ResearchDepth.DEEP]

        assert config.max_searches == 25
        assert config.max_ralph_iterations == 5
        assert config.require_cross_validation is True
        assert config.min_sources_for_claim == 2
        assert "arxiv" in config.sources
        assert "github" in config.sources

    def test_exhaustive_config(self):
        config = DEPTH_CONFIGS[ResearchDepth.EXHAUSTIVE]

        assert config.max_searches == 50
        assert config.max_ralph_iterations == 10
        assert config.coverage_threshold == 0.95
        assert config.min_sources_for_claim == 3
        assert "docs" in config.sources

    def test_config_is_hashable(self):
        config = DEPTH_CONFIGS[ResearchDepth.QUICK]
        assert hash(config) is not None


class TestGetDepthConfig:
    def test_returns_correct_config(self):
        config = get_depth_config(ResearchDepth.DEEP)
        assert config == DEPTH_CONFIGS[ResearchDepth.DEEP]

    def test_all_depths(self):
        for depth in ResearchDepth:
            config = get_depth_config(depth)
            assert isinstance(config, DepthConfig)


class TestInferResearchDepth:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("quick summary of AI", ResearchDepth.QUICK),
            ("brief overview of LLMs", ResearchDepth.QUICK),
            ("what is context engineering?", ResearchDepth.QUICK),
            ("simple explanation of transformers", ResearchDepth.QUICK),
        ],
    )
    def test_quick_keywords(self, query: str, expected: ResearchDepth):
        assert infer_research_depth(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("analyze the performance of GPT-5", ResearchDepth.DEEP),
            ("compare different RAG strategies", ResearchDepth.DEEP),
            ("investigate agent architectures", ResearchDepth.DEEP),
            ("deep dive into context windows", ResearchDepth.DEEP),
        ],
    )
    def test_deep_keywords(self, query: str, expected: ResearchDepth):
        assert infer_research_depth(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("comprehensive study of AI safety", ResearchDepth.EXHAUSTIVE),
            ("thorough analysis of LLM training", ResearchDepth.EXHAUSTIVE),
            ("academic review of attention mechanisms", ResearchDepth.EXHAUSTIVE),
            ("literature review on context engineering", ResearchDepth.EXHAUSTIVE),
        ],
    )
    def test_exhaustive_keywords(self, query: str, expected: ResearchDepth):
        assert infer_research_depth(query) == expected

    def test_default_to_standard(self):
        assert infer_research_depth("how do agents work?") == ResearchDepth.STANDARD
        assert (
            infer_research_depth("explain RAG architecture") == ResearchDepth.STANDARD
        )

    def test_case_insensitive(self):
        assert infer_research_depth("COMPREHENSIVE study") == ResearchDepth.EXHAUSTIVE
        assert infer_research_depth("Quick Overview") == ResearchDepth.QUICK
