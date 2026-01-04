# TASKS.md - 상세 작업 분류 (Granular Task Breakdown)

> **기준**: `ROADMAP.md`에 정의된 항목을 구체적인 파일 및 함수 수준의 작업으로 세분화

---

## 🔴 EPIC 1: LLMConfig 정합성 확보 (P0)

### 배경
`RigAgentAdapter::complete()` 및 `stream()`이 `LLMConfig`의 `temperature`, `max_tokens`만 사용하고 `model`, `api_key`, `api_base`는 무시함.

### 작업 목록

#### Task 1.1: LLMConfig 필드 활용 정책 결정
- **유형**: Design Decision
- **담당 파일**: N/A (문서 작업)
- **작업 내용**:
    - [ ] Option A (Per-Request 모델 변경 지원): `RigAgentAdapter`에 에이전트/클라이언트 팩토리 도입. 캐싱 전략 설계.
    - [ ] Option B (No-Op 명시화): `model`/`api_key` 필드를 deprecated 처리하고 경고 로그 추가.
- **산출물**: 선택한 옵션 및 근거를 `docs/DECISION_GUIDE.md`에 기록.

#### Task 1.2: `RigAgentAdapter` 수정 (Option A 선택 시)
- **유형**: Code Change
- **담당 파일**: `src/compat/rig_agent_adapter.rs`
- **담당 함수**: `new()`, `complete()`, `stream()`
- **작업 내용**:
    - [ ] `RigAgentAdapterFactory` 구조체 또는 메서드 신규 추가.
    - [ ] `complete()`/`stream()` 내에서 `config.model`이 지정되면 해당 모델 에이전트를 캐시에서 조회하거나 생성.
- **테스트**: `tests/rig_adapter_config_test.rs` (신규 작성 필요)

#### Task 1.3: `RigAgentAdapter` 수정 (Option B 선택 시)
- **유형**: Code Change
- **담당 파일**: `src/compat/rig_agent_adapter.rs`
- **담당 함수**: `complete()`, `stream()`
- **작업 내용**:
    - [ ] `config.model`/`api_key`가 설정되어 있으면 `tracing::warn!` 로그 출력.
    - [ ] 문서 주석에 해당 필드가 무시됨을 명시.
- **테스트**: 기존 테스트에서 경고 로그 발생 여부 확인.

---

## 🟠 EPIC 2: 스트리밍 완벽 지원 (P0.5)

### 배경
`RigAgentAdapter::stream()`이 텍스트/Usage만 방출하고 Tool Call Delta를 무시함. `AgentExecutor`에 스트리밍 실행 경로 없음.

### 작업 목록

#### Task 2.1: `MessageChunk` 확장
- **유형**: Code Change
- **담당 파일**: `src/llm/provider.rs`
- **담당 구조체**: `MessageChunk`
- **작업 내용**:
    - [ ] `MessageChunk` enum에 `ToolCallDelta` 변형 추가.
    ```rust
    pub enum MessageChunk {
        Content { delta: String },
        ToolCallDelta { id: String, name: Option<String>, args_delta: String },
        Usage(TokenUsage),
        Done,
    }
    ```
- **테스트**: `src/llm/provider.rs` 내 `tests` 모듈에 단위 테스트 추가.

#### Task 2.2: `RigAgentAdapter::stream()` 수정
- **유형**: Code Change
- **담당 파일**: `src/compat/rig_agent_adapter.rs`
- **담당 함수**: `stream()`
- **작업 내용**:
    - [ ] Rig 스트림 아이템 중 `ToolCall` 관련 항목을 `MessageChunk::ToolCallDelta`로 변환하는 로직 추가.
    - [ ] Rig 0.27 `StreamedAssistantContent` API 구조 확인 및 매핑.
- **선행 조건**: Rig 0.27.0의 스트리밍 API 구조 확인 필요 (docs.rs 또는 Rig 레포 확인).
- **테스트**: `tests/streaming_adapter_test.rs` (신규)

