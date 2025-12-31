# DeepAgents 기반 Research Multi Agent System

Agent 2.0 Paradigm 을 잘 구현하는 DeepAgent 를 활용해서, FileSystem 기반 Context Engineering 을 원활히 수행하는 Research 용 Multi Agent 구성(From LangChain's deepagents library)

![agent_20_paradigm](./agent_20_paradigm.png)

## Agent 1.0 vs Agent 2.0

![agent_versus_10_20](./agent_versus_10_20.jpeg)

## DeepAgent Technical Guide

[DeepAgent Technical Guide](./DeepAgents_Technical_Guide.md)

## 프로젝트 구조

```bash
deepagent-context-engineering/
│
├── research_agent/              # 메인 에이전트 모듈
│   ├── researcher/              #    └─ 자율 연구 에이전트 (CompiledSubAgent)
│   ├── skills/                  #    └─ 스킬 미들웨어 (Progressive Disclosure)
│   └── subagents/               #    └─ SubAgent 정의 유틸리티
│
├── skills/                      # 프로젝트 레벨 스킬 정의
│   ├── academic-search/         #    └─ arXiv 논문 검색
│   ├── data-synthesis/          #    └─ 다중 소스 데이터 통합
│   ├── report-writing/          #    └─ 구조화된 보고서 작성
│   └── skill-creator/           #    └─ 스킬 생성 메타스킬
│
├── research_workspace/          # 연구 결과물 저장소 (가상 파일시스템의 ROOT)
│   └── (에이전트가 생성한 보고서, TODO 등)
│
├── deep-agents-ui/              # DeepAgent 프론트엔드 UI (Next.js + React)
│   └── src/                     #    └─ 소스 코드
│
├── deepagents_sourcecode/       # DeepAgents 라이브러리 소스 참조
│   └── libs/                    #    └─ 라이브러리 코드
│
├── DeepAgent_research.ipynb     # Research DeepAgent 활용 노트북
├── DeepAgents_Technical_Guide.md # DeepAgents 가이드 (한국어)
├── langgraph.json               # LangGraph API 배포 설정
└── pyproject.toml               # Python 프로젝트 설정 (uv package manager)
```

### 주요 디렉토리 설명

| 디렉토리 | 설명 |
|----------|------|
| `research_agent/` | DeepAgent 기반 멀티 에이전트 시스템의 핵심 모듈 |
| `skills/` | YAML 프론트매터 기반 스킬 정의 (SKILL.md 파일들) |
| `research_workspace/` | 에이전트의 영구 파일시스템 저장소 |
| `deep-agents-ui/` | LangChain 제공 DeepAgent 시각화 UI |

---

## DeepAgent 기반의 Research 수행용 MAS(Multi Agent System)

```bash
research_agent/
├── agent.py                 # 메인 오케스트레이터 (create_deep_agent)
├── prompts.py               # 오케스트레이터 및 Simple SubAgent 프롬프트
├── tools.py                 # tavily_search, think_tool
├── utils.py                 # 노트북 시각화 헬퍼
│
├── researcher/              # 자율적 연구 에이전트 모듈 (NEW)
│   ├── __init__.py          # 모듈 exports
│   ├── agent.py             # create_researcher_agent, get_researcher_subagent
│   └── prompts.py           # AUTONOMOUS_RESEARCHER_INSTRUCTIONS
│
├── skills/                  # Skills 미들웨어
│   └── middleware.py        # SkillsMiddleware (Progressive Disclosure)
│
└── subagents/               # SubAgent 유틸리티
    └── definitions.py       # SubAgent 정의 헬퍼
```

### 핵심 파일 설명

| 파일 | 역할 |
|------|------|
| `agent.py` | 메인 에이전트 생성 및 구성 |
| `researcher/agent.py` | 자율적으로 연구하게끔 구성된 에이전트 |
| `researcher/prompts.py` | "넓게 탐색 → 깊게 파기" 전략으로 구성된 워크플로우 정의 |
| `prompts.py` | 오케스트레이터(Main DeepAgent) 워크플로우 및 위임(Delegation) 전략 |


## DeepAgent UI(Made by LangChain)
```bash
git clone https://github.com/langchain-ai/deep-agents-ui.git
cd deep-agents-ui
npm install -g yarn
yarn install
yarn dev
```


### 참고자료

- [LangChain DeepAgent Docs](https://docs.langchain.com/oss/python/deepagents/overview)
- [LangGraph CLI Docs](https://docs.langchain.com/langsmith/cli#configuration-file)
- [DeepAgent UI](https://github.com/langchain-ai/deep-agents-ui)
- [Agents-2.0-deep-agents](https://www.philschmid.de/agents-2.0-deep-agents)
