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


def run_agent(session_id: str, user_message: str) -> dict:
    """에이전트에 메시지를 보내고 응답을 파싱하여 반환합니다."""
    runner = get_runner()
    content = types.Content(
        role="user",
        parts=[types.Part(text=user_message)],
    )

    thinking_parts: list[str] = []
    text_parts: list[str] = []
    all_function_calls: list = []
    all_function_responses: list = []

    for event in runner.run(
        user_id=USER_ID,
        session_id=session_id,
        new_message=content,
    ):
        if not event.content or not event.content.parts:
            continue

        for part in event.content.parts:
            if part.function_call:
                all_function_calls.append(part.function_call)
            elif part.function_response:
                all_function_responses.append(part.function_response)
            elif part.text and not event.partial:
                if getattr(part, "thought", False):
                    thinking_parts.append(part.text)
                else:
                    text_parts.append(part.text)

    # function_call과 function_response를 순서대로 매칭
    tool_interactions = []
    for fc, fr in zip(all_function_calls, all_function_responses):
        tool_interactions.append(
            {
                "name": fc.name,
                "args": dict(fc.args) if fc.args else {},
                "response": dict(fr.response) if fr and fr.response else {},
            }
        )

    return {
        "content": "".join(text_parts),
        "thinking": "\n".join(thinking_parts),
        "tool_interactions": tool_interactions,
    }


def reset_database():
    """DB와 에이전트 세션을 초기화합니다."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()
    get_runner.clear()
    st.session_state.messages = []
    st.session_state.session_id = str(uuid.uuid4())


def render_assistant_message(msg: dict):
    """assistant 메시지의 thinking, 툴 호출, 텍스트를 렌더링합니다."""
    if msg.get("thinking"):
        with st.expander("사고 과정", icon="💭"):
            st.markdown(msg["thinking"])

    for tool in msg.get("tool_interactions", []):
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
    st.caption("시설 유지보수 문의를 도와드립니다.")
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

# --- 사용자 입력 처리 ---
if prompt := st.chat_input("메시지를 입력하세요"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("답변을 생성 중입니다..."):
            response = run_agent(st.session_state.session_id, prompt)

        render_assistant_message(response)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response["content"],
            "thinking": response.get("thinking", ""),
            "tool_interactions": response.get("tool_interactions", []),
        }
    )
