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
    """Extract the most recently purchased tier name from the quote phase consumer messages."""
    result = None
    for phase in timeline:
        if phase["step"] == "quote":
            for msg in phase["messages"]:
                if msg["from"] == "consumer":
                    m = re.search(r"package_id=(\w+)", msg["text"])
                    if m:
                        result = m.group(1)
    return result


def render_stepper(timeline: list[dict]) -> None:
    completed = {p["step"] for p in timeline if p["status"] == "done"}
    active = _current_step(timeline)
    pills = []
    for step_id in STEP_ORDER:
        label = STEP_LABELS[step_id]
        if step_id in completed:
            pills.append(
                f'<span style="background:#14291a;border:1px solid #22c55e;border-radius:12px;'
                f'padding:3px 12px;font-size:11px;font-weight:500;color:#22c55e;">✓ {label}</span>'
            )
        elif step_id == active:
            pills.append(
                f'<span style="background:#1a2f4a;border:1px solid #3b82f6;border-radius:12px;'
                f'padding:3px 12px;font-size:11px;font-weight:500;color:#3b82f6;">● {label}</span>'
            )
        else:
            pills.append(
                f'<span style="background:#1a1a2a;border:1px solid #333;border-radius:12px;'
                f'padding:3px 12px;font-size:11px;font-weight:500;color:#555;">○ {label}</span>'
            )
    arrow = '<span style="color:#444;margin:0 6px;">›</span>'
    st.markdown(
        '<div style="padding:6px 0;display:flex;align-items:center;flex-wrap:wrap;gap:4px;">'
        + arrow.join(pills) + "</div>",
        unsafe_allow_html=True,
    )


def render_phase(phase: dict) -> None:
    status = phase["status"]
    color, bg, icon = PHASE_COLORS.get(status, PHASE_COLORS["pending"])
    label = STEP_LABELS[phase["step"]]
    summary = phase.get("summary", "")
    turn = phase.get("turn", "")

    turn_html = (
        f'<span style="font-size:10px;color:#444;margin-left:8px;">turn {turn}</span>'
        if turn else ""
    )
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
        f'<div style="width:16px;height:16px;border-radius:50%;border:2px solid {color};'
        f'background:{bg};display:flex;align-items:center;justify-content:center;'
        f'font-size:8px;color:{color};flex-shrink:0;">{icon}</div>'
        f'<span style="font-size:13px;font-weight:600;color:{color};">{label}</span>'
        f'<span style="font-size:9px;border-radius:4px;padding:1px 7px;'
        f'background:{bg};color:{color};border:1px solid {color}44;">{status.upper()}</span>'
        f'{turn_html}</div>',
        unsafe_allow_html=True,
    )

    if phase["messages"]:
        bubbles = ""
        for msg in phase["messages"]:
            sender = msg["from"]
            text = html_lib.escape(msg["text"]).replace("\n", "<br>")
            slabel, b_bg, b_border, accent = BUBBLE_STYLES.get(sender, BUBBLE_STYLES["provider"])
            bubbles += (
                f'<div style="background:{b_bg};border:1px solid {b_border};'
                f'border-left:3px solid {accent};border-radius:6px;'
                f'padding:8px 12px;margin-bottom:6px;font-size:12px;">'
                f'<div style="font-size:9px;color:{accent};text-transform:uppercase;'
                f'letter-spacing:0.4px;margin-bottom:4px;">{slabel}</div>'
                f'<div style="color:#ccc;white-space:pre-wrap;">{text}</div></div>'
            )
        st.markdown(
            f'<div style="border-left:2px solid {color}44;padding-left:12px;'
            f'margin-left:8px;margin-bottom:4px;">{bubbles}</div>',
            unsafe_allow_html=True,
        )

    if summary:
        st.caption(f"↳ {summary}")
    st.divider()


