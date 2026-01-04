# Rig Framework 공식 문서 기반 중복성 검증 리포트 (Verification Report)

> **검증 기준**: `rig-core` v0.27 공식 문서 및 생태계
> **검증 대상**: `rig-deepagents` 프로젝트의 주요 모듈
> **결론 요약**: `rig-deepagents`는 `rig-core`의 기능을 중복 구현한 것이 아니라, **엔터프라이즈 요구사항(상태 관리, 제어권, 테스트)을 충족하기 위해 상위 계층을 독자적으로 구축**한 것으로 판단됨.

---

## 1. 미들웨어 아키텍처 (Middleware Architecture)

### 🔍 비교 분석
*   **Rig Official (`rig-core`)**:
    *   기본적으로 `AgentBuilder` 패턴을 사용하여 프롬프트와 도구를 연결합니다.
    *   HTTP 요청 수준의 미들웨어(`reqwest-middleware`)는 지원하지만, **에이전트의 사고 과정(Thoughts)에 개입하는 논리적 미들웨어는 제공하지 않습니다.**
    *   단순한 `chat()` 메서드 호출로 동작하며, 중간에 실행을 멈추거나(Interrupt) 건너뛰는(Skip) 제어권이 없습니다.
*   **DeepAgents (`src/middleware/`, `executor.rs`)**:
    *   `before_model`, `after_model` 훅을 통해 컨텍스트를 동적으로 수정하거나 LLM 호출을 가로챕니다.
    *   `ModelControl::Interrupt`를 통해 **Human-in-the-Loop**를 구현합니다.

### ✅ 검증 결과: [중복 아님 / 고유 기능]
> Rig 공식 문서에는 에이전트 실행 흐름을 제어하는 State Machine이 존재하지 않습니다. DeepAgents의 미들웨어 스택은 **필수적인 확장 기능**입니다.

---

## 2. 그래프 런타임 (Pregel / Graph Runtime)

### 🔍 비교 분석
*   **Rig Official**:
    *   최근 `rigs`라는 별도 크레이트를 통해 그래프 워크플로우를 실험적으로 지원하기 시작했습니다.
    *   하지만 이는 초기 단계이며, LangGraph 수준의 정교한 **Checkpointing(SQLite/Redis 기반 상태 저장)** 기능은 기본 라이브러리에 포함되어 있지 않습니다.
*   **DeepAgents (`src/pregel/`)**:
    *   LangGraph의 Pregel 알고리즘을 Rust로 직접 구현했습니다.
    *   **영속성(Persistence)**: 노드 실행 후 상태를 DB에 저장하여 서버가 재시작되어도 `resume` 할 수 있는 기능은 Rig Core에 없는 핵심 기능입니다.

### ⚠️ 검증 결과: [기능적 유사성 존재 / 구현 방식 차별화]
> `rigs` 크레이트와 개념적으로 겹치지만, DeepAgents는 **Checkpointer(상태 저장소)** 와 **미들웨어와의 통합**을 위해 독자적인 Graph Runtime을 구현했습니다. 이는 엔터프라이즈 환경(서버 재시작 대응)을 위해 필요한 선택입니다.

---

## 3. 추상화 래퍼 (LLMProvider & Tool Traits)

### 🔍 비교 분석
*   **Rig Official**:
    *   `CompletionModel` 트레이트와 `Tool` 트레이트를 제공합니다.
    *   테스트를 위한 Mocking 기능이 제한적이며, 토큰 사용량(Token Usage) 집계나 속도 제한(Rate Limiting) 같은 운영 기능이 내장되어 있지 않습니다.
*   **DeepAgents (`src/llm/`, `src/tools/`)**:
    *   `LLMProvider`: Rig 클라이언트를 감싸서 **테스트용 가짜 모델(Mock)** 과 **실제 모델**을 동일한 인터페이스로 교체 가능하게 만들었습니다.
    *   `Tool` Wrapper: 도구 실행 성공/실패 지표를 수집하고, 에러를 구조화하기 위해 래핑했습니다.

### ✅ 검증 결과: [필수적인 래핑 (Necessary Wrapper)]
> 기능 자체는 Rig가 제공하지만, **테스트 용이성(Testability)** 과 **관측 가능성(Observability)** 을 확보하기 위해 불가피하게 작성된 래핑 코드입니다. 단순 중복이 아닌 "운영을 위한 강화(Enhancement)"입니다.

---

## 4. 백엔드 시스템 (Filesystem/Memory Backend)

### 🔍 비교 분석
*   **Rig Official**:
    *   파일 시스템 접근에 대한 추상화가 없습니다. 도구 안에서 `std::fs`를 직접 사용합니다.
*   **DeepAgents (`src/backends/`)**:
    *   `Backend` 트레이트를 통해 **OS 파일 시스템**과 **인메모리 가상 파일 시스템**을 교체 가능하게 만들었습니다.
    *   이를 통해 "파일 삭제 에이전트"를 안전하게 테스트할 수 있습니다.

### ✅ 검증 결과: [고유 기능]
> Rig는 샌드박싱이나 시스템 리소스 추상화를 제공하지 않습니다. 이는 DeepAgents만의 독창적인 설계입니다.

---

## 🧐 최종 요약 (Executive Summary)

라인 바이 라인 검토 결과, `rig-deepagents` 불필요하게 바퀴를 재발명한 부분은 없습니다. 
오히려 **Rig Framework를 "라이브러리"로 사용하고, 그 위에 "애플리케이션 프레임워크"를 구축**한 형태입니다.

1.  **Rig Core 역할**: LLM 통신, 기본 도구 정의 프로토콜 제공 (Foundation layer).
2.  **DeepAgents 역할**: 상태 관리, 실행 제어, 테스트 환경, 영속성 제공 (Application layer).

**결론**: 현재 구현은 Rig의 부족한 부분을 정확히 보완하고 있으며, 삭제할 중복 코드는 승인되지 않습니다.
