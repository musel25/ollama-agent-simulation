import streamlit as st
from consumer_agent import run_consumer, clear_inter_agent_log

st.set_page_config(page_title="Ollama Agent Simulation", layout="wide")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "agent_log" not in st.session_state:
    st.session_state.agent_log = []

MODELS = ["qwen3:4b", "qwen3:1.7b"]

with st.sidebar:
    st.header("⚙️ Settings")
    selected_model = st.selectbox("Ollama model", MODELS, index=0)
    st.caption(f"Pull with: `ollama pull {selected_model}`")

left_col, right_col = st.columns(2)

with left_col:
    st.title("🛒 Consumer Agent")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("Ask the consumer agent...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("Agents working..."):
            response, log_snapshot = run_consumer(user_input, model=selected_model)

        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.session_state.agent_log = log_snapshot
        st.rerun()

with right_col:
    st.title("📡 Agent-to-Agent Log")
    st.subheader("Provider ↔ Consumer Communication")

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
        clear_inter_agent_log()
        st.session_state.agent_log = []
        st.rerun()
