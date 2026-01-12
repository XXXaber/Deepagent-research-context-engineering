from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from research_agent.researcher.depth import ResearchDepth, get_depth_config
from research_agent.researcher.ralph_loop import (
    Finding,
    RalphLoopState,
    ResearchRalphLoop,
    ResearchSession,
    SourceQuality,
    SourceType,
)


class TestRalphLoopState:
    def test_default_values(self):
        state = RalphLoopState()

        assert state.iteration == 1
        assert state.max_iterations == 0
        assert state.completion_promise == "RESEARCH_COMPLETE"
        assert state.findings_count == 0
        assert state.coverage_score == 0.0

    def test_is_max_reached_unlimited(self):
        state = RalphLoopState(max_iterations=0, iteration=100)
        assert state.is_max_reached() is False

    def test_is_max_reached_at_limit(self):
        state = RalphLoopState(max_iterations=5, iteration=5)
        assert state.is_max_reached() is True

    def test_is_max_reached_below_limit(self):
        state = RalphLoopState(max_iterations=5, iteration=3)
        assert state.is_max_reached() is False


class TestFinding:
    def test_creation(self):
        finding = Finding(
            content="Test content",
            source_url="https://example.com",
            source_title="Example",
            confidence=0.9,
        )

        assert finding.content == "Test content"
        assert finding.confidence == 0.9
        assert finding.verified_by == []

    def test_with_verification(self):
        finding = Finding(
            content="Test",
            source_url="https://a.com",
            source_title="A",
            confidence=0.8,
            verified_by=["https://b.com", "https://c.com"],
        )

        assert len(finding.verified_by) == 2

    def test_weighted_confidence_without_quality(self):
        finding = Finding(
            content="Test",
            source_url="https://a.com",
            source_title="A",
            confidence=0.8,
        )
        assert finding.weighted_confidence == 0.8

    def test_weighted_confidence_with_quality(self):
        quality = SourceQuality(
            source_type=SourceType.ARXIV,
            recency_score=0.8,
            authority_score=0.9,
            relevance_score=0.85,
        )
        finding = Finding(
            content="Test",
            source_url="https://arxiv.org/abs/1234",
            source_title="Paper",
            confidence=0.9,
            quality=quality,
        )
        assert finding.weighted_confidence < finding.confidence
        assert finding.weighted_confidence > 0


class TestSourceQuality:
    def test_overall_score_calculation(self):
        quality = SourceQuality(
            source_type=SourceType.ARXIV,
            recency_score=0.8,
            authority_score=0.9,
            relevance_score=0.85,
        )
        expected = 0.8 * 0.2 + 0.9 * 0.4 + 0.85 * 0.4
        assert abs(quality.overall_score - expected) < 0.01

    def test_verification_bonus(self):
        quality_no_verify = SourceQuality(
            source_type=SourceType.WEB,
            recency_score=0.5,
            authority_score=0.5,
            relevance_score=0.5,
        )
        quality_verified = SourceQuality(
            source_type=SourceType.WEB,
            recency_score=0.5,
            authority_score=0.5,
            relevance_score=0.5,
            verification_count=3,
        )
        assert quality_verified.overall_score > quality_no_verify.overall_score

    def test_from_source_type_arxiv(self):
        quality = SourceQuality.from_source_type(SourceType.ARXIV)
        assert quality.authority_score == 0.9

    def test_from_source_type_web(self):
        quality = SourceQuality.from_source_type(SourceType.WEB)
        assert quality.authority_score == 0.5

    def test_max_score_capped(self):
        quality = SourceQuality(
            source_type=SourceType.ARXIV,
            recency_score=1.0,
            authority_score=1.0,
            relevance_score=1.0,
            verification_count=10,
        )
        assert quality.overall_score <= 1.0