#### Task 2.3: `AgentExecutor::run_streaming()` 추가
- **유형**: Code Change (Major)
- **담당 파일**: `src/executor.rs`
- **담당 구조체**: `AgentExecutor`
- **작업 내용**:
    - [ ] `run_streaming(&self, initial_state: AgentState) -> impl Stream<Item = ...>` 메서드 신규 구현.
    - [ ] 스트리밍 중 Tool Call Delta를 수집하고, 완료 시 일괄 실행하는 로직 설계.
    - [ ] 미들웨어 `before_model`/`after_model` 훅과의 호환성 확보.
- **테스트**: `tests/executor_streaming_test.rs` (신규)

---

## 🟡 EPIC 3: 복원력 및 통합 (P1)

### 작업 목록

#### Task 3.1: Tool Call JSON Fallback Parser
- **유형**: Code Change
- **담당 파일**: `src/compat/rig_agent_adapter.rs` 또는 `src/llm/mod.rs` (신규 모듈)
- **작업 내용**:
    - [ ] Rig 응답에서 Tool Call 구조가 없고, 응답 텍스트가 JSON 형태일 경우 수동 파싱 시도하는 `try_parse_tool_call_from_text()` 함수 구현.
    - [ ] `complete()` 함수 내에서 fallback 호출.
- **테스트**: 다양한 JSON 형태의 응답에 대한 단위 테스트.

#### Task 3.2: PromptHook 연동 설계
- **유형**: Design / Evaluation
- **담당 파일**: N/A
- **작업 내용**:
    - [ ] Rig `PromptHook` API 조사 (어떤 생명주기 이벤트가 발생하는지).
    - [ ] DeepAgents 미들웨어(`before_model`/`after_model`)와의 관계 정의.
    - [ ] "미들웨어 우선" 또는 "PromptHook 브릿지 구현" 결정.
- **산출물**: 결정 사항을 `docs/DECISION_GUIDE.md`에 기록.

---

## 🟢 EPIC 4: 장기 로드맵 (P2+)

### Task 4.1: OpenTelemetry 계측
- **담당 파일**: `src/executor.rs`, `src/middleware/traits.rs`
- **작업 내용**: `#[instrument]` 매크로 적용, `tracing-opentelemetry` 레이어 추가.

### Task 4.2: Checkpointing 압축 (`zstd`)
- **담당 파일**: `src/pregel/checkpoint/mod.rs` 및 백엔드 파일들
- **작업 내용**: 기존 JSON 직렬화에 `zstd` 압축 옵션 추가.

### Task 4.3: HITL Resume API 표준화
- **담당 파일**: `src/pregel/runtime.rs`, `src/workflow/compiled.rs`
- **작업 내용**: `resume(checkpoint_id: &str, feedback: Value)` 인터페이스 정의 및 구현.

### Task 4.4: WASM Tool Sandbox
- **담당 파일**: `src/backends/mod.rs` (신규 `WasmBackend` 모듈)
- **작업 내용**: Wasmtime 런타임 통합, 도구를 WASI 모듈로 실행.

### Task 4.5: MCP 서버 구현
- **담당 파일**: `src/bin/mcp_server.rs` (신규)
- **작업 내용**: MCP 프로토콜 핸들러 구현, 기존 도구들을 MCP Tool로 노출.

### Task 4.6: 동적 미들웨어 구성
- **담당 파일**: `src/middleware/stack.rs`, `src/config.rs`
- **작업 내용**: JSON/YAML 파일에서 미들웨어 파이프라인을 읽어 런타임에 구성하는 기능.

---

## 📋 작업 우선순위 매트릭스

| Epic | 우선순위 | 핵심 파일 | 예상 공수 |
|------|---------|-----------|----------|
| 1. LLMConfig | P0 | `rig_agent_adapter.rs` | 1-2일 |
| 2. Streaming | P0.5 | `provider.rs`, `executor.rs`, `rig_agent_adapter.rs` | 3-5일 |
| 3. Fallback/Hook | P1 | `rig_agent_adapter.rs` | 2-3일 |
| 4. Observability | P2 | `executor.rs`, `middleware/` | 2일 |
| 5. Checkpointing | P2 | `pregel/checkpoint/` | 2일 |
| 6. Security/MCP | P3 | 신규 모듈 | 1주+ |
