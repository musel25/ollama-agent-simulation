# A2A + per-agent MCP + real SDN enforcement — design

| Field | Value |
|---|---|
| Date | 2026-05-01 |
| Branch | `feat/mcp-a2a` |
| Status | Draft — pending user review |
| Author | Claude (Opus 4.7) with Müsel Tabares |
| Supersedes | The single-MCP cross-network architecture currently on `feat/mcp-a2a` |
| Paper | `paper/main.tex` — *Autonomous Agent-to-Agent Network Service Provisioning via Smart-Contract Escrow and Tokenized Authorization* |
| Sibling repo | `https://github.com/musel25/srl-gnmi-bandwidth-poc` (referred to throughout as "brother repo") |

---

## 1. Goals and non-goals

### 1.1 Goals

1. Make the implementation honor the paper's architectural claim that **A2A is the only inter-agent protocol** and **MCP is the intra-agent tool-invocation protocol**, with each agent owning its own MCP server.
2. Replace the mocked gateway response with **real SDN enforcement** — `gNMI` policer push to SR Linux + Linux `tc tbf` rate limiting on the customer-edge container — by integrating the brother repo as a Python dependency.
3. Use **standards-compliant primitives**: the official `a2a-sdk` Python package, FastMCP in-memory transport, and the RFC-8615 well-known URL `/.well-known/agent-card.json`.
4. **Stay extensible to multi-agent**: 1+1 today, designed so adding a second consumer or provider is a deployment change, not a refactor.
5. Preserve the existing on-chain settlement mechanism (`BandwidthEscrow.sol` + `BandwidthNFT.sol`) — the contracts are correct and out of scope for changes.

### 1.2 Non-goals (explicit)

1. **No identity / delegation work in this plan.** No DIDs, no ENS, no ERC-4337 smart accounts, no ERC-7710 delegation. The current EOA-per-agent model is preserved. Identity is the natural follow-up plan (Path B in the prior conversation); §13 marks the seams.
2. **No paper edits.** `paper/main.tex` and the bib stay as-is.
3. **No new contracts.** `BandwidthEscrow.sol` and `BandwidthNFT.sol` are unchanged. The activation flow uses what's already on chain.
4. **No identity-bound NFT.** The credential still names the consumer's EOA, not a human principal.
5. **No production-grade durability.** `pending_quotes` may stay in-memory; slot pool stays file-backed with `fcntl`. Persistence/HA is a separate plan.
6. **No legacy cleanup beyond what touches our changes.** Files in §14.3 are deleted; the legacy prototype files (`app.py`, `consumer_agent.py`, `provider_server.py` at repo root) stay untouched — they were already dead.

### 1.3 Research question (from §Introduction of the paper)

> Can two agents complete an end-to-end network-service acquisition where payment is escrowed on-chain, an NFT credential is exchanged for payment, and that credential triggers provider-side network activation?

Today the implementation answers "yes" except the activation step is faked. After this plan it answers "yes" with real `gNMI`+`tc` activation. That is the load-bearing thing to keep in mind when evaluating any design tradeoff in §11.

---

## 2. Background — what we have, what's wrong with it

### 2.1 Current state (post `feat/mcp-a2a`, pre this plan)

- **Two FastAPI services**: `consumer/app.py` (port 8001) drives an Ollama tool-calling loop; `provider/app.py` (port 8002) hosts a FastMCP server at `/mcp`. A separate `provider/gateway.py` (port 8003) verifies signed nonces and returns service metadata.
- **Inter-agent transport is MCP** — the consumer's `consumer/mcp_client.py` opens an `async with Client(PROVIDER_MCP_URL)` connection per call. There is no A2A traffic.
- **Agent cards** are static dicts on `/.well-known/agent.json`; nobody reads them at runtime.
- **Activation is mocked**: gateway `/service` returns a JSON dict with bandwidth fields; no network hardware is configured.

### 2.2 Specific divergences from the paper

| Paper claim (§Architecture) | Reality (today) |
|---|---|
| "A2A is the inter-agent protocol" | Inter-agent traffic is MCP. |
| "MCP is the intra-agent protocol: each agent uses it to invoke its own local tools" | Only the provider has an MCP server. The consumer has none. |
| "A2A is the only point of contact between [the agents]" | The consumer reaches the provider's MCP at `/mcp` and the gateway at `/service`. |
| "the gateway… issues the corresponding command to the SDN controller" | Gateway returns metadata; no SDN controller exists. |
| Agents "deliberately asymmetric" with role-specific tools | Asymmetry exists by accident: provider has 2 MCP tools, consumer has none. |

### 2.3 Why the current code drifted

`feat/mcp-a2a` was scoped to introduce MCP. The shortest path was to expose provider tools over MCP and let the consumer call them directly. That was a useful intermediate but is not what the paper claims.

---

## 3. Design philosophy

The four principles below resolve every ambiguous design choice that follows.

1. **Research question is sacred; the paper diagram is not.** The RQ in §1.3 must be answered end-to-end with real components. Conceptual boxes from `paper/diagrams/d3_architecture_stack.png` (e.g., "gateway") may be folded into other components if the RQ stays satisfied.
2. **A2A = inter-agent. MCP = everything else.** No inter-agent traffic outside A2A. The LLM in each agent only sees MCP tools — A2A clients are hidden inside MCP tool implementations. The LLM never directly invokes A2A.
3. **N consumers + M providers from day one.** Single-agent demo is just N=1, M=1. Adding agents = deploy more containers, not edit code. Provider URL is a parameter to consumer MCP tools; multiple `provider_url`s are passed in via env.
4. **Standards over bespoke.** `a2a-sdk` (Google A2A reference SDK), `fastmcp` in-memory transport, `/.well-known/agent-card.json` (RFC-8615). No hand-rolled JSON-RPC.

