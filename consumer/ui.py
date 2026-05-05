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


def _parse_timeline(log: list[dict], turn: int) -> list[dict]:
    """Convert /chat log entries into A2A wire bubbles + on-chain markers.

    Returns a list of {kind, sender, text, turn} where:
      kind = 'bubble' or 'chain'
      sender = 'consumer' or 'provider' (only meaningful for bubbles)
    """
    out: list[dict] = []
    for e in log:
        sender = e.get("from", "")
        msg = e.get("message", "")
        if not sender or not msg:
            continue
        if msg.startswith("requestAgreement()"):
            out.append({"kind": "chain", "text": "⛓ requestAgreement on chain", "turn": turn})
        elif "Agreement ACTIVE" in msg:
            out.append({"kind": "chain", "text": f"⛓ {msg}", "turn": turn})
        elif sender in ("consumer", "provider"):
            out.append({"kind": "bubble", "sender": sender, "text": msg, "turn": turn})
    return out


def _merge_timeline(existing: list[dict], new_items: list[dict]) -> list[dict]:
    seen = {(i["kind"], i.get("sender", ""), i["text"], i["turn"]) for i in existing}
    out = list(existing)
    for i in new_items:
        key = (i["kind"], i.get("sender", ""), i["text"], i["turn"])
        if key not in seen:
            out.append(i)
            seen.add(key)
    return out


def render_wire_panel() -> None:
    bubbles_html = []
    for item in st.session_state.timeline:
        if item["kind"] == "chain":
            bubbles_html.append(
                f'<div style="text-align:center;color:#f59e0b;font-size:10px;'
                f'padding:6px 0;letter-spacing:0.3px;">{html_lib.escape(item["text"])}</div>'
            )
            continue
        sender = item["sender"]
        text = html_lib.escape(item["text"])
        if sender == "consumer":
            bubbles_html.append(
                f'<div style="align-self:flex-start;background:#1a1a2e;'
                f'border:1px solid #2a2a4e;border-left:3px solid #818cf8;'
                f'border-radius:8px;padding:6px 9px;font-size:10px;color:#d4d8ff;'
                f'max-width:88%;font-family:ui-monospace,monospace;line-height:1.4;'
                f'word-break:break-word;">'
                f'<div style="font-size:8px;letter-spacing:0.4px;text-transform:uppercase;'
                f'opacity:0.7;margin-bottom:2px;">consumer →</div>{text}</div>'
            )
        else:
            bubbles_html.append(
                f'<div style="align-self:flex-end;background:#1a2535;'
                f'border:1px solid #2a3545;border-right:3px solid #60a5fa;'
                f'border-radius:8px;padding:6px 9px;font-size:10px;color:#d4e4ff;'
                f'max-width:88%;font-family:ui-monospace,monospace;line-height:1.4;'
                f'text-align:right;word-break:break-word;">'
                f'<div style="font-size:8px;letter-spacing:0.4px;text-transform:uppercase;'
                f'opacity:0.7;margin-bottom:2px;">← provider</div>{text}</div>'
            )

    bubbles_count = sum(1 for i in st.session_state.timeline if i["kind"] == "bubble")
    body = ("".join(bubbles_html)
            if st.session_state.timeline
            else '<div style="color:var(--text-faint);font-size:11px;">No agent-to-agent traffic yet — type intent into the chat below.</div>')

    st.markdown(f'''
      <div class="panel wire-panel">
        <div class="panel-title">
          <span>↔ Agent-to-Agent Wire</span>
          <span class="meta">JSON-RPC over HTTP · {bubbles_count} msgs</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px;max-height:520px;overflow-y:auto;">
          {body}
        </div>
      </div>
    ''', unsafe_allow_html=True)


def ingest_chat_response(turn: int, log: list[dict]) -> None:
    """Merge /chat log + poll provider /tool_log + poll consumer
    /chain_events. Uses last_provider_ts_seen and last_block_seen as
    watermarks so prior-turn entries aren't re-counted."""
    st.session_state.timeline = _merge_timeline(
        st.session_state.timeline, _parse_timeline(log, turn)
    )
    st.session_state.consumer_tool_log = _merge_tool_log(
        st.session_state.consumer_tool_log,
        _parse_consumer_tools_from_log(log, turn),
    )

    since_ts = st.session_state.last_provider_ts_seen
    try:
        with httpx.Client(timeout=5.0) as c:
            r = c.get(f"{PROVIDER_BASE_URL}/tool_log",
                      params={"since_ts": since_ts})
            r.raise_for_status()
            entries = [e for e in r.json() if e.get("status") == "ok"]
    except Exception:
        entries = []
    st.session_state.provider_tool_log = _merge_tool_log(
        st.session_state.provider_tool_log,
        [{"tool": e["tool"], "turn": turn} for e in entries],
    )
    if entries:
        st.session_state.last_provider_ts_seen = max(e["ts"] for e in entries)

    since_block = st.session_state.last_block_seen
    try:
        with httpx.Client(timeout=5.0) as c:
            r = c.get(f"{CONSUMER_BASE_URL}/chain_events",
                      params={"since_block": since_block})
            r.raise_for_status()
            new_events = r.json()
    except Exception:
        new_events = []
    if new_events:
        st.session_state.chain_events.extend(new_events)
        st.session_state.last_block_seen = max(e["block"] for e in new_events)


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


