"""
Periodic sweep that finds slots whose lease has expired and revokes
the SDN allocation, freeing the slot for reuse.
"""
from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import time

from fastmcp import Client as MCPClient

from provider.catalog import slot_pool
from provider.mcp_server import mcp

log = logging.getLogger("provider.expiry")


async def expiry_sweep_loop(period_seconds: int = 30) -> None:
    """Run forever: every period_seconds, revoke SDN for any expired slot."""
    log.info("Expiry sweep started, period=%ss", period_seconds)
    while True:
        await asyncio.sleep(period_seconds)
        try:
            await _sweep_once()
        except Exception:
            log.exception("expiry sweep error")


async def _sweep_once() -> None:
    now = time.time()
    # SlotPool reclaims expired entries on read; capture them *before* the
    # next read clears them by reading the raw rows directly.
    rows: list[dict] = []
    with open(slot_pool.path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            for line in f.read().splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    expired: list[tuple[str, str, str, int]] = []
    for row in rows:
        for s in row.get("slots", []):
            if s.get("expiresAt") is not None and s["expiresAt"] < now:
                aid = s.get("agreementId")
                if aid is None:
                    continue
                expired.append((s["pe"], s["subinterface"], s["ce"], int(aid)))

    if not expired:
        return

    async with MCPClient(mcp) as client:
        for pe, subif, ce, aid in expired:
            log.info("revoking expired slot pe=%s sif=%s aid=%s", pe, subif, aid)
            try:
                await client.call_tool("revoke_bandwidth", {
                    "customer_id": "expired",
                    "pe": pe,
                    "subinterface": subif,
                })
            except Exception:
                log.exception("revoke_bandwidth failed")
            slot_pool.release(aid)
