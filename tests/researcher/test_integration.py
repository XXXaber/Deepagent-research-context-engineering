"""E2E 통합 테스트 - ResearchRunner 전체 플로우 검증."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_agent.researcher.depth import ResearchDepth
from research_agent.researcher.ralph_loop import Finding, ResearchSession
from research_agent.researcher.runner import ResearchRunner


class TestE2EResearchFlow:
    """전체 연구 플로우 E2E 테스트."""

    @pytest.fixture
    def temp_workspace(self):
        """임시 워크스페이스 생성."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_agent_response_incomplete(self):
        """완료되지 않은 에이전트 응답."""
        return {
            "messages": [
                MagicMock(
                    content="I found some information about the topic. "
                    "Still need to investigate more aspects."
                )
            ]
        }

    @pytest.fixture
    def mock_agent_response_complete(self):
        """완료된 에이전트 응답."""
        return {
            "messages": [
                MagicMock(
                    content="Research is comprehensive. "
                    "<promise>RESEARCH_COMPLETE</promise>"
                )
            ]
        }

    def test_runner_initialization_creates_session(self, temp_workspace):
        """Runner 초기화 시 세션이 생성되는지 확인."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            runner = ResearchRunner("Test query", depth="quick")

            assert runner.session is not None
            assert runner.query == "Test query"
            assert runner.depth == ResearchDepth.QUICK

    def test_session_initialization_creates_files(self, temp_workspace):
        """세션 초기화 시 필요한 파일들이 생성되는지 확인."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            runner = ResearchRunner("Test query", depth="quick")
            runner.session.initialize()

            assert runner.session.session_dir.exists()
            assert (runner.session.session_dir / "TODO.md").exists()
            assert (runner.session.session_dir / "FINDINGS.md").exists()

            todo_content = (runner.session.session_dir / "TODO.md").read_text()
            assert "Test query" in todo_content

    def test_iteration_prompt_contains_query(self, temp_workspace):
        """반복 프롬프트에 쿼리가 포함되는지 확인."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            runner = ResearchRunner("Context Engineering 분석", depth="deep")
            prompt = runner._build_iteration_prompt(1)

            assert "Context Engineering 분석" in prompt
            assert "Iteration 1/5" in prompt
            assert "RESEARCH_COMPLETE" in prompt

    def test_completion_detection_by_promise(self, temp_workspace):
        """promise 태그로 완료 감지."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            runner = ResearchRunner("Test", depth="quick")
            result = {
                "messages": [
                    MagicMock(content="Done <promise>RESEARCH_COMPLETE</promise>")
                ]
            }

            assert runner._check_completion(result) is True

    def test_completion_detection_by_coverage(self, temp_workspace):
        """coverage 기반 완료 감지."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            runner = ResearchRunner("Test", depth="quick")
            runner.session.ralph_loop.state.coverage_score = 0.95

            result = {"messages": [MagicMock(content="Still working...")]}
            assert runner._check_completion(result) is True

    def test_no_completion_when_incomplete(self, temp_workspace):
        """완료 조건 미충족 시 False 반환."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            runner = ResearchRunner("Test", depth="deep")
            runner.session.ralph_loop.state.coverage_score = 0.3
            runner.session.ralph_loop.state.iteration = 1

            result = {"messages": [MagicMock(content="Working on it...")]}
            assert runner._check_completion(result) is False