def render_catalog(active_tier: str | None = None) -> None:
    try:
        with httpx.Client() as client:
            resp = client.get(f"{CONSUMER_BASE_URL}/catalog_proxy")
            resp.raise_for_status()
        catalog = resp.json()
    except Exception as e:
        st.error(f"Could not load catalog: {e}")
        return

    if not catalog:
        st.info("No packages available.")
        return
    cols = st.columns(len(catalog))
    for col, pkg in zip(cols, catalog):
        price_eth = float(Web3.from_wei(pkg["priceWei"], "ether"))
        available = pkg.get("availableSlots", 0)
        tier = pkg["packageId"]
        is_selected = tier == active_tier
        border = "#22c55e" if is_selected else "#2a2a3e"
        bg = "#14291a22" if is_selected else "#1a1a2a"
        tick = " ✓" if is_selected else ""
        bar_w = min(available, 10) * 10
        with col:
            st.markdown(
                f'<div style="border:1px solid {border};border-radius:8px;'
                f'padding:8px 10px;background:{bg};">'
                f'<div style="font-size:12px;font-weight:600;color:#ddd;">{html_lib.escape(str(tier))}{tick}</div>'
                f'<div style="font-size:10px;color:#666;margin:3px 0;">'
                f'{html_lib.escape(str(pkg["mbps"]))} Mbps · {html_lib.escape(str(pkg["durationSeconds"]))}s · {price_eth} ETH</div>'
                f'<div style="height:3px;background:#2a2a3e;border-radius:2px;overflow:hidden;">'
                f'<div style="width:{bar_w}%;height:100%;background:#22c55e;'
                f'border-radius:2px;"></div></div>'
                f'<div style="font-size:9px;color:#555;margin-top:3px;">{available} slots</div>'
                f"</div>",
                unsafe_allow_html=True,
            )


# ── Streamlit app ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Bandwidth Agent Simulation", layout="wide")

UI_STATE_VERSION = 3
if st.session_state.get("ui_state_version") != UI_STATE_VERSION:
    st.session_state.ui_state_version = UI_STATE_VERSION
    st.session_state.chat_history = []
    st.session_state.timeline = []
    st.session_state.turn = 0

# Sidebar
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
                st.error(resp.json().get("detail", resp.text))
        except Exception as e:
            st.error(f"Could not reach consumer agent: {e}")

# Stepper bar (full width above columns)
render_stepper(st.session_state.timeline)
st.divider()

left_col, right_col = st.columns([38, 62])

# ── Left: Human chat ───────────────────────────────────────────────────────────
with left_col:
    st.title("🧑 Human")
    st.caption("Human picks the package — agents execute the rest autonomously.")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg.get("thinking"):
                with st.expander("Thinking", expanded=False):
                    for t in msg["thinking"]:
                        st.write(t)

    user_input = st.chat_input("Ask the consumer agent...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.session_state.turn += 1
        turn = st.session_state.turn

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

        new_phases = _parse_log_to_phases(log_snapshot, turn)
        st.session_state.timeline = _merge_timeline(
            st.session_state.timeline, new_phases
        )
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": response_text,
            "thinking": thinking_snapshot,
        })
        st.rerun()

# ── Right: A2A transcript ──────────────────────────────────────────────────────
with right_col:
    st.title("🤖↔🤖 Agent-to-Agent Transcript")

    timeline = st.session_state.timeline
    active_tier = _active_tier_from_timeline(timeline)
    completed_steps = {p["step"] for p in timeline if p["status"] == "done"}

    if not timeline:
        st.info("No agent communication yet. Ask the consumer agent something.")
    else:
        # Render all accumulated phases in order (cumulative across turns)
        for phase in timeline:
            render_phase(phase)
        # Show pending placeholders for steps not yet started
        for step in STEP_ORDER:
            if step not in completed_steps:
                color, bg, icon = PHASE_COLORS["pending"]
                label = STEP_LABELS[step]
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;'
                    f'margin-bottom:12px;opacity:0.35;">'
                    f'<div style="width:16px;height:16px;border-radius:50%;'
                    f'border:2px solid {color};background:{bg};font-size:8px;'
                    f'color:{color};display:flex;align-items:center;'
                    f'justify-content:center;">{icon}</div>'
                    f'<span style="font-size:13px;color:{color};">{label}</span>'
                    f'<span style="font-size:10px;color:#444;">pending</span></div>',
                    unsafe_allow_html=True,
                )

    st.divider()
    hdr, btn_col = st.columns([5, 1])
    with hdr:
        st.caption("Live Bandwidth Catalog")
    with btn_col:
        if st.button("↻"):
            st.rerun()
    render_catalog(active_tier)

    st.divider()
    if st.button("🗑 Clear session"):
        try:
            with httpx.Client() as client:
                client.delete(f"{CONSUMER_BASE_URL}/log")
        except Exception:
            pass
        st.session_state.timeline = []
        st.session_state.chat_history = []
        st.session_state.turn = 0
        st.rerun()
