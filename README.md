# KindredPM 유지보수 비서

Google ADK 기반 시설 유지보수 AI 에이전트 데모.
임차인의 시설 문제 신고를 접수하고, 응급조치를 안내하며, 수리 일정을 예약합니다.

## 주요 기능

- **문제 유형 자동 분류** - 싱크대 누수, 변기 막힘, 보일러 고장, 도어록 고장, 곰팡이/결로
- **긴급 상황 판단** - 침수, 가스 누출 등 긴급 신호 감지 시 즉시 대응 안내
- **응급조치 안내** - 유형별 응급조치 가이드 제공
- **수리 예약 관리** - 예약 생성/조회/변경/취소, 7일치 슬롯 자동 관리
- **이메일 알림** - 예약 확인·취소 시 이메일 자동 발송
- **AI 사고 과정 표시** - 에이전트의 thinking과 tool 호출을 실시간 스트리밍

## Tech Stack

| 역할 | 기술 |
|------|------|
| LLM | Gemini 2.5 Pro (Google ADK) |
| Agent Framework | Google ADK |
| UI | Streamlit |
| DB | SQLite |
| Email | Gmail SMTP |

## 프로젝트 구조

```
app.py                        # Streamlit 채팅 앱
maintenance_agent/
├── agent.py                  # ADK Agent 설정 및 시스템 프롬프트
├── tools.py                  # Tool 구현 (응급조치, 예약, 이메일 등)
├── db.py                     # SQLite DB 레이어
└── .env                      # 환경 변수 (로컬용, 커밋 제외)
```

## 설치 및 실행

```bash
# 환경 생성
conda create -n kindredpm python=3.11 -y
conda activate kindredpm

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정 (아래 '환경 변수' 섹션 참고)
vi maintenance_agent/.env

# 실행
streamlit run app.py
```

## 환경 변수

`maintenance_agent/.env`에 아래 값을 설정합니다.

| 변수 | 설명 | 필수 |
|------|------|------|
| `GOOGLE_API_KEY` | Gemini API 키 | O |
| `GOOGLE_GENAI_USE_VERTEXAI` | Vertex AI 사용 여부 (`0` = API 키 방식) | O |
| `GMAIL_USER` | 알림 발송용 Gmail 주소 | O |
| `GMAIL_APP_PASSWORD` | Gmail 앱 비밀번호 | O |