---

## 4. Architecture

### 4.1 Diagram

```
┌─────────────────────────── CONSUMER PROCESS (per consumer) ───────────────────────────┐
│                                                                                       │
│  Ollama LLM                                                                           │
│      │ chat(messages, tools=mcp_tools)                                                │
│      ▼                                                                                │
│  Consumer driver (consumer/app.py)                                                    │
│      │ Client(consumer_mcp)  ← in-memory FastMCP transport                            │
│      ▼                                                                                │
│  consumer.mcp_server (FastMCP)                                                        │
│      tools:                                                                           │
│        wallet_address()                       ── eth_account                          │
│        sign_message(text)                     ── eth_account                          │
│        lock_payment(agreement_id)             ── web3 → Anvil                         │
│        await_settlement(agreement_id)         ── web3 → Anvil                         │
│        browse_catalog(provider_url)        ─┐                                         │
│        request_quote(provider_url, pkg)     ├─ a2a-sdk client → provider A2A endpoint │
│        present_credential(provider_url, tid)─┘                                        │
│                                                                                       │
│  Serves:                                                                              │
│    GET /.well-known/agent-card.json                                                   │
│    POST /chat (existing UI surface, unchanged contract)                               │
└─────────────────────────────────────────────────────┬─────────────────────────────────┘
                                                      │ A2A POST /v1/message/send
                                                      │ (a2a-sdk, JSON-RPC over HTTP)
                                                      ▼
┌─────────────────────────── PROVIDER PROCESS (per provider) ───────────────────────────┐
│                                                                                       │
│  A2A server (a2a-sdk Starlette routes mounted on FastAPI)                             │
│      DefaultRequestHandler(                                                           │
│          agent_executor=BandwidthProviderExecutor(),                                  │
│          task_store=InMemoryTaskStore(),                                              │
│          agent_card=public_card)                                                      │
│      │                                                                                │
│      │ on inbound a2a/message/send:                                                   │
│      ▼                                                                                │
│  BandwidthProviderExecutor (provider/agent_executor.py)                               │
│      │ Client(provider_mcp)  ← in-memory FastMCP transport                            │
│      ▼                                                                                │
│  provider.mcp_server (FastMCP)                                                        │
│      tools:                                                                           │
│        get_catalog()                                                                  │
│        request_quote(package_id, consumer_address)                                    │
│        mint_credential(agreement_id, consumer_address, slot, mbps, duration)          │
│        complete_swap(agreement_id, token_id)                                          │
│        verify_credential_ownership(token_id, signature, nonce)                        │
│        allocate_bandwidth(customer_id, pe, subinterface, mbps)  ── srl_bandwidth      │
│        revoke_bandwidth(customer_id, pe, subinterface)          ── srl_bandwidth      │
│        verify_bandwidth(src_ce, dst_ce, expected_mbps)          ── srl_bandwidth      │
│                                                                                       │
│  Background:                                                                          │
│      AgreementRequested event listener (asyncio task)                                 │
│        on event → MCP mint_credential → MCP complete_swap                             │
│                                                                                       │
│  Serves:                                                                              │
│    GET  /.well-known/agent-card.json                                                  │
│    POST /v1/message/send         (a2a-sdk JSON-RPC route)                             │
│    POST /v1/message/stream       (a2a-sdk SSE route, optional)                        │
│    GET  /v1/tasks/{task_id}      (a2a-sdk REST route)                                 │
└──────────────────────────────────────┬─────────────────────────┬──────────────────────┘
                                       │ web3                    │ pygnmi + docker exec
                                       ▼                         ▼
                  Anvil (BandwidthEscrow + BandwidthNFT)    ContainerLab
                                                            (pe1, pe2, p1, ce1..ce4)
```

Two key differences from today, restated visually:

1. The consumer no longer has an arrow into the provider's MCP — it goes via A2A.
2. The provider no longer has a `:8003` gateway — its A2A endpoint plays the gateway role.

### 4.2 Trust boundaries

| Boundary | What crosses | Trust assumption |
|---|---|---|
| Consumer LLM ↔ consumer MCP | Tool calls | Trusted (same process) |
| Consumer A2A client ↔ Provider A2A server | A2A messages over HTTP | Untrusted — payload validated; network attacker assumed |
| Provider A2A server ↔ Provider MCP | Internal tool calls | Trusted (same process) |
| Provider MCP `verify_credential_ownership` ↔ on-chain | `ownerOf()` call | Trusted (chain is the source of truth) |
| Provider MCP `allocate_bandwidth` ↔ SR Linux | gNMI over TLS | Trusted in PoC; cert pinning would be next step |
| Provider MCP `allocate_bandwidth` ↔ ContainerLab CE | `docker exec` | Trusted (host) |

