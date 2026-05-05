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

CONSUMER_TOOLS = [
    ("browse_catalog",     "a2a",      False),
    ("request_quote",      "a2a",      False),
    ("lock_payment",       "on-chain", False),
    ("await_settlement",   "on-chain", False),
    ("present_credential", "a2a",      False),
    ("wallet_address",     "local",    True),   # ambient
    ("sign_message",       "local",    True),   # ambient
]

PROVIDER_TOOLS = [
    ("get_catalog",                "read",     False),
    ("request_quote",              "read",     False),
    ("verify_credential_ownership","read",     False),
    ("mint_credential",            "on-chain", False),
    ("complete_swap",              "on-chain", False),
    ("allocate_bandwidth",         "sdn",      False),
    ("verify_bandwidth",           "sdn",      False),
    ("revoke_bandwidth",           "expiry",   True),  # ambient
]


_MCP_RE = re.compile(r"\[MCP\]\s+(\w+)\(")


def _parse_consumer_tools_from_log(log: list[dict], turn: int) -> list[dict]:
    """Extract [MCP] tool_name(...) markers from a /chat log and tag each
    with the turn it fired in. Used by ingest_chat_response."""
    out = []
    for entry in log:
        if entry.get("from") != "consumer":
            continue
        m = _MCP_RE.search(entry.get("message", ""))
        if m:
            out.append({"tool": m.group(1), "turn": turn})
    return out


def _merge_tool_log(existing: list[dict], new_entries: list[dict]) -> list[dict]:
    """De-duplicate by (tool, turn). Older turns kept; newer turns append."""
    seen = {(e["tool"], e["turn"]) for e in existing}
    out = list(existing)
    for e in new_entries:
        key = (e["tool"], e["turn"])
        if key not in seen:
            out.append(e)
            seen.add(key)
    return out


def _tool_status(tool_log: list[dict], tool_name: str, current_turn: int) -> str:
    """Return 'fired_this_turn' / 'fired_previously' / 'not_yet_fired'."""
    turns = [e["turn"] for e in tool_log if e["tool"] == tool_name]
    if not turns:
        return "not_yet_fired"
    if max(turns) >= current_turn:
        return "fired_this_turn"
    return "fired_previously"


@st.cache_data(ttl=10)
def _fetch_address(base_url: str) -> str | None:
    try:
        with httpx.Client(timeout=3.0) as c:
            r = c.get(f"{base_url}/address")
            r.raise_for_status()
            return r.json()["address"]
    except Exception:
        return None


def _render_tool_row(name: str, tag: str, ambient: bool, status: str) -> str:
    if ambient:
        border = "1px dashed #2a2a3e"; nm_color = "#666"; tag_color = "#444"; mark = ""
    elif status == "fired_this_turn":
        border = "1px solid #3b82f6"; nm_color = "#93c5fd"; tag_color = "#3b82f6"; mark = " ✓"
    elif status == "fired_previously":
        border = "1px solid #22c55e44"; nm_color = "#7fc99a"; tag_color = "#22c55e88"; mark = " ✓"
    else:
        border = "1px solid #232333"; nm_color = "#bbb"; tag_color = "#666"; mark = ""
    return (
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'font-family:ui-monospace,monospace;font-size:10px;padding:4px 8px;'
        f'border-radius:5px;background:#15151f;border:{border};margin-bottom:3px;">'
        f'<span style="color:{nm_color};">{html_lib.escape(name)}{mark}</span>'
        f'<span style="font-size:8px;color:{tag_color};">{html_lib.escape(tag)}</span></div>'
    )


def render_consumer_panel() -> None:
    addr = _fetch_address(CONSUMER_BASE_URL) or "—"
    addr_short = (addr[:6] + "…" + addr[-4:]) if addr != "—" else "—"
    turn = st.session_state.turn

    tool_rows = "".join(
        _render_tool_row(name, tag, ambient,
                         _tool_status(st.session_state.consumer_tool_log, name, turn))
        for name, tag, ambient in CONSUMER_TOOLS
    )

    st.markdown(f'''
      <div class="panel agent-panel">
        <div class="panel-title">
          <span>🛒 Consumer Agent</span>
          <span class="meta">v2.0.0</span>
        </div>
        <div style="font-size:13px;font-weight:600;color:#f0f0f8;">Bandwidth Consumer Agent</div>
        <div style="font-size:10px;color:var(--text-dim);line-height:1.4;margin:2px 0 10px;">
          Autonomously procures time-bound bandwidth from provider agents via atomic
          on-chain escrow + ERC-721 credential.
        </div>
        <div style="font-size:10px;color:#aaa;display:flex;justify-content:space-between;
                    padding:3px 0;border-top:1px dashed var(--border);">
          <span style="color:#666;text-transform:uppercase;font-size:9px;">wallet</span>
          <span style="font-family:ui-monospace,monospace;">{addr_short}</span></div>
        <div style="font-size:10px;color:#aaa;display:flex;justify-content:space-between;
                    padding:3px 0;border-top:1px dashed var(--border);">
          <span style="color:#666;text-transform:uppercase;font-size:9px;">A2A endpoint</span>
          <span>:8001/chat</span></div>
        <div style="font-size:10px;color:#aaa;display:flex;justify-content:space-between;
                    padding:3px 0;border-top:1px dashed var(--border);">
          <span style="color:#666;text-transform:uppercase;font-size:9px;">model</span>
          <span>{html_lib.escape(selected_model)}</span></div>

        <div class="label">A2A Skills</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;">
          <span style="background:#1a1a2e;border:1px solid #818cf855;color:#cfd6ff;
                       font-size:10px;padding:2px 8px;border-radius:99px;">purchase_bandwidth</span>
        </div>

        <div class="label">MCP Tools</div>
        {tool_rows}
      </div>
    ''', unsafe_allow_html=True)


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

col_l, col_c, col_r = st.columns([1, 1.2, 1])
with col_l:
    render_consumer_panel()
with col_c:
    st.markdown('<div class="panel wire-panel"><div class="panel-title">A2A Wire</div>'
                '<div style="color:var(--text-faint);font-size:11px;">— wired in next task —</div></div>',
                unsafe_allow_html=True)
with col_r:
    st.markdown('<div class="panel provider-panel"><div class="panel-title">Provider Agent</div>'
                '<div style="color:var(--text-faint);font-size:11px;">— wired in next task —</div></div>',
                unsafe_allow_html=True)
