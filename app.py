import json
import os
import uuid
from pathlib import Path

import streamlit as st

# --- 환경 변수: st.secrets (Cloud) > .env (로컬) ---
try:
    for key in ("GOOGLE_API_KEY", "GMAIL_USER", "GMAIL_APP_PASSWORD"):
        if key in st.secrets:
            os.environ.setdefault(key, st.secrets[key])
except FileNotFoundError:
    pass

if "GOOGLE_API_KEY" not in os.environ:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / "maintenance_agent" / ".env")

# --- Agent / Runner 초기화 (import 전에 환경 변수 설정 필요) ---
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from maintenance_agent.agent import root_agent
from maintenance_agent.db import DB_PATH, init_db

APP_NAME = "maintenance_agent"
USER_ID = "streamlit_user"


@st.cache_resource
def get_runner():
    return Runner(
        app_name=APP_NAME,
        agent=root_agent,
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )


def reset_database():
    """DB와 에이전트 세션을 초기화합니다."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()
    get_runner.clear()
    st.session_state.messages = []
    st.session_state.session_id = str(uuid.uuid4())


def render_tool(tool: dict):
    """툴 호출/응답을 st.status로 렌더링합니다."""
    with st.status(f"🔧 {tool['name']}", state="complete"):
        if tool["args"]:
            st.code(
                json.dumps(tool["args"], ensure_ascii=False, indent=2),
                language="json",
            )
        if tool["response"]:
            st.divider()
            st.caption("결과")
            st.code(
                json.dumps(tool["response"], ensure_ascii=False, indent=2),
                language="json",
            )


def render_assistant_message(msg: dict):
    """히스토리 재생용: assistant 메시지를 렌더링합니다."""
    if msg.get("thinking"):
        with st.expander("💭 사고 과정"):
            st.markdown(msg["thinking"])

    for tool in msg.get("tool_interactions", []):
        render_tool(tool)

    if msg.get("content"):
        st.markdown(msg["content"])


# --- 페이지 설정 ---
st.set_page_config(
    page_title="KindredPM 유지보수 비서",
    page_icon="🏠",
    layout="centered",
)

# --- 사이드바 ---
with st.sidebar:
    st.title("KindredPM 유지보수 비서")
    st.caption("AI 기반 시설 유지보수 자동화 데모")
    st.divider()

    st.subheader("지원 문제 유형")
    st.markdown(
        "- 싱크대 누수\n"
        "- 변기 막힘\n"
        "- 보일러 고장\n"
        "- 도어록 고장\n"
        "- 곰팡이/결로"
    )

    st.subheader("주요 기능")
    st.markdown(
        "- 문제 유형 자동 분류\n"
        "- 유형별 응급조치 안내\n"
        "- 수리 일정 예약/조회/취소\n"
        "- 예약 확인 이메일 자동 발송\n"
        "- AI 사고 과정 실시간 표시"
    )

    st.divider()
    if st.button("대화 초기화", use_container_width=True):
        reset_database()
        st.rerun()

# --- 세션 상태 초기화 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# --- 채팅 히스토리 렌더링 ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            render_assistant_message(msg)
        else:
            st.markdown(msg["content"])

# --- 초기 안내 메시지 ---
if not st.session_state.messages:
    st.markdown(
        "안녕하세요! **KindredPM 유지보수 비서**입니다.\n\n"
        "시설 문제 신고, 응급조치 안내, 수리 예약까지 도와드립니다.\n"
        "아래 예시를 클릭하거나 직접 입력해주세요."
    )
    examples = [
        "싱크대에서 물이 새요",
        "변기가 막혔어요",
        "보일러가 안 켜져요",
        "도어록이 고장났어요",
        "벽에 곰팡이가 생겼어요",
    ]
    cols = st.columns(3)
    for i, example in enumerate(examples):
        if cols[i % 3].button(example, use_container_width=True):
            st.session_state.pending_prompt = example
            st.rerun()

# --- 사용자 입력 처리 (스트리밍) ---
prompt = st.chat_input("메시지를 입력하세요") or st.session_state.pop(
    "pending_prompt", None
)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        runner = get_runner()
        content = types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        )

        thinking_text = ""
        thinking_md = None
        text_content = ""
        text_el = None
        pending_call = None
        tool_interactions = []

        run_config = RunConfig(streaming_mode=StreamingMode.SSE)
        thinking_status = st.status("응답 생성 중...", expanded=False)
        tool_container = st.container()
        text_container = st.container()

        for event in runner.run(
            user_id=USER_ID,
            session_id=st.session_state.session_id,
            new_message=content,
            run_config=run_config,
        ):
            if not event.content or not event.content.parts:
                continue

            is_partial = getattr(event, "partial", False)

            for part in event.content.parts:
                if getattr(part, "thought", False) and part.text and is_partial:
                    # --- Thinking 스트리밍 (partial 이벤트) ---
                    if thinking_md is None:
                        if thinking_status is None:
                            thinking_status = st.status("사고 중...", expanded=True)
                        else:
                            thinking_status.update(label="사고 중...", expanded=True)
                        thinking_md = thinking_status.empty()
                    thinking_text += part.text
                    thinking_md.markdown(thinking_text)

                elif part.function_call and not is_partial:
                    # --- 툴 호출 (aggregated 이벤트) ---
                    if thinking_status is not None:
                        thinking_status.update(label="💭 사고 과정", expanded=False)
                        thinking_md = None
                    pending_call = part.function_call

                elif part.function_response and not is_partial:
                    # --- 툴 응답 (aggregated 이벤트) ---
                    fr = part.function_response
                    call_name = pending_call.name if pending_call else fr.name
                    call_args = (
                        dict(pending_call.args)
                        if pending_call and pending_call.args
                        else {}
                    )
                    response_data = dict(fr.response) if fr.response else {}
                    tool_data = {
                        "name": call_name,
                        "args": call_args,
                        "response": response_data,
                    }
                    tool_interactions.append(tool_data)
                    with tool_container:
                        render_tool(tool_data)
                    pending_call = None

                elif part.text and not getattr(part, "thought", False) and is_partial:
                    # --- 응답 텍스트 스트리밍 (partial 이벤트) ---
                    if thinking_status is not None:
                        thinking_status.update(
                            label="💭 사고 과정", state="complete", expanded=False
                        )
                        thinking_status = None
                        thinking_md = None
                    text_content += part.text
                    if text_el is None:
                        text_el = text_container.empty()
                    text_el.markdown(text_content)

        if thinking_status is not None:
            thinking_status.update(
                label="💭 사고 과정", state="complete", expanded=False
            )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": text_content,
            "thinking": thinking_text,
            "tool_interactions": tool_interactions,
        }
    )