class TestResearchRalphLoop:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as td:
            original_file = ResearchRalphLoop.STATE_FILE
            ResearchRalphLoop.STATE_FILE = Path(td) / ".claude" / "test-state.md"
            yield Path(td)
            ResearchRalphLoop.STATE_FILE = original_file

    def test_init_default(self, temp_dir: Path):
        loop = ResearchRalphLoop("test query")

        assert loop.query == "test query"
        assert loop.max_iterations == 10
        assert loop.coverage_threshold == 0.85

    def test_init_with_depth_config(self, temp_dir: Path):
        config = get_depth_config(ResearchDepth.EXHAUSTIVE)
        loop = ResearchRalphLoop("test query", depth_config=config)

        assert loop.max_iterations == 10
        assert loop.coverage_threshold == 0.95
        assert "docs" in loop.sources

    def test_create_research_prompt(self, temp_dir: Path):
        loop = ResearchRalphLoop("test query", max_iterations=5)
        prompt = loop.create_research_prompt()

        assert "test query" in prompt
        assert "1/5" in prompt
        assert "RESEARCH_COMPLETE" in prompt

    def test_save_and_load_state(self, temp_dir: Path):
        loop = ResearchRalphLoop("test query")
        loop.state.iteration = 3
        loop.state.findings_count = 5
        loop.state.coverage_score = 0.6
        loop.save_state()

        assert loop.STATE_FILE.exists()

        loop2 = ResearchRalphLoop("test query")
        loaded = loop2.load_state()

        assert loaded is True
        assert loop2.state.iteration == 3
        assert loop2.state.findings_count == 5
        assert loop2.state.coverage_score == 0.6

    def test_increment_iteration(self, temp_dir: Path):
        loop = ResearchRalphLoop("test query")
        loop.save_state()

        assert loop.state.iteration == 1
        loop.increment_iteration()
        assert loop.state.iteration == 2

    def test_is_complete_by_coverage(self, temp_dir: Path):
        loop = ResearchRalphLoop("test query", coverage_threshold=0.8)
        loop.state.coverage_score = 0.85

        assert loop.is_complete() is True

    def test_is_complete_by_max_iterations(self, temp_dir: Path):
        loop = ResearchRalphLoop("test query", max_iterations=5)
        loop.state.iteration = 5
        loop.state.coverage_score = 0.5

        assert loop.is_complete() is True

    def test_cleanup(self, temp_dir: Path):
        loop = ResearchRalphLoop("test query")
        loop.save_state()
        assert loop.STATE_FILE.exists()

        loop.cleanup()
        assert not loop.STATE_FILE.exists()


class TestResearchSession:
    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            original_workspace = ResearchSession.WORKSPACE
            original_state_file = ResearchRalphLoop.STATE_FILE

            ResearchSession.WORKSPACE = Path(td) / "research_workspace"
            ResearchRalphLoop.STATE_FILE = Path(td) / ".claude" / "test-state.md"

            yield Path(td)

            ResearchSession.WORKSPACE = original_workspace
            ResearchRalphLoop.STATE_FILE = original_state_file

    def test_init(self, temp_workspace: Path):
        session = ResearchSession("test query")

        assert session.query == "test query"
        assert session.session_id is not None
        assert session.findings == []

    def test_initialize_creates_files(self, temp_workspace: Path):
        session = ResearchSession("test query", session_id="test123")
        session.initialize()

        assert session.session_dir.exists()
        assert (session.session_dir / "TODO.md").exists()
        assert (session.session_dir / "FINDINGS.md").exists()

    def test_add_finding(self, temp_workspace: Path):
        session = ResearchSession("test query", session_id="test123")
        session.initialize()

        finding = Finding(
            content="Test finding",
            source_url="https://example.com",
            source_title="Example",
            confidence=0.9,
        )
        session.add_finding(finding)

        assert len(session.findings) == 1
        assert session.ralph_loop.state.findings_count == 1
        assert session.ralph_loop.state.coverage_score > 0

    def test_coverage_calculation(self, temp_workspace: Path):
        session = ResearchSession("test query", session_id="test123")
        session.initialize()

        source_types = [
            SourceType.WEB,
            SourceType.ARXIV,
            SourceType.GITHUB,
            SourceType.DOCS,
        ]
        for i in range(10):
            quality = SourceQuality.from_source_type(
                source_types[i % len(source_types)],
                relevance_score=0.9,
                recency_score=0.9,
            )
            finding = Finding(
                content=f"Finding {i}",
                source_url=f"https://example{i}.com",
                source_title=f"Source {i}",
                confidence=0.9,
                quality=quality,
            )
            session.add_finding(finding)

        assert session.ralph_loop.state.coverage_score > 0.7
        assert session.ralph_loop.state.coverage_score <= 1.0

    def test_complete_iteration(self, temp_workspace: Path):
        session = ResearchSession("test query", session_id="test123")
        session.initialize()

        done = session.complete_iteration()
        assert done is False
        assert session.ralph_loop.state.iteration == 2

    def test_finalize(self, temp_workspace: Path):
        session = ResearchSession("test query", session_id="test123")
        session.initialize()

        summary_path = session.finalize()

        assert summary_path.exists()
        assert "SUMMARY.md" in str(summary_path)
        assert not session.ralph_loop.STATE_FILE.exists()