def render_provider_panel() -> None:
    addr = _fetch_address(PROVIDER_BASE_URL) or "—"
    addr_short = (addr[:6] + "…" + addr[-4:]) if addr != "—" else "—"
    turn = st.session_state.turn

    tool_rows = "".join(
        _render_tool_row(name, tag, ambient,
                         _tool_status(st.session_state.provider_tool_log, name, turn))
        for name, tag, ambient in PROVIDER_TOOLS
    )

    skills_html = "".join(
        f'<span style="background:#1a2535;border:1px solid #60a5fa55;color:#d4e4ff;'
        f'font-size:10px;padding:2px 8px;border-radius:99px;">{s}</span>'
        for s in ("get_catalog", "request_quote", "activate")
    )

    st.markdown(f'''
      <div class="panel provider-panel">
        <div class="panel-title">
          <span>🏪 Provider Agent</span>
          <span class="meta">v2.0.0</span>
        </div>
        <div style="font-size:13px;font-weight:600;color:#f0f0f8;">Bandwidth Provider Agent</div>
        <div style="font-size:10px;color:var(--text-dim);line-height:1.4;margin:2px 0 10px;">
          Sells time-bound bandwidth via atomic on-chain escrow + ERC-721 credential.
          Activates SDN policy on credential presentation.
        </div>
        <div style="font-size:10px;color:#aaa;display:flex;justify-content:space-between;
                    padding:3px 0;border-top:1px dashed var(--border);">
          <span style="color:#666;text-transform:uppercase;font-size:9px;">wallet</span>
          <span style="font-family:ui-monospace,monospace;">{addr_short}</span></div>
        <div style="font-size:10px;color:#aaa;display:flex;justify-content:space-between;
                    padding:3px 0;border-top:1px dashed var(--border);">
          <span style="color:#666;text-transform:uppercase;font-size:9px;">A2A endpoint</span>
          <span>:8002/a2a</span></div>
        <div style="font-size:10px;color:#aaa;display:flex;justify-content:space-between;
                    padding:3px 0;border-top:1px dashed var(--border);">
          <span style="color:#666;text-transform:uppercase;font-size:9px;">SDN</span>
          <span>{"mock" if SDN_MOCK else "real"}</span></div>

        <div class="label">A2A Skills</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;">{skills_html}</div>

        <div class="label">MCP Tools</div>
        {tool_rows}
      </div>
    ''', unsafe_allow_html=True)


def render_chat_panel() -> None:
    st.markdown('<div class="panel agent-panel"><div class="panel-title">'
                '<span>👤 Human → Consumer</span>'
                '<span class="meta">intent · reasoning trace</span></div>',
                unsafe_allow_html=True)
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg.get("thinking"):
                with st.expander("Thinking", expanded=False):
                    for t in msg["thinking"]:
                        st.write(t)
    st.markdown('</div>', unsafe_allow_html=True)


def render_chain_panel() -> None:
    events = st.session_state.chain_events
    if not events:
        rows_html = ('<div style="color:var(--text-faint);font-size:11px;'
                     'padding:6px 0;">No on-chain events yet.</div>')
    else:
        rows = []
        for e in events:
            args_str = ", ".join(f"{k}={v}" for k, v in (e.get("args") or {}).items())
            if len(args_str) > 60:
                args_str = args_str[:57] + "..."
            rows.append(
                f'<div style="font-family:ui-monospace,monospace;font-size:10px;'
                f'color:#bbb;padding:5px 8px;border-bottom:1px solid var(--border-soft);">'
                f'<span style="color:#f59e0b;">{html_lib.escape(e["event"])}</span> '
                f'<span style="color:#888;">{html_lib.escape(args_str)}</span>'
                f'<span style="color:#666;float:right;">block {e["block"]} · gas {e["gas"]:,}</span>'
                f'</div>'
            )
        rows_html = "".join(rows)

    st.markdown(f'''
      <div class="panel chain-panel">
        <div class="panel-title">
          <span>⛓ On-chain Events</span>
          <span class="meta">Anvil · {len(events)} events</span>
        </div>
        {rows_html}
      </div>
    ''', unsafe_allow_html=True)


