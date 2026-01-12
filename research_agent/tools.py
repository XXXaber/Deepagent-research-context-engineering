"""연구 도구 모듈.

이 모듈은 연구 에이전트를 위한 검색 및 콘텐츠 처리 유틸리티를 제공합니다.
다중 소스 검색(Tavily, mgrep, arXiv, grep.app, Context7)을 지원합니다.

## 도구 흐름도

```
┌─────────────────────────────────────────────────────────────────┐
│                    comprehensive_search                          │
│  (다중 소스 오케스트레이션)                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  web     │  │  local   │  │  arxiv   │  │     github       │ │
│  │          │  │          │  │          │  │                  │ │
│  │ mgrep    │  │ mgrep    │  │ arxiv_   │  │ github_code_     │ │
│  │ (web)    │  │ (path)   │  │ search   │  │ search           │ │
│  │    or    │  │          │  │          │  │ (grep.app API)   │ │
│  │ tavily   │  │          │  │          │  │                  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
│                                                                   │
│  ┌──────────────────┐                                            │
│  │      docs        │                                            │
│  │                  │                                            │
│  │ library_docs_    │                                            │
│  │ search           │                                            │
│  │ (Context7 API)   │                                            │
│  └──────────────────┘                                            │
└─────────────────────────────────────────────────────────────────┘
```

v2 업데이트 (2026-01):
- mgrep 시맨틱 검색 통합 (2배 토큰 효율성)
- arXiv 학술 논문 검색
- grep.app GitHub 코드 검색
- Context7 라이브러리 문서 검색
- comprehensive_search 통합 도구
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Annotated, Literal

import httpx
from dotenv import load_dotenv
from langchain_core.tools import InjectedToolArg, tool
from markdownify import markdownify
from tavily import TavilyClient

# ============================================================================
# 환경 설정
# ============================================================================

load_dotenv()  # .env 파일에서 API 키 로드

# arXiv 패키지 선택적 임포트 (설치되지 않은 환경 지원)
try:
    import arxiv

    ARXIV_AVAILABLE = True
except ImportError:
    ARXIV_AVAILABLE = False
    arxiv = None  # type: ignore

# mgrep CLI 설치 여부 확인
MGREP_AVAILABLE = shutil.which("mgrep") is not None

# Tavily 클라이언트 초기화
tavily_client = TavilyClient()


# ============================================================================
# 헬퍼 함수
# ============================================================================


def fetch_webpage_content(url: str, timeout: float = 10.0) -> str:
    """웹페이지를 가져와서 HTML을 Markdown으로 변환한다.

    이 헬퍼 함수는 HTTP GET 요청을 수행하고(브라우저와 유사한 User-Agent 사용),
    응답 상태 코드를 검증한 후, `markdownify`를 사용하여 반환된 HTML을
    Markdown으로 변환합니다.

    참고:
        - 이 함수는 헬퍼 함수입니다(LangChain 도구가 아님).
        - `tavily_search` 같은 도구 래퍼가 전체 페이지 콘텐츠를 추출할 때 호출합니다.
        - 예외 발생 시 예외를 던지지 않고 사람이 읽을 수 있는 에러 문자열을 반환합니다.

    Args:
        url: 가져올 전체 URL (예: "https://example.com/article").
        timeout: 요청 타임아웃(초).

    Returns:
        웹페이지 콘텐츠의 Markdown 문자열.
        가져오기/변환 실패 시 다음 형식의 문자열 반환:
        "Error fetching content from {url}: {exception_message}".
    """
    # 브라우저처럼 보이는 User-Agent 헤더 설정
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        # HTTP GET 요청 수행
        response = httpx.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()  # 4xx, 5xx 에러 시 예외 발생

        # HTML을 Markdown으로 변환하여 반환
        return markdownify(response.text)
    except Exception as e:
        return f"Error fetching content from {url}: {str(e)}"


# ============================================================================
# 웹 검색 도구
# ============================================================================


@tool()
def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 1,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
) -> str:
    """Tavily를 사용해 웹을 검색하고 전체 페이지 콘텐츠를 Markdown으로 반환한다.

    이 도구는 두 단계로 동작합니다:
    1) Tavily Search를 사용하여 쿼리에 관련된 URL을 찾습니다.
    2) 각 결과 URL에 대해 `fetch_webpage_content`를 통해 전체 웹페이지 콘텐츠를
       가져와 Markdown으로 변환합니다.

    Args:
        query: 자연어 검색 쿼리 (예: "context engineering best practices").
        max_results: Tavily에서 가져올 최대 검색 결과 수.
            도구 주입 인자로 처리됨; 기본값은 1.
        topic: Tavily 토픽 필터. 허용 값:
            - "general"
            - "news"
            - "finance"
            도구 주입 인자로 처리됨; 기본값은 "general".

    Returns:
        다음을 포함하는 Markdown 형식 문자열:
        - 요약 헤더: "Found N result(s) for '{query}':"
        - 각 결과에 대해:
          - 제목
          - URL
          - Markdown으로 변환된 전체 웹페이지 콘텐츠
          - 구분선 ("---")

    Example:
        >>> tavily_search.invoke({"query": "LangGraph CLI configuration", "max_results": 2})
    """
    # Tavily API를 사용해 관련 URL 목록을 조회
    search_results = tavily_client.search(
        query,
        max_results=max_results,
        topic=topic,
    )

    # 각 검색 결과에 대해 전체 콘텐츠를 가져옴
    result_texts = []
    for result in search_results.get("results", []):
        url = result["url"]
        title = result["title"]

        # 웹페이지 콘텐츠를 가져와서 Markdown으로 변환
        content = fetch_webpage_content(url)

        # 결과 형식화
        result_text = f"""## {title}
