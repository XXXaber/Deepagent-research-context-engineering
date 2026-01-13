직접 구현과 오픈소스 활용 기준이 궁금합니다. 

(e.g. 복잡한 RDB에서 사용자의 자연어 입력으로 데이터 검색을 해야할때 검색 에이전트 또는 mcp를 직접 구현하는것 VS vanna ai 같은 오픈소스를 사용하는 것) 

강사님 같은 경우에는 어떤 선택을 할지 궁금합니다.

Q: 데이터마트 Agent

MCP 도구: Query Execute

---

Skills: 
    1. 회원 정보 스킬
    2. 구매 정보 스킬...


MCP가 특정 기능을 수행하기 위한 tool의 집합이라면, 
skills는 개별 tool들을 context를 덜 잡아먹는 방법으로 나열해놓은 것이라고 이해해도 될까요?

Tool search tools


langchain에서 만든 skill GitHub repository가 있는건가요? 
보여주신 axriv search 처럼요.
>> awesome-skills

표준 MCP포맷으로 도구를 정의하는것 대비
랭체인의 bind_tool 형식으로 붙여서 툴콜링하는것과
비교하면 토큰사용이 후자가 좀 더 효율적이지 않나요?

function_call 스펙이 다 다름...
Openai
Gemini
Anthropic
-> MCP (langchain tool)

챗봇을 만든다고 할때 사용자의 챗 기록이 메모리에 점점 쌓여서 
컨텍스트 윈도우가 다 찼을때 강사님께서는 어떻게 대처하시나요?

메모리는 외부에 Redis 레이어를 별도로 빼서 주기적으로 compact하거나 정돈하는 방법론이 있습니다. 참고: https://youtu.be/UhsESUrjTjg?si=5j-LTwIms0PNhHOD

MCP 호출하면
안에 Resources랑, Prompt 같은것들도 도구 사용을 위해 가져올 수 있었는데
Skill에도 이런것들을 정의하나요?

---

근데 지금 모델들 보면 MoE추론기 붙으면서
각 모델별로 reasoning parser이랑 toolcall parser다 표준없이 난립하고 있잖아요
gpt oss도 하모니 포맷때문에 머리터지는줄 알았는데

강사님 오프라인 강의는 다음 차수는 없는걸까요?

사내 레거시 서버에서 api 통신을 한다면 mcp server-mcp 호출 보다 
그냥 백엔드 파이썬 코드 api 통신-skills 이렇게 가는게 더 나은 방향이라고 생각하시나요?

SKILL.md (HTTP 호출 할 수 있음)
- get/run.py
- post/run.py


Agent 개발 시에 langchain과 같은 라이브러리를 이용하는 것이 
빠르고 편해보이는데, 단점도 있을까요? 
예를 들면 python을 이용해 직접 구현 하는것의 장점?

여러 멀티 에이전트 종류들 중에서 강사님은 주로 어떤걸 선택하시나요? 
e.g. supervisor


프롬포트 엔지지어링 이슈인지 모르겠는데, 
저는 CV 연구를 하는데 "데이터" import export를 모델이 잘 처리 못해주던데, 
혹시 그런건 왜그런거고 어떻게 해야 잘 만들어줄까요?

파이썬을 이용해 직접구현은
아에 새로운 라이브러를 만드시나요?
아니면 랭체인 내부에 파편화된 base 모듈을 wrapping해서 만드시나요?

Skills에 코드 실행은 파이썬이 아니라 go 같은것도 되는지요?

실무에서 Workflow로 일일히 각 노드랑 분기 정해주는 거 외에 
Agent가 자동으로 선택하겠끔 하는 ReAct 패턴 같은 것도 실제로 많이 쓰시나요?

이미지 input 차원이 너무 커서 해당부분만 개발하는데 2~3일이 걸려서요. 
저만 그런건지 이상하게 input을 잘 못만들어주더라구요.. ㅜㅜ

langchain와 같은 agent framework를 사용해서 node와 edge를 직접 구현하는 대신에
claude agent sdk와 같은 기술을 사용하는 건 어떻게 생각하시나요?