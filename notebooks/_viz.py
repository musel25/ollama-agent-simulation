"""Notebook rendering helpers.

Single source of truth for mermaid diagrams, MCP-tool inspectors,
A2A agent-card views, JSON state diffs, chat-bubble logs, on-chain
state pills, event timelines, network-topology graphs, and the
before/after ipywidgets toggle. Imported by every notebook in the
pedagogical series.

Mermaid rendering uses the mermaid.ink HTTP service (the same approach
LangGraph uses internally for draw_mermaid_png). Offline behavior:
fall back to a fenced markdown block so notebooks remain readable.
"""
from __future__ import annotations

import base64
import html as _html
import io
import json
from typing import Any, Iterable

import httpx
from IPython.display import HTML, Image


def render_mermaid(source: str) -> HTML | Image:
    """Render mermaid source as a PNG via mermaid.ink, or fenced text on failure."""
    try:
        encoded = base64.urlsafe_b64encode(source.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{encoded}"
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
        return Image(data=resp.content, format="png")
    except Exception:
        # offline or rate-limited fallback
        escaped = _html.escape(source)
        return HTML(f"<pre style='background:#f6f8fa;padding:8px;"
                    f"border-radius:6px'><code>{escaped}</code></pre>")
