"""
Streamlit dashboard — port 8501.

Two-agent symmetric layout: consumer panel | A2A wire | provider panel.
Pulls cumulative state from /chat, /tool_log, /chain_events into
st.session_state so it survives inter_agent_log.clear() on each turn.
"""
from __future__ import annotations

import html as html_lib
import json
import os
import re
import time

import httpx
import streamlit as st
from web3 import Web3

CONSUMER_BASE_URL = os.environ.get("CONSUMER_BASE_URL", "http://localhost:8001")
PROVIDER_BASE_URL = os.environ.get("PROVIDER_BASE_URL", "http://localhost:8002")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
MODELS = list(dict.fromkeys([DEFAULT_MODEL, "qwen3:4b", "qwen3:1.7b"]))
SDN_MOCK = os.environ.get("SDN_MOCK", "true").lower() == "true"

# ── Streamlit page setup ───────────────────────────────────────────────────
st.set_page_config(page_title="A2A Bandwidth Provisioning", layout="wide")

st.markdown("""
<style>
  :root {
    --bg-page: #0d0d12;
    --bg-panel: #13131c;
    --bg-deep: #0e0e16;
    --border: #2a2a3e;
    --border-soft: #1f1f2a;
    --text: #d8d8e0;
    --text-dim: #8a8a9a;
    --text-faint: #555;
    --accent-consumer: #818cf8;
    --accent-provider: #60a5fa;
    --accent-wire: #34d399;
    --accent-chain: #f59e0b;
    --accent-success: #22c55e;
    --accent-active: #3b82f6;
  }
  section[data-testid="stSidebar"] { width: 240px !important; min-width: 240px !important; }
  .block-container { padding-top: 1.6rem !important; padding-bottom: 1rem !important; max-width: 1600px; }
  .stApp { background: var(--bg-page); }

  .panel { background: var(--bg-panel); border: 1px solid var(--border);
           border-radius: 10px; padding: 12px 14px; margin-bottom: 12px; }
  .panel-title { font-size: 11px; font-weight: 600; letter-spacing: 0.6px;
                 text-transform: uppercase; color: #cfd6ff;
                 display:flex; justify-content:space-between; align-items:center;
                 margin-bottom: 8px; }
  .panel-title .meta { font-size: 9px; color: var(--text-faint); font-weight: 400;
                       letter-spacing: 0.2px; text-transform: none; }

  .agent-panel { border-left: 3px solid var(--accent-consumer); }
  .provider-panel { border-left: 3px solid var(--accent-provider); }
  .wire-panel { border-left: 3px solid var(--accent-wire); }
  .chain-panel { border-left: 3px solid var(--accent-chain); }

  .label { font-size: 9px; color: var(--text-faint); letter-spacing: 0.6px;
           text-transform: uppercase; margin: 10px 0 4px; }
</style>
""", unsafe_allow_html=True)

# ── session_state init ─────────────────────────────────────────────────────
UI_STATE_VERSION = 4
if st.session_state.get("ui_state_version") != UI_STATE_VERSION:
    st.session_state.ui_state_version = UI_STATE_VERSION
    st.session_state.chat_history = []
    st.session_state.timeline = []           # phases for the A2A wire
    st.session_state.consumer_tool_log = []  # parsed [MCP] markers from /chat log, dedup'd
    st.session_state.provider_tool_log = []  # entries from provider /tool_log
    st.session_state.chain_events = []       # entries from consumer /chain_events
    st.session_state.probe_samples = []
    st.session_state.turn = 0
    st.session_state.running = False
    st.session_state.last_block_seen = 0
    st.session_state.last_provider_ts_seen = 0.0

# ── sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    selected_model = st.selectbox("Ollama model", MODELS, index=MODELS.index(DEFAULT_MODEL))
    st.caption(f"Pull with: `ollama pull {selected_model}`")
    st.divider()
    if st.button("🗑 Clear session"):
        try:
            with httpx.Client() as c:
                c.delete(f"{CONSUMER_BASE_URL}/log")
        except Exception:
            pass
        for k in ("chat_history", "timeline", "consumer_tool_log",
                  "provider_tool_log", "chain_events", "probe_samples"):
            st.session_state[k] = []
        st.session_state.turn = 0
        st.session_state.last_block_seen = 0
        st.session_state.last_provider_ts_seen = time.time()
        st.rerun()

STAGES = [
    ("01", "Discovery",     "🔍", "browse_catalog"),
    ("02", "Quote",         "💬", "request_quote"),
    ("03", "Payment Lock",  "🔒", "lock_payment"),
    ("04", "Atomic Swap",   "⚡", "await_settlement"),
    ("05", "Activation",    "🪪", "present_credential"),
    ("06", "Consumption",   "📡", "verify_bandwidth"),
]


def _consumer_tool_fired(name: str) -> bool:
    return any(e["tool"] == name for e in st.session_state.consumer_tool_log)


def _provider_tool_fired(name: str) -> bool:
    return any(e["tool"] == name for e in st.session_state.provider_tool_log)


def _stage_status(trigger: str) -> str:
    # Stage 06 fires only if iperf was run; treat probe_samples as the trigger.
    if trigger == "verify_bandwidth":
        return "done" if st.session_state.probe_samples else "pending"
    if _consumer_tool_fired(trigger) or _provider_tool_fired(trigger):
        return "done"
    return "pending"


def render_header() -> None:
    turn = st.session_state.turn
    if st.session_state.running:
        status = f"BUSY · turn {turn}"
        color = "#3b82f6"
        bg = "#1a2f4a"
    elif turn > 0:
        status = f"READY · turn {turn}"
        color = "#22c55e"
        bg = "#14291a"
    else:
        status = "IDLE"
        color = "#666"
        bg = "#15151f"

    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
        f'padding-bottom:14px;border-bottom:1px solid var(--border);margin-bottom:14px;">'
        f'<div><div style="font-size:18px;font-weight:600;color:#f0f0f8;">'
        f'A2A Bandwidth Provisioning — autonomous agent demo</div>'
        f'<div style="font-size:11px;color:var(--text-dim);margin-top:3px;">'
        f'Orange Labs · MCP-driven consumer & provider · atomic on-chain swap · '
        f'SDN ({"mock" if SDN_MOCK else "real"})</div></div>'
        f'<div style="background:{bg};border:1px solid {color}55;color:{color};'
        f'font-size:10px;padding:4px 10px;border-radius:99px;font-weight:600;'
        f'letter-spacing:0.4px;">● {status}</div></div>',
        unsafe_allow_html=True,
    )


def render_pipeline() -> None:
    tiles = []
    for num, label, icon, trigger in STAGES:
        status = _stage_status(trigger)
        if status == "done":
            border = "#22c55e88"; bg = "#14291a44"; lcolor = "#22c55e"
        else:
            border = "var(--border)"; bg = "#15151f"; lcolor = "#bbb"
        tiles.append(
            f'<div style="background:{bg};border:1px solid {border};border-radius:8px;'
            f'padding:10px 8px;text-align:center;">'
            f'<div style="font-size:9px;color:#555;letter-spacing:1px;">{num}</div>'
            f'<div style="font-size:18px;margin:4px 0;">{icon}</div>'
            f'<div style="font-size:10px;font-weight:500;color:{lcolor};">{label}</div></div>'
        )
    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px;'
        'margin-bottom:16px;">' + "".join(tiles) + "</div>",
        unsafe_allow_html=True,
    )


# ── body ───────────────────────────────────────────────────────────────────
render_header()
render_pipeline()
