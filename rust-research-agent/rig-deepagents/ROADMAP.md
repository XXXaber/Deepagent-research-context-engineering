# DeepAgents: 상세 구성 및 향후 계획

> **작성자**: Senior Rust Engineer / AI Architect
> **대상**: `rig-deepagents` 프로젝트
> **목표**: 현재 아키텍처의 상세 분석과 엔터프라이즈급 완성을 위한 향후 로드맵 제시

---

## 🏗 Part 1: 상세 아키텍처 (Detailed Configuration)

`rig-deepagents`는 단순한 에이전트 스크립트가 아니라, **미들웨어 기반의 에이전트 런타임**입니다. Python의 LangGraph나 LangChain과 유사한 엔터프라이즈 기능을 Rust의 타입 안정성과 고성능으로 구현하는 것을 목표로 합니다.

### 1. 핵심 아키텍처: 인터셉터 패턴 (Interceptor Pattern)

표준 `rig-core` 에이전트와 달리, 이 시스템은 **미들웨어 스택(Middleware Stack)** 을 중심으로 동작합니다. 모든 LLM 요청과 도구 실행은 일련의 훅(Hook)을 통과합니다.

#### 실행 루프 (Executor Loop in `executor.rs`)
`AgentExecutor`는 단순한 반복문이 아닌 정교한 상태 머신(State Machine)입니다:

1.  **Before Agent**: 에이전트 시작 전, 미들웨어가 초기 상태를 설정합니다 (예: DB에서 체크포인트 로드).
2.  **순환 단계 (Loop)**:
    *   **Before Model**: 미들웨어가 다음을 수행할 수 있습니다.
        *   **요청 수정**: 검색 결과나 파일 내용을 컨텍스트에 동적으로 주입.
        *   **Skip**: 캐시된 응답이 있다면 LLM 호출을 건너뜀.
        *   **Interrupt**: 사람의 승인이 필요할 경우 실행을 일시 정지 (`ModelControl::Interrupt`).
    *   **LLM Call**: `LLMProvider` 트레이트를 통해 모델 호출.
    *   **After Model**: 응답 검증, 로깅, 또는 개인정보 마스킹 처리.
    *   **Tool Execution**: 도구 실행 및 결과 처리.
3.  **After Agent**: 최종 정리 및 상태 저장.

```rust
// 제어 흐름 예시
match before_control {
    ModelControl::Interrupt(i) => return Err(DeepAgentError::Interrupt(i)), // HITL 지원
    ModelControl::Skip(resp) => resp.message,
    ModelControl::Continue => llm.complete(...).await?,
}
```

### 2. 추상화 계층 (Abstraction Layers)

시스템은 테스트 용이성과 확장성을 위해 주요 컴포넌트를 추상화했습니다.

*   **`LLMProvider` Trait**: Rig의 기본 클라이언트를 감쌉니다. 이를 통해 토큰 사용량 계산, 속도 제한(Rate Limiting), 테스트용 Mock 응답 주입이 가능합니다.
*   **`Backend` Trait**: 물리적 환경(OS)에 대한 접근을 추상화합니다.
    *   **`FilesystemBackend`**: 실제 프로덕션용 파일 시스템 접근.
    *   **`MemoryBackend`**: 테스트 및 샌드박스용 인메모리 파일 시스템. 이를 통해 "모든 파일 삭제" 같은 위험한 에이전트 행동도 안전하게 테스트할 수 있습니다.

### 3. Pregel 그래프 런타임 (`pregel/`)

LangGraph에서 영감을 받은 DAG(Directed Acyclic Graph) 런타임입니다.
*   **Nodes**: 개별 작업 단위 (예: "Planning", "Execution", "Review").
*   **Checkpointer**: 노드 간 전환 시점마다 상태를 영구 저장소(SQLite, Redis 등)에 스냅샷으로 저장합니다. 이를 통해 서버가 재시작되어도 에이전트의 기억이 유지됩니다.

---

## 🗺 Part 2: 0.27.x 호환성 및 마이그레이션 (0.27.x Compatibility & Migration)

최근 분석(`deliverable.md`, `streaming_prompt_hook_llmconfig_plan.md`)을 통해 식별된 Rig 0.27과의 통합 이슈를 해결하기 위한 우선순위 계획입니다.

### 1단계: 핵심 정합성 확보 (Core Consistency) - P0
**목표**: `LLMConfig`와 실제 동작의 불일치 해소