Authentication of A2A traffic: this plan uses **unauthenticated** A2A for the demo (the provider treats every inbound message as anonymous and validates only what's in the payload). The credential check is purely cryptographic (ECDSA signature over a nonce, recovered to an address, compared to `ownerOf(token_id)` on chain). Adding a `securityScheme` in the AgentCard is in scope for §13.

---

## 5. Component-level design

### 5.1 New files

| Path | Purpose |
|---|---|
| `consumer/mcp_server.py` | FastMCP server with the seven consumer tools (§7.1). |
| `consumer/a2a_client.py` | Thin wrapper around `a2a-sdk` client. Exposes `discover_provider`, `send_to_provider(provider_url, payload)`. Used internally by consumer MCP tools, not by the LLM. |
| `provider/agent_executor.py` | `BandwidthProviderExecutor(AgentExecutor)` — handles inbound A2A messages. Routes to provider MCP tools via in-memory MCP client. |
| `provider/agent_card.py` | Builds the `a2a.types.AgentCard` instance for both consumer and provider; centralized to keep schema consistency. |
| `shared/a2a_messages.py` | Pydantic models for the structured `data` parts the agents exchange. Defines `BrowseCatalogRequest`, `QuoteRequest`, `ActivateRequest`, etc. |
| `shared/slot_pool.py` | Slot-pool data structure: per-tier list of `{pe, subinterface, ce, agreement_id, expires_at}`. Manages reservations. |

### 5.2 Files that change

| Path | Change |
|---|---|
| `consumer/app.py` | LLM loop now wires `Client(consumer_mcp)` (in-memory). Tool dispatch goes through MCP. Static `AGENT_CARD` becomes an `a2a.types.AgentCard` from `agent_card.py`. `/.well-known/agent.json` becomes a redirect to `/agent-card.json`. |
| `consumer/mcp_client.py` | **Deleted.** Replaced by `consumer/a2a_client.py`. |
| `provider/app.py` | Mounts a2a-sdk routes; removes `/quote` POST endpoint (now A2A-only); event listener uses in-memory MCP client to call its own tools. |
| `provider/mcp_server.py` | Adds five new tools (mint_credential, complete_swap, verify_credential_ownership, allocate/revoke/verify bandwidth). |
| `provider/catalog.py` | Catalog values rescaled (§9.1). Slot pool replaces simple slot counter. |
| `provider/inventory.txt` | New JSONL schema (§7.4). Migration: hand-edit (file is dev/test only). |
| `pyproject.toml` | `uv add a2a-sdk "srl-bandwidth @ git+https://github.com/musel25/srl-gnmi-bandwidth-poc.git"`. |
| `docker-compose.yml` | Removes `:8003` port; parameterizes consumer/provider for multi-agent (§10). |
| `Dockerfile.provider` | Installs `containerlab` client tools? **No** — see §11. The provider container talks to ContainerLab on the host via Docker socket mount. |
| `Makefile` | `make demo` target updated; new `make clab-up` / `make clab-down` targets that call brother repo's deploy/destroy scripts. |
| `tests/test_mcp_client.py` | Renamed and rewritten as `tests/test_consumer_mcp.py` — exercises the in-memory FastMCP client against the consumer server. |
| `tests/test_catalog.py` | Updated for new catalog values + slot-pool semantics. |
| `provider/gateway.py` | **Deleted.** |
| `consumer/ui.py` | Streamlit UI: minor copy update; underlying `/chat` contract is unchanged. |

### 5.3 Files unchanged (asserted)

- `contracts/src/BandwidthEscrow.sol`
- `contracts/src/BandwidthNFT.sol`
- `contracts/script/Deploy.s.sol`
- `shared/contracts.py`, `shared/abi/*.json`
- `paper/**` (per user instruction)

---

## 6. Data flows — six paper stages mapped to A2A + MCP

The paper's §Scenario lists six stages. This section traces each through the new architecture so the mapping is unambiguous.

### Stage 1 — Discovery and Selection

| Step | Actor | Mechanism |
|---|---|---|
| Consumer LLM decides it needs a tier | LLM | system prompt |
| LLM calls `browse_catalog(provider_url)` | MCP (in-memory) | `Client(consumer_mcp).call_tool("browse_catalog", {...})` |
| Consumer MCP tool resolves provider's agent card | A2A | `A2ACardResolver(httpx, base_url=provider_url).get_agent_card()` |
| Consumer MCP tool sends `message/send` with `data` part `{action: "get_catalog"}` | A2A | `client.send_message(SendMessageRequest(message=...))` |
| Provider AgentExecutor receives, calls own MCP `get_catalog` | MCP (in-memory) | `Client(provider_mcp).call_tool("get_catalog", {})` |
| Provider AgentExecutor returns Task with Artifact whose part has the catalog JSON | A2A | `event_queue.enqueue_event(TaskArtifactUpdateEvent(...))` |
| Consumer MCP tool returns catalog JSON to LLM | MCP | tool result string |

### Stage 2 — Payment Lock

| Step | Actor | Mechanism |
|---|---|---|
| LLM picks a tier and calls `request_quote(provider_url, package_id)` | MCP | in-memory call |
| Tool sends A2A `data: {action: "request_quote", package_id, consumer_address}` | A2A | send_message |
| Provider AgentExecutor calls MCP `request_quote(package_id, consumer_address)` | MCP (in-memory) | call_tool |
| Provider returns `{agreement_id, price_wei, mbps, duration_seconds}` in Artifact | A2A | enqueue |
| Consumer MCP tool caches the quote (preserving 128-bit `agreement_id` precision) | local | `quote_cache[str(agreement_id)] = {...}` |
| LLM calls `lock_payment(agreement_id)` | MCP | in-memory |
| Tool sends `escrow.requestAgreement(agreement_id, provider, mbps, duration)` with `value=price_wei` | web3 | tx, wait for receipt |
| Tool returns tx hash | MCP | tool result |

### Stage 3 — Credential Issuance

Trigger is **on-chain**, not LLM-driven.

| Step | Actor | Mechanism |
|---|---|---|
| `BandwidthEscrow.requestAgreement` emits `AgreementRequested` | EVM | event |
| Provider's background event listener picks it up | provider/app.py asyncio task | `escrow.events.AgreementRequested.get_logs(...)` |
| Listener selects free slot from pool, binds to agreement | local | `slot_pool.allocate(tier, agreement_id)` |
| Listener calls own MCP `mint_credential(...)` | MCP (in-memory) | call_tool |
| `mint_credential` calls `nft.mint(provider, agreement_id, mbps, duration, endpoint)` | web3 | tx |

### Stage 4 — Swap

| Step | Actor | Mechanism |
|---|---|---|
| Listener calls own MCP `complete_swap(agreement_id, token_id)` | MCP (in-memory) | call_tool |
| Tool calls `nft.approve(escrow, token_id)` then `escrow.deposit(agreement_id, token_id)` | web3 | tx |
| Inside `escrow.deposit`: NFT → consumer, ETH → provider, status → ACTIVE | EVM | atomic |

### Stage 5 — Activation

| Step | Actor | Mechanism |
|---|---|---|
| Consumer LLM calls `await_settlement(agreement_id)` | MCP | polls `escrow.getAgreement` |
| When ACTIVE, LLM calls `present_credential(provider_url, token_id)` | MCP | in-memory |
| Tool generates fresh nonce (unix timestamp) and signs it | local | `eth_account.sign_message` |
| Tool sends A2A `data: {action: "activate", token_id, nonce, signature}` | A2A | send_message |
| Provider AgentExecutor calls MCP `verify_credential_ownership(token_id, signature, nonce)` | MCP | call_tool |
| MCP tool: nonce age check → `Account.recover_message` → `nft.ownerOf(token_id)` → compare | web3 | call |

### Stage 6 — Consumption

| Step | Actor | Mechanism |
|---|---|---|
| Provider AgentExecutor calls MCP `allocate_bandwidth(customer_id=consumer_address, pe, subinterface, mbps)` | MCP | call_tool |
| MCP tool delegates to `srl_bandwidth.bandwidth.allocate_bandwidth(ServiceRequest(...))` | imported | function call |
| `srl_bandwidth` pushes gNMI policer to PE | pygnmi | gRPC+TLS |
| `srl_bandwidth` applies `tc tbf` on connected CE container | docker exec | subprocess |
| Provider AgentExecutor returns Artifact `{status: "active", bandwidth_mbps, seconds_remaining, endpoint}` | A2A | enqueue |
| Consumer LLM reports success to user | MCP/UI | text response |

---

## 7. Schemas

### 7.1 Consumer MCP tools

```python
@mcp.tool()
def wallet_address() -> str:
    """Return the consumer agent's Ethereum address (0x...)."""

@mcp.tool()
def sign_message(text: str) -> str:
    """Sign an arbitrary text with the consumer's key. Returns hex signature.
    Used internally by present_credential; rarely needed by the LLM directly."""

@mcp.tool()
async def browse_catalog(provider_url: str) -> str:
    """Discover a provider's catalog via A2A. Returns JSON array of
    {packageId, mbps, durationSeconds, priceWei, availableSlots}."""

@mcp.tool()
async def request_quote(provider_url: str, package_id: str) -> str:
    """Request a quote via A2A. Returns
    {agreementId, priceWei, bandwidthMbps, durationSeconds}."""

@mcp.tool()
def lock_payment(agreement_id: str) -> str:
    """Send escrow.requestAgreement on-chain using the cached quote.
    Returns tx hash on success."""

@mcp.tool()
def await_settlement(agreement_id: str, max_attempts: int = 8) -> str:
    """Poll escrow.getAgreement until status == ACTIVE.
    Returns the tokenId on success or 'PENDING' if exhausted."""

@mcp.tool()
async def present_credential(provider_url: str, token_id: int) -> str:
    """Sign a fresh nonce, send A2A 'activate' message, return service
    metadata {bandwidth_mbps, seconds_remaining, endpoint, status}."""
```

### 7.2 Provider MCP tools

```python
@mcp.tool()
def get_catalog() -> str:
    """JSON array with availability."""

@mcp.tool()
def request_quote(package_id: str, consumer_address: str) -> str:
    """JSON quote with agreementId, or {error}."""

@mcp.tool()
def mint_credential(
    agreement_id: int,
    consumer_address: str,
    pe: str,
    subinterface: str,
    ce: str,
    mbps: int,
    duration_seconds: int,
) -> str:
    """Mint NFT, return JSON {tokenId, txHash, endpoint}.
    Endpoint embeds (pe, subinterface) so the credential is bound to a
    specific resource slot."""

@mcp.tool()
def complete_swap(agreement_id: int, token_id: int) -> str:
    """Approve escrow, call deposit. Returns JSON {txHash, status}.
    Reverts if status != REQUESTED on-chain."""

@mcp.tool()
def verify_credential_ownership(token_id: int, signature: str, nonce: str) -> str:
    """ECDSA recover, compare to ownerOf(tokenId).
    Returns JSON {ok: bool, signer, owner, agreement_id, mbps, duration_seconds,
                  endpoint, seconds_remaining, status}."""

@mcp.tool()
def allocate_bandwidth(customer_id: str, pe: str, subinterface: str, mbps: float) -> str:
    """Wraps srl_bandwidth.bandwidth.allocate_bandwidth.
    Returns JSON AllocationResult {success, gnmi_pushed, tc_applied, message}."""

@mcp.tool()
def revoke_bandwidth(customer_id: str, pe: str, subinterface: str) -> str:
    """Wraps srl_bandwidth.bandwidth.revoke_bandwidth. Returns JSON {status: 'revoked'}."""

@mcp.tool()
def verify_bandwidth(src_ce: str, dst_ce: str,
                     expected_mbps: float | None = None,
                     tolerance: float = 0.2) -> str:
    """Wraps srl_bandwidth.bandwidth.verify_bandwidth.
    Returns JSON VerifyResult {passed, measured_mbps, expected_mbps, message}."""
```

### 7.3 A2A `data` payloads (`shared/a2a_messages.py`)

A2A messages carry `parts`. Where today's MCP returns a JSON string, A2A returns a `Part` with `data: {...}`. We define Pydantic models for round-tripping:

```python
class BrowseCatalogRequest(BaseModel):
    action: Literal["get_catalog"] = "get_catalog"

class QuoteRequest(BaseModel):
    action: Literal["request_quote"] = "request_quote"
    package_id: str
    consumer_address: str

class ActivateRequest(BaseModel):
    action: Literal["activate"] = "activate"
    token_id: int
    nonce: str            # unix timestamp string (matches gateway today)
    signature: str        # 0x-prefixed hex

class CatalogResponse(BaseModel):
    catalog: list[CatalogEntry]

class QuoteResponse(BaseModel):
    agreement_id: str     # serialized as string to preserve uint256
    price_wei: int
    bandwidth_mbps: int
    duration_seconds: int

class ActivateResponse(BaseModel):
    status: Literal["active", "denied"]
    bandwidth_mbps: int | None = None
    seconds_remaining: int | None = None
    endpoint: str | None = None
    reason: str | None = None
```

The agent executor's dispatch: read the first `data` part, look up `action`, route. Anything else returns an error Artifact with status `TASK_STATE_REJECTED`.

### 7.4 Slot pool (`provider/inventory.txt`)

New JSONL — one row per tier:

```json
{
  "tier": "small",
  "mbps": 2,
  "durationSeconds": 600,
  "slots": [
    {"pe": "pe1", "subinterface": "ethernet-1/2.0", "ce": "ce1",
     "agreementId": null, "expiresAt": null}
  ]
}
{
  "tier": "medium",
  "mbps": 5,
  "durationSeconds": 600,
  "slots": [
    {"pe": "pe1", "subinterface": "ethernet-1/3.0", "ce": "ce3",
     "agreementId": null, "expiresAt": null}
  ]
}
{
  "tier": "large",
  "mbps": 8,
  "durationSeconds": 600,
  "slots": [
    {"pe": "pe2", "subinterface": "ethernet-1/2.0", "ce": "ce2",
     "agreementId": null, "expiresAt": null}
  ]
}
```

Reads/writes still use `fcntl.LOCK_EX`. A slot is "available" iff `agreementId is None or time.time() > expiresAt`. The rationale for the rescaled `mbps` values is in §9.

### 7.5 Agent cards

Both agents serve a card. Consumer's is minimal (it is a client most of the time, but advertising still helps observability):

```python
provider_card = AgentCard(
    name="Bandwidth Provider Agent",
    description="Sells bandwidth packages via atomic on-chain escrow + NFT credential. "
                "Activates network policy via gNMI on Nokia SR Linux PE.",
    version="2.0.0",
    default_input_modes=["application/json", "text/plain"],
    default_output_modes=["application/json"],
    capabilities=AgentCapabilities(streaming=False, extended_agent_card=False),
    supported_interfaces=[
        AgentInterface(protocol_binding="JSONRPC",
                       url=f"{PROVIDER_BASE_URL}/v1/message/send"),
    ],
    skills=[
        AgentSkill(id="get_catalog", name="Get Catalog",
                   description="...", tags=["bandwidth", "catalog"]),
        AgentSkill(id="request_quote", name="Request Quote", ...),
        AgentSkill(id="activate", name="Activate Service", ...),
    ],
)
```

Served at both `/.well-known/agent-card.json` (canonical, RFC-8615) and `/.well-known/agent.json` (legacy alias, returns 301 to canonical).

---

## 8. ContainerLab integration

### 8.1 Topology

We adopt the brother repo's 7-node topology verbatim: `pe1`, `pe2`, `p1`, `ce1..ce4`. No changes to `topology/bandwidth-poc.clab.yml`.

### 8.2 Where ContainerLab runs

ContainerLab requires:
- root (creates veth pairs)
- direct host Docker access
- Linux host (or WSL2)

It cannot live inside a Compose service without privileged mode + host networking, which defeats its isolation. **Decision: ContainerLab runs on the host.** The provider container is given:

```yaml
provider-agent:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro    # to docker exec on CEs
  extra_hosts:
    - "host.docker.internal:host-gateway"             # to reach pe management IPs
  environment:
    - GNMI_TARGET_OVERRIDE=auto                       # pygnmi resolves via docker inspect
```

The provider's `allocate_bandwidth` MCP tool ultimately runs `subprocess.run(["docker", "exec", ...])` and `pygnmi.gNMIclient(target=mgmt_ip, ...)`. With the docker socket mounted, both work from inside the container. The brother repo's `bandwidth.py` already does `docker inspect` to discover mgmt IPs at runtime — no static config needed.

### 8.3 Mock SDN fallback

For reviewers / CI without ContainerLab:

```python
# provider/mcp_server.py
SDN_MOCK = os.environ.get("SDN_MOCK", "false").lower() == "true"

@mcp.tool()
def allocate_bandwidth(...):
    if SDN_MOCK:
        log.info("SDN_MOCK: pretending to allocate %s Mbps on %s/%s for %s",
                 mbps, pe, subinterface, customer_id)
        return json.dumps({"success": True, "gnmi_pushed": False, "tc_applied": False,
                           "message": "mock"})
    return _delegate_to_srl_bandwidth(...)
```

`SDN_MOCK=true` is set in `docker-compose.yml` by default; `make demo-real` flips it off and assumes the user has clab deployed.

### 8.4 Operating model

```
$ bash ../srl-gnmi-bandwidth-poc/scripts/deploy.sh   # one-time per session
$ bash ../srl-gnmi-bandwidth-poc/scripts/push-config.sh
$ make up                                             # this repo: anvil + agents
$ SDN_MOCK=false make demo                            # real allocation + iperf3
```

`make clab-up` and `make clab-down` are convenience wrappers in this repo's Makefile.

---

## 9. Catalog rescaling

### 9.1 New values

| Tier | Today (Mbps) | New (Mbps) | Slot |
|---|---|---|---|
| small | 50 | **2** | pe1 / ethernet-1/2.0 / ce1 |
| medium | 100 | **5** | pe1 / ethernet-1/3.0 / ce3 |
| large | 500 | **8** | pe2 / ethernet-1/2.0 / ce2 |

`durationSeconds` stays at 600. `priceWei` stays unchanged (the on-chain check is `priceWei == quote.priceWei`, not a market price).

### 9.2 Why

The free Nokia SR Linux container caps the datapath at **1000 PPS ≈ 12 Mbps at 1500 B MTU** (brother repo `CLAUDE.md`, Constraint 1). Allocations above this hit the cap, not the policer/tc, and `verify_bandwidth` fails. Keeping all tiers ≤ 8 Mbps gives headroom and lets `verify_bandwidth` actually distinguish tiers.

### 9.3 What about the paper's numbers?

The paper does not commit to specific Mbps values for the catalog. The phrase "small/medium/large" appears nowhere in `main.tex`. So this rescaling does not touch the paper.

### 9.4 Spare slot

`ce4` (pe2 / ethernet-1/3.0) is intentionally unmapped. It exists in the topology but holds no tier — reserved for the multi-agent stretch in §10.

---

## 10. Multi-agent extensibility

### 10.1 Multiple consumers

Add `consumer-agent-2` to `docker-compose.yml`:

```yaml
consumer-agent-2:
  build: { context: ., dockerfile: Dockerfile.consumer }
  environment:
    - CONSUMER_PRIVATE_KEY=${CONSUMER_PRIVATE_KEY_2}
    - PROVIDER_A2A_URLS=http://provider-agent:8002
    - OLLAMA_HOST=http://ollama:11434
  ports:
    - "8011:8001"      # external port shifted
```

`anvil` ships with 10 pre-funded test accounts; account #2 becomes `CONSUMER_PRIVATE_KEY_2` in `.env`.

The consumer's slot is the catalog tier × the slot pool's binding policy (§7.4). Two consumers buying `medium` would race for the single medium slot — second one gets "no slots available" until the first expires. Adding a second medium slot is a one-line edit in `inventory.txt`.

### 10.2 Multiple providers

Add `provider-agent-2`:

```yaml
provider-agent-2:
  build: { context: ., dockerfile: Dockerfile.provider }
  environment:
    - PROVIDER_PRIVATE_KEY=${PROVIDER_PRIVATE_KEY_2}
    - INVENTORY_FILE=/app/provider/inventory-2.txt
  ports:
    - "8012:8002"
```

Provider 2's `inventory-2.txt` claims a disjoint set of subinterfaces (e.g., ce4-only). Consumer's `PROVIDER_A2A_URLS` becomes `http://provider-agent:8002,http://provider-agent-2:8012`.

### 10.3 LLM-side changes

System prompt becomes parameterized:

```
Available providers (you may choose any):
  - http://provider-agent:8002      (id: provider-1)
  - http://provider-agent-2:8012    (id: provider-2)

For the user's request, you SHOULD call browse_catalog on each, compare prices
and availability, then proceed with the best option.
```

The `provider_url` parameter on every consumer MCP tool makes this work without code changes.

### 10.4 What does NOT scale yet

- `pending_quotes` is in-memory per provider — provider restart loses pending quotes (consumer's ETH would need manual `cancel` after the deadline).
- Inventory is a single `inventory.txt` per provider — only one provider process per inventory file (still file-locked, but not horizontally scalable).
- Anvil is a single instance — no L2, no multi-chain.

These are flagged as future-work, not addressed by this plan.

---

## 11. Tradeoffs and rejected alternatives

### 11.1 Folding gateway into A2A vs. keeping it separate (decided: fold)

**Pros of folding:** one fewer port, one fewer process, single A2A surface for the consumer to talk to, AgentExecutor naturally encapsulates "verify + activate" as one flow.

**Cons:** the paper draws gateway as a separate box (`d3_architecture_stack.png`). A reviewer expecting that diagram literally might object.

**Decision:** fold. The paper is a conceptual diagram; the RQ is satisfied either way. Easier to revert this if needed than to re-fold later.

### 11.2 Brother repo via Git URL vs. editable local path (decided: Git URL)

**Editable local path** (`uv add --editable ../srl-gnmi-bandwidth-poc`):
- Faster iteration if both repos are being changed simultaneously.
- Requires sibling-path layout — breaks for anyone cloning fresh.

**Git URL** (`uv add "srl-bandwidth @ git+https://github.com/musel25/srl-gnmi-bandwidth-poc.git"`):
- Reproducible from a fresh clone.
- Requires brother repo to expose a real package name (rename `src/` → `srl_bandwidth/` — Phase 0).
- Pin to a specific commit SHA in `pyproject.toml` for stability.

**Decision:** Git URL with commit pin. The 5-minute brother-repo rename is worth it.

### 11.3 LLM sees A2A vs. LLM only sees MCP (decided: only MCP)

**LLM sees A2A** (a `send_a2a_message(provider, text)` tool):
- More "honest" — the LLM knows it's talking across an agent boundary.
- Requires the LLM to construct A2A payloads correctly, doubling prompt complexity.

**LLM only sees MCP** (current decision):
- LLM uses high-level verbs (`browse_catalog`, `request_quote`, `present_credential`).
- A2A is plumbing inside those tools.
- Matches paper's literal statement: "MCP is the intra-agent protocol".

**Decision:** MCP only. If we later need the LLM to negotiate adversarially (e.g., counter-offers), a `send_a2a_message` tool can be added without removing the high-level tools.

### 11.4 In-memory MCP vs. subprocess MCP (decided: in-memory)

FastMCP's docs note in-memory is "specifically designed for testing scenarios." That's a soft warning, not a prohibition — the API is stable and is the only way to keep "one MCP per agent" without a subprocess hop. The LLM-driven path in `consumer/app.py` and the AgentExecutor in `provider/agent_executor.py` both use `Client(mcp_instance)` directly. If a future deployment needs to scale MCP horizontally, the in-memory client becomes an HTTP client (one-line change).

### 11.5 Why NOT redesign contracts to bind credential to delegation

The paper claims feasibility for the EOA-credential model. Adding ERC-4337 / ERC-7710 changes the threat model and probably needs new contracts. Out of scope for this plan; flagged in §13.

### 11.6 Why NOT use x402 for payment

Two reasons. First, the paper §Architecture explicitly compares escrow to x402 and chooses escrow for "auditability". Second, x402 produces a stateless receipt, not a transferable credential — the paper's Stage 5 (presenting the NFT) doesn't fit x402's model. We respect the paper's choice.

---

## 12. Phase plan (high-level — full implementation plan in a separate document)

Each phase has acceptance criteria. Phases are sequential except where noted.

| Phase | Name | Outputs | Acceptance |
|---|---|---|---|
| **0** | Brother-repo prep | `srl_bandwidth/` package; pushed to GitHub | `pip install git+...` succeeds in a fresh venv |
| **1** | Dependencies | `a2a-sdk` and `srl-bandwidth` in `pyproject.toml` | `uv sync` succeeds; smoke imports work |
| **2** | Provider intra-agent MCP | 5 new MCP tools, slot pool, listener uses MCP | event listener still settles AgreementRequested → ACTIVE on Anvil |
| **3** | Provider A2A server | `agent_executor.py`, mounted Starlette routes | A2A `message/send` with `get_catalog` returns the catalog |
| **4** | Drop gateway, fold activation | `gateway.py` deleted, `verify_credential_ownership` MCP tool | A2A `activate` returns mock allocation result |
| **5** | Consumer intra-agent MCP + A2A client | `consumer/mcp_server.py`, refactored LLM loop | end-to-end purchase flow completes against Anvil-only (SDN_MOCK=true) |
| **6** | Catalog rescale + slot pool | new `inventory.txt`, rescaled catalog | tier 'medium' purchase yields slot binding `(pe1, e1-3, ce3)` |
| **7** | Real SDN demo | Makefile targets, ContainerLab integration, mock toggle | with clab deployed and `SDN_MOCK=false`: `verify_bandwidth(ce1, ce3, expected=5)` passes after a `medium` purchase |
| **8** | Multi-agent stretch | 2nd consumer container, prompt update | two consumers complete simultaneous purchases without interference |

Phases 2 and 3 can be parallelized after Phase 1 (different files); all others are strictly sequential.

The detailed step-by-step implementation plan (test list, file diffs, commit boundaries) will be produced after this spec is approved, in a separate document under `docs/superpowers/plans/`.

---

## 13. Future-work seams (out of scope for this plan)

This plan is intentionally architected to leave clean attachment points for the next steps the user has flagged:

| Future capability | Where it attaches in this plan |
|---|---|
| **Decentralized agent identity (DID / on-chain AgentCard)** | `provider/agent_card.py` and `consumer/agent_card.py` already centralize the card. Replace `AgentCard(...)` with a card resolved from a DID document or an on-chain registry. Vaziry et al. (cited in the paper) is the natural reference. |
| **ERC-4337 smart-account agents** | Today's `consumer.mcp_server.lock_payment` calls `_send_tx` which signs with the EOA. Swap that out for a UserOp builder + bundler client; the MCP tool signature stays the same. |
| **ERC-7710 / ERC-7715 delegation** | A new MCP tool `set_mandate(delegation_doc)` on the consumer. `lock_payment` checks the active mandate before signing. The on-chain side gets a delegation contract; `BandwidthEscrow` is unchanged. |
| **Verifiable credentials for the agent ↔ human binding** | An attestation issued (e.g., via EAS) that links the consumer EOA to a human DID. Consumer's `present_credential` carries the attestation alongside the NFT proof. |
| **A2A push notifications for stages 3+4** | a2a-sdk's `tasks/pushNotifications/*` methods. Consumer registers a webhook; provider posts when settlement completes. Eliminates the `await_settlement` polling loop. Requires the consumer to expose an HTTP server even when only making outbound calls today. |
| **Real x402 payment alternative** | Add a per-call `pay_per_request` MCP tool on the provider; consumer-side `request_with_payment` MCP tool. This becomes a sibling, not a replacement, of escrow — the paper's audit-trail benefit only applies to escrow. |

Each item is a separate spec; none of them require revisiting the architecture in this document.

---

## 14. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `a2a-sdk` API churn (current v1.0.2; project is young) | Medium | Medium | Pin to a specific minor version in `pyproject.toml`; isolate all SDK imports to two files (`provider/agent_executor.py`, `consumer/a2a_client.py`). |
| FastMCP in-memory transport semantics change | Low | Medium | Same isolation strategy: one creation site per agent. |
| ContainerLab not available on the reviewer's machine | High | Low | `SDN_MOCK=true` fallback (§8.3); `make demo` still produces a green run. |
| 1000 PPS cap interferes with verify_bandwidth | Medium | Medium | Catalog rescaled to ≤8 Mbps (§9). |
| 128-bit `agreement_id` vs. JSON precision | Medium | High | Already mitigated in current code: `agreement_id` serialized as string in the consumer cache, parsed via `int()` before web3 calls. Same convention preserved. |
| Provider restart during pending quote | Low | Medium | Document as a known limitation (consumer must `cancel` after deadline). Could be mitigated by persisting `pending_quotes` to disk; not in scope. |
| gNMI TLS verification disabled (`skip_verify=True`) | Low | Low | Inherited from brother repo (self-signed cert). Cert pinning is future work. |
| Race between two consumers requesting the same slot | Medium | Medium | Slot pool uses `fcntl.LOCK_EX`; first to acquire the lock wins, second sees no availability. Documented behavior. |
| Mismatched A2A SDK between Python versions | Low | Medium | This repo is `>=3.11`, brother repo is `>=3.13`. Confirm `a2a-sdk` supports 3.11 (it does per PyPI); if not, bump this repo to 3.13. |

---

## 15. Acceptance criteria (system-level)

After all phases, the following must be true:

1. `bash ../srl-gnmi-bandwidth-poc/scripts/deploy.sh && bash ../srl-gnmi-bandwidth-poc/scripts/push-config.sh && make up && SDN_MOCK=false make demo` — completes without error end-to-end.
2. The consumer LLM emits **only MCP tool calls**, never direct HTTP to the provider.
3. The provider receives **only A2A messages** from the consumer (verifiable by tcpdump or by removing `consumer/mcp_client.py` — there is no replacement that talks to provider's MCP).
4. After a `medium` purchase, `iperf3 -u -b 15M ce3→ce4` shows `5.0 ± 1.0 Mbps` measured (medium maps to slot `pe1/ethernet-1/3.0 / ce3`; brother repo Phase 2 verified `5.20 Mbps ± 0.20` for the same path at 5 Mbps target). For `small` (pe1/ethernet-1/2.0 / ce1) the verify path is ce1→ce2; for `large` (pe2/ethernet-1/2.0 / ce2) the path is ce2→ce1.
5. After NFT lease `durationSeconds` elapses, the slot is reclaimed on next inventory read; a subsequent `revoke_bandwidth` MCP call removes the gNMI policer and tc qdisc.
6. `pytest tests/ -q` is green.
7. The paper's six stages map 1:1 to the data flows in §6 of this document.
8. Spinning up a second consumer (`consumer-agent-2`) and running `make demo` from both terminals at once produces two ACTIVE agreements on different slots, neither failing.
9. `curl http://localhost:8002/.well-known/agent-card.json | jq` returns a valid `AgentCard` per `a2a-sdk`'s schema.
10. `provider/gateway.py` is deleted from `git ls-files` output.

---

## 16. Out of scope (reaffirmed)

- Identity primitives (DID, ERC-4337, ERC-7710), per §1.2.
- Paper edits, per §1.2.
- Contract changes, per §1.2.
- Persistent durable storage for pending quotes / inventory, per §10.4.
- Production-grade auth on A2A (mTLS, OAuth2), per §4.2.
- L2 / multi-chain, per §10.4.
- vLLM scale-up — Ollama stays.
- UI overhaul — Streamlit copy may change but the contract stays.

---

## 17. References

- Paper: `paper/main.tex`
- A2A protocol spec: `https://a2a-protocol.org/latest/specification/`
- A2A Python SDK: `https://github.com/a2aproject/a2a-python` (`a2a-sdk` on PyPI)
- FastMCP docs: `https://gofastmcp.com/`
- Brother repo: `https://github.com/musel25/srl-gnmi-bandwidth-poc`
- pygnmi: `https://github.com/akarneliuk/pygnmi`
- `paper/notes.md` §2 (Vaziry et al.) — primary reference for the future identity/x402 work
- Codebase reference: `CODEBASE_REFERENCE.md` (root)