class TestE2EWithMockedAgent:
    """Mock 에이전트를 사용한 E2E 테스트."""

    @pytest.fixture
    def temp_workspace(self):
        """임시 워크스페이스 생성."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_single_iteration_completion(self, temp_workspace):
        """단일 반복으로 완료되는 케이스."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            runner = ResearchRunner("Quick test", depth="quick")

            mock_agent = AsyncMock()
            mock_agent.ainvoke.return_value = {
                "messages": [MagicMock(content="<promise>RESEARCH_COMPLETE</promise>")]
            }
            runner.agent = mock_agent

            async def run_test():
                runner.session.initialize()

                result = await runner._execute_iteration(1)
                is_complete = runner._check_completion(result)

                return is_complete

            is_complete = asyncio.get_event_loop().run_until_complete(run_test())
            assert is_complete is True

    def test_multiple_iterations_until_completion(self, temp_workspace):
        """여러 반복 후 완료되는 케이스."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            runner = ResearchRunner("Deep test", depth="deep")

            call_count = 0

            async def mock_invoke(*args, **kwargs):
                nonlocal call_count
                call_count += 1

                if call_count >= 3:
                    return {
                        "messages": [
                            MagicMock(content="<promise>RESEARCH_COMPLETE</promise>")
                        ]
                    }
                return {"messages": [MagicMock(content="Still researching...")]}

            mock_agent = AsyncMock()
            mock_agent.ainvoke = mock_invoke
            runner.agent = mock_agent

            async def run_test():
                runner.session.initialize()

                iteration = 1
                max_iter = 5

                while iteration <= max_iter:
                    result = await runner._execute_iteration(iteration)
                    if runner._check_completion(result):
                        break
                    iteration += 1

                return iteration

            final_iteration = asyncio.get_event_loop().run_until_complete(run_test())
            assert final_iteration == 3
            assert call_count == 3


class TestFilesystemStateChanges:
    """파일시스템 상태 변화 검증."""

    @pytest.fixture
    def temp_workspace(self):
        """임시 워크스페이스 생성."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_findings_file_updated_on_add(self, temp_workspace):
        """Finding 추가 시 파일이 업데이트되는지 확인."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            session = ResearchSession("Test query")
            session.initialize()

            finding = Finding(
                content="Important discovery about LLMs",
                source_url="https://example.com/article",
                source_title="LLM Research Paper",
                confidence=0.9,
            )
            session.add_finding(finding)

            findings_content = (session.session_dir / "FINDINGS.md").read_text()
            assert "Important discovery about LLMs" in findings_content
            assert "https://example.com/article" in findings_content
            assert "LLM Research Paper" in findings_content

    def test_coverage_updates_with_findings(self, temp_workspace):
        """Finding 추가 시 coverage가 업데이트되는지 확인."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            session = ResearchSession("Test query")
            session.initialize()

            initial_coverage = session.ralph_loop.state.coverage_score
            assert initial_coverage == 0.0

            for i in range(5):
                finding = Finding(
                    content=f"Finding {i}",
                    source_url=f"https://example.com/{i}",
                    source_title=f"Source {i}",
                    confidence=0.8,
                )
                session.add_finding(finding)

            assert session.ralph_loop.state.coverage_score > initial_coverage
            assert session.ralph_loop.state.findings_count == 5

    def test_summary_created_on_finalize(self, temp_workspace):
        """finalize 시 SUMMARY.md가 생성되는지 확인."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            session = ResearchSession("Test query")
            session.initialize()

            finding = Finding(
                content="Test finding",
                source_url="https://example.com",
                source_title="Test Source",
                confidence=0.9,
            )
            session.add_finding(finding)

            summary_path = session.finalize()

            assert summary_path.exists()
            summary_content = summary_path.read_text()
            assert "Test query" in summary_content
            assert "Total Findings: 1" in summary_content


class TestCompletionConditions:
    """완료 조건 동작 확인."""

    @pytest.fixture
    def temp_workspace(self):
        """임시 워크스페이스 생성."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_max_iterations_limit(self, temp_workspace):
        """최대 반복 횟수 제한 동작 확인."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            runner = ResearchRunner("Test", depth="quick")

            assert runner.config.max_ralph_iterations == 1

            runner.session.ralph_loop.state.iteration = 1
            assert runner.session.ralph_loop.is_complete() is True

    def test_coverage_threshold_completion(self, temp_workspace):
        """coverage threshold 도달 시 완료."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            runner = ResearchRunner("Test", depth="deep")

            runner.session.ralph_loop.state.coverage_score = 0.84
            assert runner.session.ralph_loop.is_complete() is False

            runner.session.ralph_loop.state.coverage_score = 0.85
            assert runner.session.ralph_loop.is_complete() is True

    def test_iteration_increment(self, temp_workspace):
        """반복 증가 동작 확인."""
        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            session = ResearchSession("Test query")
            session.initialize()

            initial_iteration = session.ralph_loop.state.iteration
            assert initial_iteration == 1

            session.complete_iteration()
            assert session.ralph_loop.state.iteration == 2

    def test_state_file_persistence(self, temp_workspace):
        """상태 파일 영속성 확인."""
        state_file = temp_workspace / ".claude" / "research-ralph-loop.local.md"

        with patch.object(ResearchSession, "WORKSPACE", temp_workspace):
            with patch(
                "research_agent.researcher.ralph_loop.ResearchRalphLoop.STATE_FILE",
                state_file,
            ):
                session = ResearchSession("Test query")
                session.initialize()

                assert state_file.exists()

                state_content = state_file.read_text()
                assert "active: true" in state_content
                assert "iteration: 1" in state_content