def _active_token_id() -> int | None:
    """Find the most recent tokenId mentioned in the timeline."""
    for item in reversed(st.session_state.timeline):
        if item["kind"] == "chain" and "tokenId=" in item["text"]:
            m = re.search(r"tokenId=(\d+)", item["text"])
            if m:
                return int(m.group(1))
    return None


def render_nft_strip() -> None:
    tid = _active_token_id()
    if tid is None:
        st.markdown(
            '<div style="background:#0f1410;border:1px solid #22c55e22;border-radius:8px;'
            'padding:10px 14px;font-size:11px;color:var(--text-faint);margin-bottom:12px;">'
            '🪪 NFT credential — no active credential yet</div>',
            unsafe_allow_html=True,
        )
        return

    try:
        with httpx.Client(timeout=5.0) as c:
            r = c.get(f"{CONSUMER_BASE_URL}/check_token", params={"tokenId": tid})
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        st.markdown(
            f'<div style="color:#f87171;font-size:11px;">NFT lookup failed: {html_lib.escape(str(e))}</div>',
            unsafe_allow_html=True,
        )
        return

    owner_short = data["owner"][:6] + "…" + data["owner"][-4:]
    sdn_rule = f"policer {data['bandwidth_mbps']} Mbps · {data['endpoint'].replace('clab://', '')}"
    st.markdown(f'''
      <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;
                  padding:10px 14px;background:#0f1410;border:1px solid #22c55e55;
                  border-radius:8px;font-size:10px;margin-bottom:12px;">
        <div><div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:0.4px;
                        margin-bottom:3px;">Token ID</div>
             <div style="color:#a7e8c4;font-family:ui-monospace,monospace;">{tid}</div></div>
        <div><div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:0.4px;
                        margin-bottom:3px;">Owner</div>
             <div style="color:#a7e8c4;font-family:ui-monospace,monospace;">{owner_short}</div></div>
        <div><div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:0.4px;
                        margin-bottom:3px;">Status</div>
             <div style="color:#a7e8c4;font-family:ui-monospace,monospace;">{html_lib.escape(data["status"])} · {data["seconds_remaining"]}s</div></div>
        <div><div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:0.4px;
                        margin-bottom:3px;">SDN Rule</div>
             <div style="color:#a7e8c4;font-family:ui-monospace,monospace;">{html_lib.escape(sdn_rule)}</div></div>
        <div><div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:0.4px;
                        margin-bottom:3px;">QoS</div>
             <div style="color:#a7e8c4;font-family:ui-monospace,monospace;">guaranteed</div></div>
      </div>
    ''', unsafe_allow_html=True)


def render_iperf_expander() -> None:
    tid = _active_token_id()
    with st.expander("📡 Bandwidth probe (iperf3)", expanded=False):
        if tid is None:
            st.caption("No active credential.")
            return
        if st.button("Run iperf3 probe"):
            try:
                with httpx.Client(timeout=30.0) as c:
                    r = c.post(f"{CONSUMER_BASE_URL}/probe_proxy", json={"tokenId": tid})
                    r.raise_for_status()
                    st.session_state.probe_samples.append(r.json())
                    st.rerun()
            except Exception as e:
                st.error(f"Probe failed: {e}")
        if st.session_state.probe_samples:
            chart_data = {
                "measured_mbps": [s["measured_mbps"] for s in st.session_state.probe_samples],
                "expected_mbps": [s["expected_mbps"] for s in st.session_state.probe_samples],
            }
            st.line_chart(chart_data, height=200)
            last = st.session_state.probe_samples[-1]
            st.caption(
                f"last: {last['src_ce']} → {last['dst_ce']} "
                f"{last['measured_mbps']:.2f} / {last['expected_mbps']:.1f} Mbps"
            )


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
    render_wire_panel()
with col_r:
    render_provider_panel()

bottom_l, bottom_r = st.columns([1, 1])
with bottom_l:
    render_chat_panel()
with bottom_r:
    render_chain_panel()

render_nft_strip()
render_iperf_expander()


user_input = st.chat_input("Ask the consumer agent…")
if user_input:
    st.session_state.turn += 1
    st.session_state.running = True
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    try:
        with httpx.Client(timeout=300.0) as c:
            r = c.post(f"{CONSUMER_BASE_URL}/chat",
                       json={"message": user_input, "model": selected_model})
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        data = {"response": f"Error: {e}", "log": [], "thinking": []}

    ingest_chat_response(st.session_state.turn, data.get("log", []))
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": data.get("response", ""),
        "thinking": data.get("thinking", []),
    })
    st.session_state.running = False
    st.rerun()
