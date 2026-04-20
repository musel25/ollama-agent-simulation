"""
Streamlit thin-client UI — port 8501.
All logic delegated to consumer/app.py over HTTP.
"""
import httpx
import streamlit as st

CONSUMER_BASE_URL = "http://localhost:8001"
MODELS = ["qwen3:4b", "qwen3:1.7b"]


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

with st.sidebar:
    st.header("⚙️ Settings")
    selected_model = st.selectbox("Ollama model", MODELS, index=0)
    st.caption(f"Pull with: `ollama pull {selected_model}`")

    st.divider()
    st.header("🔑 Gateway Check")
    token_input = st.text_input("Token ID (integer)", placeholder="0")
    if st.button("Verify token") and token_input.strip():
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{CONSUMER_BASE_URL}/check_token",
                    params={"tokenId": token_input.strip()},
                )
            if resp.status_code == 200:
                data = resp.json()
                st.success(
                    f"Active — {data['bandwidth_mbps']} Mbps | "
                    f"{data['seconds_remaining']}s remaining"
                )
            else:
                detail = resp.json().get("detail", resp.text)
                st.error(detail)
        except Exception as e:
            st.error(f"Could not reach consumer agent: {e}")

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
            try:
                with httpx.Client(timeout=300.0) as client:
                    resp = client.post(
                        f"{CONSUMER_BASE_URL}/chat",
                        json={"message": user_input, "model": selected_model},
                    )
                    resp.raise_for_status()
                data = resp.json()
                response_text = data["response"]
                log_snapshot = data["log"]
            except Exception as e:
                response_text = f"Error reaching consumer agent: {e}"
                log_snapshot = []
        st.session_state.chat_history.append({"role": "assistant", "content": response_text})
        st.session_state.agent_log = log_snapshot
        st.rerun()

with right_col:
    st.title("📡 Provider")
    log_tab, catalog_tab = st.tabs(["Agent-to-Agent Log", "Catalog"])

    with log_tab:
        st.subheader("Consumer ↔ Provider interactions")
        if not st.session_state.agent_log:
            st.info("No agent communication yet.")
        else:
            for entry in st.session_state.agent_log:
                if entry["from"] == "consumer":
                    with st.chat_message("consumer", avatar="🛒"):
                        st.write(entry["message"])
                else:
                    with st.chat_message("provider", avatar="🏪"):
                        st.write(entry["message"])
        if st.button("🗑 Clear Log"):
            try:
                with httpx.Client() as client:
                    client.delete(f"{CONSUMER_BASE_URL}/log")
            except Exception:
                pass
            st.session_state.agent_log = []
            st.rerun()

    with catalog_tab:
        st.subheader("Live Bandwidth Catalog")
        if st.button("Refresh"):
            st.rerun()
        try:
            with httpx.Client() as client:
                resp = client.get(f"{CONSUMER_BASE_URL}/catalog_proxy")
                resp.raise_for_status()
            catalog = resp.json()
            for pkg in catalog:
                from web3 import Web3
                price_eth = float(Web3.from_wei(pkg["priceWei"], "ether"))
                available = pkg.get("availableSlots", "?")
                bar_filled = min(available, 10) if isinstance(available, int) else 0
                bar = "█" * bar_filled + "░" * (10 - bar_filled)
                st.markdown(
                    f"**{pkg['packageId'].capitalize()}** — "
                    f"{pkg['mbps']} Mbps / {pkg['durationSeconds']}s / "
                    f"`{price_eth} ETH`"
                )
                st.caption(f"Slots: [{bar}] {available} available")
        except Exception as e:
            st.error(f"Could not reach consumer agent: {e}")