**URL:** {url}

{content}

---
"""
        result_texts.append(result_text)

    # 최종 응답 형식으로 조합
    response = f"""Found {len(result_texts)} result(s) for '{query}':

{chr(10).join(result_texts)}"""

    return response


# ============================================================================
# 사고 도구 (Reflection Tool)
# ============================================================================


@tool()
def think_tool(reflection: str) -> str:
    """명시적 반성 단계를 강제하고 다음 행동을 기록한다.

    검색이나 주요 결정 시점 직후에 이 도구를 사용하여:
    - 학습한 내용 요약 (사실, 정의, 핵심 주장)
    - 부족한 부분 파악 (누락된 용어, 증거, 구현 세부사항)
    - 다음 구체적 단계 결정 (다음 쿼리, 다음 소스, 또는 종합 시작)

    이 도구는 자체적으로 상태를 유지하지 않습니다; 에이전트가 구조화된 방식으로
    추론을 외부화하도록 강제하기 위해 확인 문자열을 반환합니다.

    Args:
        reflection: 다음을 포함하는 간결하지만 구체적인 반성:
            - 학습한 내용 (글머리 기호로 정리 가능한 사실들)
            - 아직 누락된 부분
            - 다음 단계 (정확한 도구 + 정확한 쿼리)

    Returns:
        반성이 기록되었음을 나타내는 확인 문자열.
        (반환된 문자열은 로그/트랜스크립트에서 볼 수 있도록 의도됨.)

    Example:
        >>> think_tool.invoke({
        ...   "reflection": (
        ...     "Learned: RAG vs. context caching differ in latency/cost trade-offs. "
        ...     "Gap: need concrete caching APIs and constraints. "
        ...     "Next: library_docs_search(library_name='openai', query='response caching')."
        ...   )
        ... })
    """
    return f"Reflection recorded: {reflection}"


# ============================================================================
# 시맨틱 검색 도구 (mgrep)
# ============================================================================


@tool()
def mgrep_search(
    query: str,
    path: Annotated[str, InjectedToolArg] = ".",
    max_results: Annotated[int, InjectedToolArg] = 10,
    web: Annotated[bool, InjectedToolArg] = False,
) -> str:
    """`mgrep`을 사용하여 시맨틱 검색을 수행한다 (로컬 코드 또는 웹 답변 모드).

    이 도구는 `mgrep` CLI를 호출합니다:
    - 로컬 모드 (`web=False`): `path` 아래의 파일을 검색하고 매치를 반환.
    - 웹 모드 (`web=True`): `mgrep --web --answer`를 사용하여 웹 결과를
      검색하고 요약 (로컬 `mgrep` 설치에서 지원되는 경우).

    Args:
        query: 찾고자 하는 내용을 설명하는 자연어 검색 쿼리
            (예: "Where is ResearchDepth configured?").
        path: `web=False`일 때 검색할 파일시스템 경로. 기본값: ".".
            도구 주입 인자로 처리됨.
        max_results: 반환할 최대 결과 수. 기본값: 10.
            도구 주입 인자로 처리됨.
        web: True이면 `mgrep --web --answer`를 통해 웹 검색/답변 모드 수행.
            False이면 `path` 아래에서 로컬 시맨틱 검색 수행.
            도구 주입 인자로 처리됨.

    Returns:
        - 성공 시: `mgrep` stdout (트림됨), stdout이 비어있으면 "No results".
        - `mgrep` 미설치 시: 설치 안내 문자열.
        - 실패 시: 사람이 읽을 수 있는 에러 문자열 (stderr 또는 타임아웃 포함).

    Example:
        >>> mgrep_search.invoke({"query": "How is the researcher agent created?", "path": "research_agent"})
        >>> mgrep_search.invoke({"query": "latest agentic RAG techniques", "web": True, "max_results": 5})
    """
    # mgrep 설치 여부 확인
    if not MGREP_AVAILABLE:
        return (
            "mgrep is not installed. "
            "Install with `npm install -g @mixedbread/mgrep && mgrep login`."
        )

    # 명령어 구성
    cmd = ["mgrep", "-m", str(max_results)]

    # 웹 모드인 경우 추가 플래그 설정
    if web:
        cmd.extend(["--web", "--answer"])

    cmd.append(query)

    # 로컬 모드인 경우 경로 추가
    if not web:
        cmd.append(path)

    try:
        # 서브프로세스로 mgrep 실행
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # 60초 타임아웃
        )

        # 비정상 종료 시 에러 반환
        if result.returncode != 0:
            return f"mgrep error: {result.stderr.strip()}"

        # 결과 반환 (비어있으면 "No results")
        return result.stdout.strip() or "No results"

    except subprocess.TimeoutExpired:
        return "mgrep timeout (exceeded 60 seconds)"
    except Exception as e:
        return f"mgrep execution error: {e}"


# ============================================================================
# 학술 검색 도구 (arXiv)
# ============================================================================


@tool()
def arxiv_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 5,
    sort_by: Annotated[
        Literal["relevance", "submittedDate", "lastUpdatedDate"], InjectedToolArg
    ] = "relevance",
) -> str:
    """arXiv에서 학술 논문을 검색하고 Markdown 요약을 반환한다.

    선택적 `arxiv` Python 패키지를 사용합니다. 각 결과는 제목, 저자(처음 5명 +
    나머지 수), 출판 날짜, URL, 요약된 초록과 함께 Markdown으로 렌더링됩니다.

    Args:
        query: arXiv 쿼리 문자열 (예: "transformer architecture", "context engineering").
        max_results: 반환할 최대 논문 수. 기본값: 5.
        sort_by: 결과 정렬 기준. 다음 중 하나:
            - "relevance" (관련성)
            - "submittedDate" (제출 날짜)
            - "lastUpdatedDate" (마지막 업데이트 날짜)
            기본값: "relevance".

    Returns:
        다음을 포함하는 Markdown 문자열:
        - 찾은 논문 수를 나타내는 헤더
        - 각 논문에 대해: 제목, 저자, 출판 날짜, URL, 초록 발췌
        `arxiv` 패키지가 없으면 설치 안내 문자열 반환.
        결과가 없으면 "not found" 메시지 반환.

    Example:
        >>> arxiv_search.invoke({"query": "retrieval augmented generation evaluation", "max_results": 3})
    """
    # arxiv 패키지 설치 여부 확인
    if not ARXIV_AVAILABLE or arxiv is None:
        return "arxiv package not installed. Install with `pip install arxiv`."

    # 정렬 기준 매핑
    sort_criterion_map = {
        "relevance": arxiv.SortCriterion.Relevance,
        "submittedDate": arxiv.SortCriterion.SubmittedDate,
        "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
    }

    # arXiv 클라이언트 및 검색 객체 생성
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=sort_criterion_map.get(sort_by, arxiv.SortCriterion.Relevance),
    )

    # 검색 결과 처리
    results = []
    for paper in client.results(search):
        # 저자 목록 (최대 5명 + 나머지 수)
        authors = ", ".join(a.name for a in paper.authors[:5])
        if len(paper.authors) > 5:
            authors += f" et al. ({len(paper.authors) - 5} more)"

        # 초록 (최대 800자)
        abstract = paper.summary[:800]
        if len(paper.summary) > 800:
            abstract += "..."

        # Markdown 형식으로 결과 추가
        results.append(
            f"## {paper.title}\n\n"
            f"**Authors:** {authors}\n"
            f"**Published:** {paper.published.strftime('%Y-%m-%d')}\n"
            f"**URL:** {paper.entry_id}\n\n"
            f"### Abstract\n{abstract}\n\n---"
        )

    # 결과가 없으면 메시지 반환
    if not results:
        return f"No papers found for '{query}'."

    return f"Found {len(results)} paper(s) for '{query}':\n\n" + "\n\n".join(results)


# ============================================================================
# 통합 검색 도구
# ============================================================================


@tool()
def comprehensive_search(
    query: str,
    sources: Annotated[
        list[Literal["web", "local", "arxiv", "github", "docs"]], InjectedToolArg
    ] = ["web"],
    max_results_per_source: Annotated[int, InjectedToolArg] = 5,
    library_name: Annotated[str | None, InjectedToolArg] = None,
) -> str:
    """다중 소스 검색을 실행하고 결과를 단일 Markdown 보고서로 통합한다.

    이 도구는 `sources`에 따라 여러 다른 도구를 오케스트레이션합니다:
    - "local": 로컬 코드베이스에서 `mgrep_search` 실행.
    - "web": 가능하면 `mgrep_search`를 `web=True`로 사용; 그렇지 않으면
      `tavily_search`로 폴백.
    - "arxiv": `arxiv_search` 실행.
    - "github": `github_code_search` 실행.
    - "docs": `library_docs_search` 실행 (`library_name` 필요).

    Args:
        query: 선택된 소스에서 사용할 검색 쿼리.
        sources: 쿼리할 소스. 허용 값:
            "web", "local", "arxiv", "github", "docs".
        max_results_per_source: 소스당 최대 결과 수. 기본값: 5.
        library_name: "docs"가 `sources`에 포함된 경우 필수. Context7에서
            인식할 수 있는 라이브러리/제품 이름이어야 함 (예: "langchain").

    Returns:
        소스별 섹션 헤더가 있고 "---"로 구분된 Markdown 문자열.
        선택된 소스가 없으면 "no results" 메시지 반환.

    Example:
        >>> comprehensive_search.invoke({
        ...   "query": "how to configure LangGraph deployment",
        ...   "sources": ["web", "local", "docs"],
        ...   "library_name": "langgraph",
        ...   "max_results_per_source": 3
        ... })
    """
    all_results = []

    # 로컬 코드베이스 검색
    if "local" in sources:
        local_result = mgrep_search.invoke(
            {"query": query, "path": ".", "max_results": max_results_per_source}
        )
        all_results.append(f"# Local Codebase Search\n\n{local_result}")

    # 웹 검색
    if "web" in sources:
        if MGREP_AVAILABLE:
            # mgrep 웹 모드 사용 (설치된 경우)
            web_result = mgrep_search.invoke(
                {"query": query, "max_results": max_results_per_source, "web": True}
            )
        else:
            # Tavily로 폴백
            web_result = tavily_search.invoke(
                {"query": query, "max_results": max_results_per_source}
            )
        all_results.append(f"# Web Search Results\n\n{web_result}")

    # arXiv 학술 검색
    if "arxiv" in sources:
        arxiv_result = arxiv_search.invoke(
            {"query": query, "max_results": max_results_per_source}
        )
        all_results.append(f"# Academic Papers (arXiv)\n\n{arxiv_result}")

    # GitHub 코드 검색
    if "github" in sources:
        github_result = github_code_search.invoke(
            {"query": query, "max_results": max_results_per_source}
        )
        all_results.append(f"# GitHub Code Search\n\n{github_result}")

    # 공식 문서 검색
    if "docs" in sources and library_name:
        docs_result = library_docs_search.invoke(
            {"library_name": library_name, "query": query}
        )
        all_results.append(
            f"# Official Documentation ({library_name})\n\n{docs_result}"
        )

    # 결과가 없으면 메시지 반환
    if not all_results:
        return f"No search results found for '{query}'."

    # 모든 결과를 구분선으로 연결
    return "\n\n---\n\n".join(all_results)


# ============================================================================
# GitHub 코드 검색 도구
# ============================================================================


@tool()
def github_code_search(
    query: str,
    language: Annotated[list[str] | None, InjectedToolArg] = None,
    repo: Annotated[str | None, InjectedToolArg] = None,
    max_results: Annotated[int, InjectedToolArg] = 5,
    use_regex: Annotated[bool, InjectedToolArg] = False,
) -> str:
    """grep.app을 사용하여 공개 GitHub 코드를 검색하고 실제 예제를 반환한다.

    이 도구는 개념적 키워드가 아닌 *리터럴 코드 패턴*을 찾기 위한 것입니다.
    예: `useState(`, `getServerSession`, 또는 멀티라인 정규식 패턴.

    필터링 동작:
        - `repo`: 저장소 이름에 대한 부분 문자열 매치 (예: "vercel/").
        - `language`: grep.app의 언어 필드에 대한 정확한 매치.

    Args:
        query: 코드 검색 패턴. 리터럴 코드 토큰을 선호. 예:
            - "useState("
            - "async function"
            - "(?s)useEffect\\(\\(\\) => {.*removeEventListener" (`use_regex=True`와 함께)
        language: 포함할 언어 목록 (선택). 예: ["TypeScript", "Python"].
        repo: 저장소 필터 (선택). 예: "facebook/react", "vercel/".
        max_results: 출력에 포함할 최대 매치 수. 기본값: 5.
        use_regex: True이면 `query`를 정규표현식으로 해석. 기본값: False.

    Returns:
        매칭된 저장소와 스니펫을 나열하는 Markdown 문자열:
        - 저장소 이름
        - 파일 경로
        - 언어
        - 잘린 스니펫 (최대 ~500자)
        필터와 매치하는 결과가 없거나 HTTP 에러 발생 시 사람이 읽을 수 있는 메시지 반환.

    Example:
        >>> github_code_search.invoke({
        ...   "query": "getServerSession(",
        ...   "language": ["TypeScript", "TSX"],
        ...   "max_results": 3
        ... })
    """
    # grep.app API 엔드포인트
    base_url = "https://grep.app/api/search"

    # 요청 파라미터 구성
    params = {
        "q": query,
        "case": "false",  # 대소문자 구분 안함
        "words": "false",  # 단어 단위 매치 안함
        "regexp": str(use_regex).lower(),  # 정규식 사용 여부
    }

    # 요청 헤더 설정
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    try:
        # API 요청 수행
        response = httpx.get(base_url, params=params, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        # 검색 결과 추출
        hits = data.get("hits", {}).get("hits", [])

        # 결과가 없으면 메시지 반환
        if not hits:
            return f"No GitHub code found for '{query}'."

        results = []
        count = 0

        # 각 검색 결과 처리
        for hit in hits:
            # 최대 결과 수에 도달하면 중단
            if count >= max_results:
                break

            # 저장소 이름 추출
            repo_name = hit.get("repo", "unknown/unknown")

            # 저장소 필터 적용
            if repo and repo not in repo_name:
                continue

            # 파일 경로 및 브랜치 추출
            file_path = hit.get("path", "unknown")
            branch = hit.get("branch", "main")

            # 코드 스니펫 추출 및 HTML 태그 제거
            content_data = hit.get("content", {})
            snippet_html = content_data.get("snippet", "")
            import re

            # HTML 태그 제거
            snippet = re.sub(r"<[^>]+>", "", snippet_html)
            # HTML 엔티티 변환
            snippet = (
                snippet.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
            )
            # 빈 줄 제거 및 트림
            snippet = "\n".join(
                line.strip() for line in snippet.split("\n") if line.strip()
            )
            # 500자 초과 시 잘라냄
            snippet = snippet[:500] + "..." if len(snippet) > 500 else snippet

            # 파일 확장자에서 언어 추론
            lang = file_path.split(".")[-1] if "." in file_path else "unknown"
            lang_map = {
                "py": "python",
                "ts": "typescript",
                "js": "javascript",
                "tsx": "tsx",
                "jsx": "jsx",
            }
            lang = lang_map.get(lang, lang)

            # 언어 필터 적용
            if language and lang not in [l.lower() for l in language]:
                continue

            # GitHub URL 구성
            github_url = f"https://github.com/{repo_name}/blob/{branch}/{file_path}"

            # Markdown 형식으로 결과 추가
            results.append(
                f"## {repo_name}\n"
                f"**File:** [`{file_path}`]({github_url})\n"
                f"**Language:** {lang}\n\n"
                f"```{lang}\n{snippet}\n```\n"
            )
            count += 1

        # 필터 적용 후 결과가 없으면 메시지 반환
        if not results:
            filter_msg = ""
            if language:
                filter_msg += f" (language: {language})"
            if repo:
                filter_msg += f" (repo: {repo})"
            return f"No GitHub code found for '{query}'{filter_msg}."

        # 결과 반환
        return (
            f"Found {len(results)} GitHub code snippet(s) for '{query}':\n\n"
            + "\n---\n".join(results)
        )

    except httpx.TimeoutException:
        return "GitHub code search timeout (exceeded 30 seconds)"
    except httpx.HTTPStatusError as e:
        return f"GitHub code search HTTP error: {e.response.status_code}"
    except Exception as e:
        return f"GitHub code search error: {e}"


# ============================================================================
# 라이브러리 문서 검색 도구 (Context7)
# ============================================================================


@tool()
def library_docs_search(
    library_name: str,
    query: str,
    max_tokens: Annotated[int, InjectedToolArg] = 5000,
) -> str:
    """Context7을 사용하여 공식 라이브러리 문서를 검색한다.

    이 도구는 다음을 수행합니다:
    1) `library_name`을 Context7 `libraryId`로 해석.
    2) 제공된 `query`로 Context7 문서를 쿼리.

    Args:
        library_name: 해석할 라이브러리/제품 이름 (예: "langchain", "react", "fastapi").
        query: 특정 문서 쿼리 (예: "how to configure retries", "authentication middleware").
        max_tokens: 반환된 문서 콘텐츠의 최대 토큰 예산. 기본값: 5000.

    Returns:
        다음을 포함하는 Markdown 문자열:
        - 라이브러리 제목
        - 쿼리
        - 해석된 라이브러리 ID
        - 추출된 문서 콘텐츠
        타임아웃, HTTP 실패, 라이브러리 누락, 빈 결과 시 사람이 읽을 수 있는 에러 메시지 반환.

    Example:
        >>> library_docs_search.invoke({
        ...   "library_name": "langchain",
        ...   "query": "Tool calling with InjectedToolArg",
        ...   "max_tokens": 2000
        ... })
    """
    # Context7 API 엔드포인트
    resolve_url = "https://context7.com/api/v1/resolve-library-id"
    query_url = "https://context7.com/api/v1/query-docs"

    # 요청 헤더
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "DeepResearchAgent/1.0",
    }

    try:
        # 1단계: 라이브러리 이름을 ID로 해석
        resolve_response = httpx.post(
            resolve_url,
            json={"libraryName": library_name, "query": query},
            headers=headers,
            timeout=30.0,
        )

        # 라이브러리를 찾지 못한 경우
        if resolve_response.status_code == 404:
            return f"Library '{library_name}' not found in Context7."

        resolve_response.raise_for_status()
        resolve_data = resolve_response.json()

        # 라이브러리 목록 확인
        libraries = resolve_data.get("libraries", [])
        if not libraries:
            return f"No documentation found for '{library_name}'."

        # 첫 번째 결과에서 ID와 제목 추출
        library_id = libraries[0].get("id", "")
        library_title = libraries[0].get("name", library_name)

        if not library_id:
            return f"Could not resolve library ID for '{library_name}'."

        # 2단계: 문서 쿼리
        docs_response = httpx.post(
            query_url,
            json={
                "libraryId": library_id,
                "query": query,
                "maxTokens": max_tokens,
            },
            headers=headers,
            timeout=60.0,  # 문서 쿼리는 더 긴 타임아웃
        )
        docs_response.raise_for_status()
        docs_data = docs_response.json()

        # 콘텐츠 추출
        content = docs_data.get("content", "")
        if not content:
            return f"No documentation found for '{query}' in '{library_name}'."

        # 결과 반환
        return (
            f"# {library_title} Official Documentation\n\n"
            f"**Query:** {query}\n"
            f"**Library ID:** {library_id}\n\n"
            f"---\n\n{content}"
        )

    except httpx.TimeoutException:
        return f"Library docs search timeout (library: {library_name})"
    except httpx.HTTPStatusError as e:
        return f"Library docs search HTTP error: {e.response.status_code}"
    except Exception as e:
        return f"Library docs search error: {e}"
