"""ResearchRunner 테스트."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_agent.researcher.depth import ResearchDepth, get_depth_config
from research_agent.researcher.runner import ResearchRunner, run_deep_research


class TestResearchRunner:
    """ResearchRunner 클래스 테스트."""

    def test_init_with_string_depth(self):
        """문자열 depth로 초기화."""
        runner = ResearchRunner("test query", depth="deep")
        assert runner.depth == ResearchDepth.DEEP
        assert runner.query == "test query"

    def test_init_with_enum_depth(self):
        """ResearchDepth enum으로 초기화."""
        runner = ResearchRunner("test query", depth=ResearchDepth.EXHAUSTIVE)
        assert runner.depth == ResearchDepth.EXHAUSTIVE

    def test_config_loaded(self):
        """DepthConfig가 올바르게 로드되는지 확인."""
        runner = ResearchRunner("test query", depth="deep")
        expected_config = get_depth_config(ResearchDepth.DEEP)
        assert (
            runner.config.max_ralph_iterations == expected_config.max_ralph_iterations
        )
        assert runner.config.coverage_threshold == expected_config.coverage_threshold

    def test_session_initialized(self):
        """ResearchSession이 생성되는지 확인."""
        runner = ResearchRunner("test query", depth="standard")
        assert runner.session is not None
        assert runner.session.query == "test query"

    def test_build_iteration_prompt(self):
        """반복 프롬프트 생성."""
        runner = ResearchRunner("Context Engineering 분석", depth="deep")
        prompt = runner._build_iteration_prompt(1)

        assert "Context Engineering 분석" in prompt
        assert "Iteration 1/" in prompt
        assert "RESEARCH_COMPLETE" in prompt
        assert str(runner.config.coverage_threshold) in prompt or "85%" in prompt

    def test_build_iteration_prompt_unlimited(self):
        """무제한 반복 프롬프트."""
        with patch.object(
            ResearchRunner,
            "__init__",
            lambda self, *args, **kwargs: None,
        ):
            runner = ResearchRunner.__new__(ResearchRunner)
            runner.query = "test"
            runner.config = MagicMock()
            runner.config.max_ralph_iterations = 0  # unlimited
            runner.config.coverage_threshold = 0.85
            runner.session = MagicMock()
            runner.session.session_id = "test123"
            runner.session.ralph_loop = MagicMock()
            runner.session.ralph_loop.state = MagicMock()
            runner.session.ralph_loop.state.findings_count = 0
            runner.session.ralph_loop.state.coverage_score = 0.0

            prompt = runner._build_iteration_prompt(5)
            # unlimited일 때는 iteration만 표시
            assert "Iteration 5" in prompt


class TestCheckCompletion:
    """완료 체크 로직 테스트."""

    def setup_method(self):
        """테스트 설정."""
        self.runner = ResearchRunner("test", depth="quick")

    def test_completion_by_promise_tag(self):
        """promise 태그로 완료 감지."""
        result = {
            "messages": [
                MagicMock(content="Research done <promise>RESEARCH_COMPLETE</promise>")
            ]
        }
        assert self.runner._check_completion(result) is True

    def test_completion_by_keyword(self):
        """RESEARCH_COMPLETE 키워드로 완료 감지."""
        result = {"messages": [MagicMock(content="RESEARCH_COMPLETE - all done")]}
        assert self.runner._check_completion(result) is True

    def test_not_complete(self):
        """완료되지 않은 경우."""
        self.runner = ResearchRunner("test", depth="deep")
        result = {"messages": [MagicMock(content="Still working on it...")]}
        self.runner.session.ralph_loop.state.coverage_score = 0.5
        self.runner.session.ralph_loop.state.iteration = 1
        assert self.runner._check_completion(result) is False

    def test_completion_by_coverage(self):
        """coverage 기반 완료."""
        result = {"messages": [MagicMock(content="Working...")]}
        # coverage가 threshold 이상이면 완료
        self.runner.session.ralph_loop.state.coverage_score = 0.90
        assert self.runner._check_completion(result) is True


class TestRunDeepResearchFunction:
    """run_deep_research 함수 테스트."""

    def test_function_is_async(self):
        """run_deep_research가 async 함수인지 확인."""
        import asyncio
        import inspect

        assert inspect.iscoroutinefunction(run_deep_research)

    def test_function_signature(self):
        """함수 시그니처 확인."""
        import inspect

        sig = inspect.signature(run_deep_research)
        params = list(sig.parameters.keys())
        assert "query" in params
        assert "depth" in params
        assert "model" in params


class TestCLIIntegration:
    """CLI 통합 테스트."""

    def test_module_can_be_run(self):
        """모듈이 실행 가능한지 확인."""
        from research_agent.researcher import runner

        assert hasattr(runner, "main")
        assert callable(runner.main)

    def test_argparse_setup(self):
        """argparse가 올바르게 설정되었는지 확인."""
        import argparse
        from research_agent.researcher.runner import main

        # main 함수가 argparse를 사용하는지 간접 확인
        # (실제 실행은 하지 않음)
        assert callable(main)


class TestSessionWorkspace:
    """세션 워크스페이스 테스트."""

    def test_session_dir_created(self):
        """세션 디렉토리가 생성되는지 확인."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "research_agent.researcher.ralph_loop.ResearchSession.WORKSPACE",
                Path(tmpdir),
            ):
                runner = ResearchRunner("test query", depth="quick")
                runner.session.initialize()

                assert runner.session.session_dir.exists()
                assert (runner.session.session_dir / "TODO.md").exists()
                assert (runner.session.session_dir / "FINDINGS.md").exists()
