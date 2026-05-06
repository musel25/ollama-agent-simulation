"""Watch the escrow for AgreementRequested events and drive mint+swap.

Lives apart from provider/app.py so the listener loop can be exercised
in isolation by tests and notebooks. The MCP client passed in is the
same in-memory FastMCP server the rest of the app uses.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastmcp import Client as MCPClient
from fastmcp import FastMCP
from web3 import Web3

from provider.catalog import (
    CATALOG_BY_ID, cleanup_quotes, pending_quotes, slot_pool,
)
from shared.contracts import get_escrow_contract

log = logging.getLogger("provider.event_listener")


async def run(w3: Web3, mcp: FastMCP, poll_interval_s: float = 2.0) -> None:
    """Loop forever: poll AgreementRequested logs and drive mint/swap.

    Cancellable: catch `asyncio.CancelledError` in the caller's `finally`
    so `lifespan` can clean shut down.
    """
    escrow = get_escrow_contract(w3)
    last_block = w3.eth.block_number
    log.info("Event listener started at block %d", last_block)
    handler_tasks: set[asyncio.Task] = set()

    while True:
        await asyncio.sleep(poll_interval_s)
        try:
            current = w3.eth.block_number
            if current <= last_block:
                continue
            events = escrow.events.AgreementRequested.get_logs(
                fromBlock=last_block + 1, toBlock=current)
            last_block = current
            for evt in events:
                args = evt["args"]
                t = asyncio.create_task(
                    _handle(escrow, mcp, args["agreementId"], args))
                handler_tasks.add(t)
                t.add_done_callback(handler_tasks.discard)
        except Exception:
            log.exception("Event listener error")


async def _handle(escrow, mcp: FastMCP, agreement_id: int, args: dict) -> None:
    cleanup_quotes()
    quote = pending_quotes.get(agreement_id)
    if not quote or time.time() > quote["expires"]:
        log.warning("No valid quote for agreementId=%d", agreement_id)
        return
    pkg = CATALOG_BY_ID.get(quote["packageId"])
    if not pkg:
        log.error("Unknown packageId for agreementId=%d", agreement_id)
        return
    ag = escrow.functions.getAgreement(agreement_id).call()
    if (ag[2] != pkg["mbps"] or ag[3] != pkg["durationSeconds"]
            or ag[4] != pkg["priceWei"]):
        log.error("Param mismatch for agreementId=%d", agreement_id)
        return
    slot = slot_pool.reserve(pkg["packageId"], agreement_id,
                             pkg["durationSeconds"])
    if slot is None:
        log.error("No slots for tier=%s", pkg["packageId"])
        return
    try:
        async with MCPClient(mcp) as client:
            mint = await client.call_tool("mint_credential", {
                "agreement_id": agreement_id,
                "consumer_address": args["consumer"],
                "pe": slot.pe, "subinterface": slot.subinterface,
                "ce": slot.ce, "mbps": pkg["mbps"],
                "duration_seconds": pkg["durationSeconds"],
            })
            mint_data = json.loads(mint.content[0].text)
            token_id = int(mint_data["tokenId"])
            await client.call_tool("complete_swap", {
                "agreement_id": agreement_id, "token_id": token_id})
        del pending_quotes[agreement_id]
    except Exception:
        log.exception("mint/swap flow failed for agreementId=%d", agreement_id)
        slot_pool.release(agreement_id)
