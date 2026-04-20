import socket
import subprocess
import time

import httpx
import streamlit as st

from consumer_agent import clear_inter_agent_log, run_consumer

PROVIDER_BASE_URL = "http://localhost:8001"


def _provider_running() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", 8001)) == 0


def _start_provider() -> None:
    if not _provider_running():
        subprocess.Popen(
            ["uv", "run", "uvicorn", "provider_server:app", "--port", "8001", "--log-level", "error"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)


_start_provider()


def render_content(content: str) -> None:
    if "<think>" in content and "</think>" in content:
        think = content.split("</think>")[0].replace("<think>", "").strip()
        answer = content.split("</think>", 1)[1].strip()
        with st.expander("🧠 Thinking..."):
            st.write(think)
        if answer:
            st.write(answer)
    else:
        st.write(content)


st.set_page_config(page_title="Bandwidth Agent Simulation", layout="wide")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "agent_log" not in st.session_state:
    st.session_state.agent_log = []

MODELS = ["qwen3:4b"]

with st.sidebar:
    st.header("⚙️ Settings")
    selected_model = st.selectbox("Ollama model", MODELS, index=0)
    st.caption(f"Pull with: `ollama pull {selected_model}`")

    status_icon = "🟢" if _provider_running() else "🔴"
    st.caption(f"{status_icon} Provider at {PROVIDER_BASE_URL}")

    st.divider()
    st.header("🔑 Gateway Check")
    token_input = st.text_input("Paste token to verify", placeholder="xxxxxxxx-xxxx-...")
    if st.button("Verify token") and token_input.strip():
        try:
            with httpx.Client() as client:
                resp = client.get(f"{PROVIDER_BASE_URL}/service", params={"token": token_input.strip()})
            if resp.status_code == 200:
                data = resp.json()
                st.success(
                    f"Active — {data['tier']} tier | {data['mbps']} Mbps | "
                    f"{data['remaining_min']} min remaining"
                )
            else:
                detail = resp.json().get("detail", resp.text)
                st.error(detail)
        except Exception as e:
            st.error(f"Could not reach provider: {e}")

left_col, right_col = st.columns(2)

with left_col:
    st.title("🛒 Consumer Agent")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            render_content(msg["content"])

    user_input = st.chat_input("Ask the consumer agent...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("Agents working..."):
            response, log_snapshot = run_consumer(user_input, model=selected_model)

        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.session_state.agent_log = log_snapshot
        st.rerun()

with right_col:
    st.title("📡 Provider")
    log_tab, catalog_tab = st.tabs(["Agent-to-Agent Log", "Catalog"])

    with log_tab:
        st.subheader("Consumer ↔ Provider HTTP calls")

        if not st.session_state.agent_log:
            st.info("No agent communication yet.")
        else:
            for entry in st.session_state.agent_log:
                if entry["from"] == "consumer":
                    with st.chat_message("consumer", avatar="🛒"):
                        st.write(entry["message"])
                elif entry["from"] == "provider_step":
                    if entry["role"] == "tool_call":
                        st.code(entry["content"], language="http")
                    else:
                        st.caption(f"↳ {entry['content']}")
                else:
                    with st.chat_message("provider", avatar="🏪"):
                        render_content(entry["message"])

        if st.button("🗑 Clear Log"):
            clear_inter_agent_log()
            st.session_state.agent_log = []
            st.rerun()

    with catalog_tab:
        st.subheader("Live Bandwidth Catalog")
        if st.button("Refresh"):
            st.rerun()
        try:
            with httpx.Client() as client:
                resp = client.get(f"{PROVIDER_BASE_URL}/catalog")
                resp.raise_for_status()
                catalog = resp.json()
            for tier in catalog:
                slots = tier["slots"]
                bar = "█" * slots + "░" * (10 - slots)
                st.markdown(
                    f"**{tier['tier'].capitalize()}** — "
                    f"{tier['mbps']} Mbps / {tier['duration_min']} min / "
                    f"`{tier['price_eth']} ETH`"
                )
                st.caption(f"Slots: [{bar}] {slots} remaining")
        except Exception as e:
            st.error(f"Could not reach provider: {e}")