- [ ] **LLMConfig 적용 수정**
    - **문제**: `RigAgentAdapter`가 `LLMConfig`의 `model`, `api_key`, `api_base` 필드를 무시함.
    - **해결안**:
        1.  `RigAgentAdapter`에 Provider Factory를 도입하여 설정값에 기반한 에이전트 생성 지원.
        2.  또는, 문서화를 통해 해당 필드가 `AgentBuilder` 외부에서만 유효함을 명시하고 로깅 추가.

### 2단계: 스트리밍 완벽 지원 (Streaming Parity) - P0.5
**목표**: 사용자 경험(UX) 향상 및 Rig 기능 완전 구현

- [ ] **Tool Call Streaming 지원**
    - **문제**: 현재 `RigAgentAdapter::stream`은 텍스트와 최종 Usage만 방출하며, 도구 호출(Tool Call) 스트리밍은 무시됨.
    - **해결안**: `MessageChunk` 구조체를 확장하거나 별도 이벤트를 통해 Tool Call Delta를 클라이언트로 전송하도록 구현.
- [ ] **Executor Streaming 경로 추가**
    - **계획**: 현재 `complete()`만 사용하는 `AgentExecutor`에 `run_streaming()` 메서드를 추가하여 실시간 응답 지원.

### 3단계: 복원력 및 통합 (Resiliency & Integration) - P1
**목표**: 예외 상황 처리 및 고급 기능 연동

- [ ] **Tool Call 파싱 복원력 (Fallback Parsing)**
    - **문제**: 일부 모델이 Tool Call을 순수 JSON 텍스트로 반환할 경우 처리 실패.
    - **해결안**: Rig 표준 파싱 실패 시, JSON Fallback 파서를 통해 복구 시도 로직 추가.
- [ ] **PromptHook 연동**
    - **계획**: Rig의 `PromptHook` 생명주기 이벤트를 DeepAgents 미들웨어 시스템과 연결하거나, 명시적으로 "미들웨어 사용 권장" 정책 수립.

---

## 🚀 Part 3: 장기 개발 로드맵 (Long-term Roadmap)

### 3-1. 핵심 안정성 및 관측 가능성 (Stability & Observability)
- [ ] **OpenTelemetry 계측 (Tracing)**
    - `tracing-opentelemetry`를 도입하여 미들웨어 스택 간 Latency 및 데이터 흐름 시각화.
- [ ] **구조화된 에러 핸들링 고도화**
    - `thiserror`를 확장하여 `Retryable`(재시도 가능) 여부를 명시적으로 구분.

### 3-2. 기능 확장 (Feature Expansion)
- [ ] **고급 Checkpointing 백엔드**
    - `zstd` 압축 지원 및 비동기 백그라운드 스냅샷 저장(Background Persistence).
- [ ] **Human-in-the-Loop (HITL) 표준 API**
    - 외부 시스템에서 중단된 작업을 조회/재개할 수 있는 `resume(checkpoint_id, feedback)` 인터페이스 표준화.

### 3-3. 보안 및 샌드박싱 (Security & Sandboxing)
- [ ] **WASM 기반 도구 실행**
    - `wasm32-wasi` 컴파일 및 Wasmtime 런타임 위에서 도구 실행 격리.
- [ ] **Docker 컨테이너 백엔드**
    - 파일 시스템 조작을 일회용 컨테이너 내부로 제한하는 `DockerBackend` 구현.

### 3-4. 생태계 통합 (Ecosystem Integration)
- [ ] **MCP (Model Context Protocol) 서버 구현**
    - 이 에이전트를 MCP 서버로 노출하여 Claude Desktop 등에서 호출 가능하게 지원.
- [ ] **동적 미들웨어 구성**
    - 런타임 설정(JSON/YAML)으로 미들웨어 파이프라인 동적 구성.

---

## 📝 결론
`rig-deepagents`는 Rig Framework 0.27의 강력한 기능을 기반으로 하면서도, **Enterprise-Grade** 요구사항(체크포인팅, 미들웨어 제어, 샌드박싱)을 충족하기 위한 독자적인 레이어를 구축하고 있습니다. 단기적으로는 Rig와의 100% 호환성(스트리밍, 설정)을 확보하고, 장기적으로는 보안과 관측성을 강화하는 방향으로 나아갈 것입니다.
