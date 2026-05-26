"""§8 — Events: how off-chain code listens."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "## 8. Events: how off-chain code listens\n"
            "\n"
            "A contract can't push data anywhere — it has no network access. What "
            "it *can* do is emit an **event** during execution. Events become "
            "**logs** attached to the tx receipt and are indexed in a Bloom filter "
            "per block. Off-chain code subscribes to these logs over the JSON-RPC "
            "WebSocket interface (`eth_subscribe`) or polls them with `eth_getLogs`.\n"
            "\n"
            "We already emitted `Greeted` events in §7. Let's read them."
        ),
        code(
            "# Fetch all logs for HelloWorld since genesis.\n"
            "raw = run(['cast', 'logs',\n"
            "           '--address', HELLO,\n"
            "           '--from-block', '0',\n"
            "           '--rpc-url', RPC])"
        ),
        md(
            "Each log has:\n"
            "\n"
            "- **`address`** — contract that emitted it (`HELLO`).\n"
            "- **`topics[0]`** — `keccak256(\"Greeted(address,uint256)\")`. The event "
            "  *signature hash*. This is how you filter by event type without "
            "  knowing the contract's ABI.\n"
            "- **`topics[1..]`** — the `indexed` arguments (here: `who`). Indexed "
            "  args are stored as topics so they're searchable; non-indexed args "
            "  go in `data` and aren't.\n"
            "- **`data`** — ABI-encoded non-indexed args (here: `count`).\n"
            "\n"
            "Filter by indexed arg — \"give me only Greeted events where `who` is Alice\":"
        ),
        code(
            "# topics[0] = signature, topics[1] = padded Alice address.\n"
            "sig = run(['cast', 'keccak', 'Greeted(address,uint256)'])\n"
            "alice_topic = '0x' + '0' * 24 + ALICE[2:].lower()\n"
            "run(['cast', 'logs',\n"
            "     '--address', HELLO,\n"
            "     '--from-block', '0',\n"
            "     sig, alice_topic, '--rpc-url', RPC])"
        ),
        md(
            "### Why this matters for BandwidthEscrow\n"
            "\n"
            "`BandwidthEscrow` emits `AgreementRequested(uint256 indexed agreementId, "
            "address indexed consumer, address indexed provider, uint256 bandwidthMbps, "
            "uint256 durationSeconds, uint256 priceWei)`.\n"
            "\n"
            "Three fields are `indexed` — the EVM allows up to three (plus the "
            "signature) topics per log. The choice tells you what the contract "
            "expects to be *filtered on*:\n"
            "\n"
            "- `agreementId` — \"give me events for this specific agreement.\"\n"
            "- `consumer` — \"give me every request from this consumer.\"\n"
            "- `provider` — \"give me every request directed at this provider.\"\n"
            "\n"
            "This is exactly what the provider service in this repo does: it "
            "subscribes to `AgreementRequested` filtered on its own provider "
            "address, then reacts to each match by calling `deposit()`. That's the "
            "bridge between on-chain state and the off-chain agents — and now you "
            "know how the listening side actually works at the protocol level."
        ),
    ]
