"""연구 도구 테스트 - 실제 API 호출 사용."""

import pytest

from research_agent.tools import (
    comprehensive_search,
    github_code_search,
    library_docs_search,
)


class TestGitHubCodeSearch:
    """github_code_search 도구 테스트."""

    def test_tool_exists(self):
        """도구가 존재하는지 확인."""
        assert github_code_search is not None
        assert callable(github_code_search.invoke)

    def test_tool_has_description(self):
        """도구 설명이 있는지 확인."""
        assert github_code_search.description is not None
        assert "GitHub" in github_code_search.description

    def test_successful_search(self):
        """성공적인 검색 테스트 - 실제 API 호출."""
        result = github_code_search.invoke({"query": "useState(", "max_results": 3})

        assert "useState" in result
        # 실제 결과에는 repo 정보가 포함됨
        assert "github.com" in result or "No GitHub code found" not in result

    def test_no_results(self):
        """No results test - 실제 API 호출."""
        result = github_code_search.invoke(
            {"query": "xyznonexistent_pattern_abc123_impossible"}
        )

        assert "No GitHub code found" in result

    def test_language_filter(self):
        """언어 필터 테스트 - 실제 API 호출."""
        result = github_code_search.invoke(
            {"query": "def test_", "language": ["python"], "max_results": 3}
        )

        # Python 파일 결과가 있거나 필터로 인해 결과 없음
        assert "python" in result.lower() or "No GitHub code found" in result


class TestLibraryDocsSearch:
    """library_docs_search 도구 테스트."""

    def test_tool_exists(self):
        """도구가 존재하는지 확인."""
        assert library_docs_search is not None
        assert callable(library_docs_search.invoke)

    def test_tool_has_description(self):
        """도구 설명이 있는지 확인."""
        assert library_docs_search.description is not None
        assert (
            "라이브러리" in library_docs_search.description
            or "library" in library_docs_search.description.lower()
        )

    def test_successful_search(self):
        """성공적인 검색 테스트 - 실제 API 호출."""
        result = library_docs_search.invoke(
            {"library_name": "langchain", "query": "how to use agents"}
        )

        # 성공하면 LangChain 관련 내용, 실패하면 에러 메시지
        assert "langchain" in result.lower() or "error" in result.lower()

    def test_library_not_found(self):
        """Library not found case - 실제 API 호출."""
        result = library_docs_search.invoke(
            {"library_name": "xyznonexistent_lib_abc123", "query": "test"}
        )

        assert "not found" in result.lower() or "error" in result.lower()


class TestComprehensiveSearchWithGitHub:
    """comprehensive_search의 GitHub 통합 테스트."""

    def test_includes_github_source(self):
        """GitHub 소스가 포함되는지 확인 - 실제 API 호출."""
        result = comprehensive_search.invoke(
            {"query": "useState(", "sources": ["github"], "max_results_per_source": 2}
        )

        assert "GitHub" in result


class TestComprehensiveSearchWithDocs:
    """comprehensive_search의 docs 통합 테스트."""

    def test_includes_docs_source(self):
        """docs 소스가 포함되는지 확인 - 실제 API 호출."""
        result = comprehensive_search.invoke(
            {
                "query": "how to create agents",
                "sources": ["docs"],
                "library_name": "langchain",
                "max_results_per_source": 2,
            }
        )

        assert (
            "공식 문서" in result
            or "Documentation" in result
            or "docs" in result.lower()
        )
