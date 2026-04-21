"""
Streamlit thin-client UI — port 8501.
All logic delegated to consumer/app.py over HTTP.
"""
import html as html_lib
import os
import re

import httpx
import streamlit as st
from web3 import Web3

CONSUMER_BASE_URL = os.environ.get("CONSUMER_BASE_URL", "http://localhost:8001")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
MODELS = list(dict.fromkeys([DEFAULT_MODEL, "qwen3:4b", "qwen3:1.7b"]))

STEP_ORDER = ["catalog", "quote", "onchain", "gateway"]
STEP_LABELS = {
    "catalog": "Catalog",
    "quote":   "Quote",
    "onchain": "On-chain TX",
    "gateway": "Gateway",
}
BUBBLE_STYLES = {
    # sender -> (label, bg, border, accent)
    "consumer": ("🛒 consumer agent", "#1a1a2e", "#2a2a4e", "#818cf8"),
    "provider": ("🏪 provider agent", "#1a2535", "#2a3545", "#60a5fa"),
    "chain":    ("⛓ blockchain",      "#1f1a0a", "#3a2a0a", "#f59e0b"),
    "gateway":  ("🌐 gateway",         "#1a2a1a", "#2a3a2a", "#34d399"),
}
PHASE_COLORS = {
    # status -> (border_color, bg_color, icon)
    "done":    ("#22c55e", "#14291a", "✓"),
    "active":  ("#3b82f6", "#1a2f4a", "●"),
    "pending": ("#555555", "#1a1a2a", "○"),
}


def _parse_log_to_phases(log: list[dict], turn: int) -> list[dict]:
    """Convert a flat inter-agent log into typed phase dicts."""
    phases: list[dict] = []

    for entry in log:
        sender = entry.get("from", "")
        msg = entry.get("message", "")
        if not sender or not msg:
            continue

        if sender == "consumer" and msg.startswith("GET /catalog"):
            phases.append({
                "step": "catalog", "status": "done", "turn": turn,
                "summary": "", "messages": [{"from": "consumer", "text": msg}],
            })

        elif sender == "provider" and "Mbps" in msg and phases and phases[-1]["step"] == "catalog":
            phases[-1]["messages"].append({"from": "provider", "text": msg})
            count = len([ln for ln in msg.split("\n") if ln.strip()])
            phases[-1]["summary"] = f"{count} tiers available"

        elif sender == "consumer" and "POST /quote" in msg:
            phases.append({
                "step": "quote", "status": "done", "turn": turn,
                "summary": "", "messages": [{"from": "consumer", "text": msg}],
            })

        elif sender == "provider" and "Quote received:" in msg:
            if phases and phases[-1]["step"] == "quote":
                phases[-1]["messages"].append({"from": "provider", "text": msg})
                m = re.search(r"price=([\d.]+ ETH)", msg)
                phases[-1]["summary"] = m.group(1) if m else "quoted"

        elif sender == "consumer" and "requestAgreement() sent." in msg:
            phases.append({
                "step": "onchain", "status": "done", "turn": turn,
                "summary": "ETH locked", "messages": [{"from": "chain", "text": msg}],
            })

        elif sender == "consumer" and "Agreement ACTIVE." in msg:
            if phases and phases[-1]["step"] == "onchain":
                phases[-1]["messages"].append({"from": "chain", "text": msg})

        elif sender == "provider" and "Gateway response:" in msg:
            phases.append({
                "step": "gateway", "status": "done", "turn": turn,
                "summary": "service active", "messages": [{"from": "gateway", "text": msg}],
            })

    return phases


def _merge_timeline(existing: list[dict], new_phases: list[dict]) -> list[dict]:
    """Append new phases, skipping any (step, turn) pair already present."""
    existing_keys = {(p["step"], p["turn"]) for p in existing}
    result = list(existing)
    for phase in new_phases:
        key = (phase["step"], phase["turn"])
        if key not in existing_keys:
            result.append(phase)
            existing_keys.add(key)
    return result


def _current_step(timeline: list[dict]) -> str:
    """Return the first step not yet completed, or the last step if all are done."""
    completed = {p["step"] for p in timeline if p["status"] == "done"}
    for step in STEP_ORDER:
        if step not in completed:
            return step
    return STEP_ORDER[-1]


def _active_tier_from_timeline(timeline: list[dict]) -> str | None:
    """Extract the purchased tier name from the quote phase consumer message."""
    for phase in timeline:
        if phase["step"] == "quote":
            for msg in phase["messages"]:
                if msg["from"] == "consumer":
                    m = re.search(r"package_id=(\w+)", msg["text"])
                    if m:
                        return m.group(1)
    return None


def render_content(content: str, thinking: list[str] | None = None, log: list[dict] | None = None) -> None:
    thoughts = list(thinking or [])
    if content:
        st.write(content)

    if thoughts:
        with st.expander("Thinking", expanded=False):
            for item in thoughts:
                st.write(item)

    if log:
        provider_entries = [entry for entry in log if entry.get("from") == "provider"]
        if provider_entries:
            with st.expander("Provider output", expanded=True):
                for entry in provider_entries:
                    st.write(entry["message"])


st.set_page_config(page_title="Bandwidth Agent Simulation", layout="wide")

UI_STATE_VERSION = 2
if st.session_state.get("ui_state_version") != UI_STATE_VERSION:
    st.session_state.ui_state_version = UI_STATE_VERSION
    st.session_state.chat_history = []
    st.session_state.agent_log = []

with st.sidebar:
    st.header("⚙️ Settings")
    selected_model = st.selectbox("Ollama model", MODELS, index=MODELS.index(DEFAULT_MODEL))
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
            render_content(msg["content"], msg.get("thinking"), msg.get("log"))

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
                thinking_snapshot = data.get("thinking", [])
            except Exception as e:
                response_text = f"Error reaching consumer agent: {e}"
                log_snapshot = []
                thinking_snapshot = []
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": response_text,
            "thinking": thinking_snapshot,
            "log": log_snapshot,
        })
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
