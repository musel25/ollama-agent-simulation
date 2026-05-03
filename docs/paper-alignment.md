# Diagnosis: Project ↔ Paper Alignment

> Goal: judge whether `ollama-agent-simulation` is good enough as the proof-of-concept that backs `paper/main.tex` ("Autonomous Agent-to-Agent Network Service Provisioning via Smart-Contract Escrow and Tokenized Authorization"), and list everything that has to change in either the paper or the code before submission.

---

## 1. Overall verdict

**The project is structurally a strong instantiation of the paper's thesis** — A2A as the only inter-agent channel, MCP as each agent's intra-agent toolset, smart-contract escrow + NFT credential atomic swap, and an NFT-gated SDN activation path. The six-stage workflow maps 1:1 to running code.

**However, the paper currently overstates two things and under-delivers on one.** Specifically:
1. It claims a **LangGraph state-machine agent** that the code does not implement (the consumer is a plain Ollama tool-calling loop).
2. It claims **Qwen3-4B** as the model, but the repo's working defaults are `qwen3:1.7b` / `ministral:3b`.
3. **§Evaluation defines RQ1/RQ2 but no numbers exist** — neither in the paper nor in the repo as a benchmark harness. The abstract already promises "reporting indicative latency and gas costs."

These three issues are blocking for an honest research paper, but all three are cheap to fix. The architectural core (RQ1 feasibility) is in fact already demonstrable end-to-end via `make demo` and `make demo-real`.

Verdict: **publishable after a focused alignment pass — perhaps 1–2 days of work**, mostly evaluation harness + one paper edit + cleanup. No architectural rework needed.

---

## 2. What aligns cleanly (no action required)

| Paper claim | Code location | Status |
|---|---|---|
| A2A is the inter-agent protocol; MCP is the intra-agent protocol | `consumer/a2a_client.py`, `provider/agent_executor.py` (A2A); `consumer/mcp_server.py`, `provider/mcp_server.py` (MCP) | ✅ exact |
| Asymmetric MCP toolsets (consumer: wallet/sign/lock/present; provider: mint/verify/swap/SDN) | Same files; tool lists in `docs/04-architecture.md §7` | ✅ exact |
| A2A is the only point of contact; everything else hidden behind MCP | LLM only sees consumer MCP; cross-agent calls wrapped in MCP tools that call `send_provider_action` | ✅ exact |
| Smart-contract escrow with atomic swap (§Architecture, "Payment") | `contracts/src/BandwidthEscrow.sol::deposit()` — checks-effects-interactions, atomic ETH↔NFT | ✅ exact |
| NFT credential, on-chain ownership-checkable, persists after redemption | `BandwidthNFT.sol` ERC-721 + on-chain `TokenMetadata`; `verify_credential_ownership` calls `ownerOf()` | ✅ exact |
| Gateway verifies token ownership before activation | `provider/agent_executor.py::_handle_activate` → MCP `verify_credential_ownership` (signed nonce + `ownerOf` + status check) | ✅ exact |
| SDN activation issues a QoS rule with a bandwidth cap | `provider/mcp_server.py::allocate_bandwidth` → `srl_bandwidth.allocate_bandwidth` (gNMI policer + `tc tbf` on CE) | ✅ exact |
| Auditability rationale for on-chain over x402 | `BandwidthEscrow.sol` events + Anvil log; project does **not** use x402, consistent with paper's design choice | ✅ exact |
| Six-stage acquisition (discovery, payment lock, credential issuance, swap, activation, consumption) | `make demo` + `make demo-real` walk all six | ✅ exact |
| "Atomic swap binds payment to authorization; gateway check binds authorization to activation" | `deposit()` reverts if anything fails; A2A `activate` handler refuses without valid `ownerOf` | ✅ exact |
| Foundry/Anvil EVM toolchain | `contracts/foundry.toml`, `anvil --block-time 1` | ✅ exact |
| Local Ollama with pinned model (operator-realistic, no third-party API) | `docker-compose.yml` runs `ollama` container; consumer talks to it | ✅ exact |

This is the heart of the paper, and the heart of the paper works.

---

## 3. Discrepancies — must adapt one side or the other

### 3.1 LangGraph claim vs. plain Ollama loop  ⚠️ **blocker**

**Paper §Prototype, "Stack rationale":**
> *"LangGraph models the six-stage workflow as an explicit state machine with typed transitions; emergent-dialogue frameworks such as CrewAI and AutoGen offer weaker workflow-progression guarantees for a deterministic pipeline."*

**Code reality:** The consumer is a 12-iteration Ollama tool-calling loop in `consumer/app.py::run_consumer` (`ollama.AsyncClient.chat(..., tools=...)`). There is no LangGraph anywhere — `pyproject.toml` does not import it, no `StateGraph` in the codebase. The "state machine" is implicit in (a) the Solidity FSM (`Status: NONE → REQUESTED → ACTIVE`), (b) the SlotPool, and (c) the fixed sequence of MCP tool names the LLM is steered toward by the system prompt.

**This is the single biggest credibility risk in the paper.** A reviewer who looks at the repo will see no LangGraph and may flag the paper for misrepresentation.

**Choose one:**
- **(A) Adapt paper [recommended].** Rewrite "Stack rationale → Agent framework" to describe what is actually used: an MCP tool-calling loop with the Ollama Python SDK, where state is enforced by (i) the on-chain status machine, (ii) the file-locked SlotPool, and (iii) constrained tool exposure (`browse_catalog → request_quote → lock_payment → await_settlement → present_credential`). Argue that the deterministic pipeline is enforced by the contract + tool boundary, *not* by an agent-framework graph. CrewAI/AutoGen comparison can stay (they would still be a worse fit), but drop the LangGraph claim. This is honest and arguably more interesting — the "state machine" lives in the chain, not in Python.
- **(B) Adapt code.** Wrap `run_consumer` in a LangGraph `StateGraph` with one node per workflow stage. ~half a day. Adds a dependency for marketing reasons. **Not recommended** unless reviewers are likely to demand it.

### 3.2 Model mismatch  ⚠️ **blocker (cosmetic but obvious)**

**Paper §Prototype:** *"Ollama runs **Qwen3-4B** locally with pinned model versions … a 4B-parameter model is sufficient for the bounded tool-calling load …"*

**Code reality:**
- `consumer/app.py:22` defaults `OLLAMA_MODEL` to `qwen3:4b` ✅
- `docker-compose.yml` pulls **both** `qwen3:4b` *and* `qwen3:1.7b`
- `.env.example:29` ships `OLLAMA_MODEL=qwen3:1.7b` ❌
- `README.md:84` instructs `ollama pull ministral:3b` and calls it the default ❌
- `Makefile:31` `make demo` uses `qwen3:4b` ✅

**Fix (either side):**
- **(A) Adapt code [recommended].** Make `qwen3:4b` the *only* default everywhere (`.env.example`, `README.md`, both Dockerfiles). Drop the `ministral:3b` reference from the README — or keep it as one tested alternative. Keep `qwen3:1.7b` as a "cheaper" option, but not the default.
- **(B) Adapt paper.** Say "Qwen3-1.7B / Qwen3-4B" and justify why a 1.7B model also works on this bounded tool-calling load (cite `belcakSmallLanguageModels2025`). This is fine if you want to show the smaller model also passes RQ1.

### 3.3 RQ1/RQ2 results missing  ⚠️ **blocker for an evaluation section**

**Paper §Evaluation:**
> *"RQ1 — End-to-end feasibility. Does the workflow complete, stage by stage, without human intervention after initial intent?"*
> *"RQ2 — Indicative cost. What are the approximate latency and gas costs for one successful run?"*

**Paper abstract:**
> *"… show that the workflow completes end-to-end, **reporting indicative latency and gas costs**."*

**Code reality:** No evaluation harness. `tests/` covers unit logic only. `make demo` proves RQ1 anecdotally but produces no structured report. No gas measurements anywhere — `forge` could emit them but is never invoked for that purpose. No latency timestamps captured per stage.

**Fix — both sides need work:**

1. **Add an `eval/` harness** in the repo:
   - `eval/run_trial.py` — drives `POST /chat` with a fixed prompt, captures wall-clock per stage:
     * t0: user prompt → first A2A call (discovery)
     * t1 → t2: `request_quote` round-trip
     * t2 → t3: `requestAgreement` mined
     * t3 → t4: `AgreementRequested` event observed by provider
     * t4 → t5: `mint` + `deposit` mined
     * t5 → t6: A2A `activate` returns
     * t6 → t7: SDN policy installed (verifiable with iperf in `demo-real`)
   - `eval/gas_report.sh` — parses `forge inspect` / `cast receipt` for `requestAgreement`, `mint`, `deposit`, `cancel` gas. (Foundry already has built-in gas reporting — `forge test --gas-report` if you add 1–2 contract tests; or `cast tx <hash>` on demo-run hashes.)
   - `eval/aggregate.py` — runs N=20 trials with `SDN_MOCK=true` for stable LLM-decoupled latencies, plus N=5 with `SDN_MOCK=false` for the SDN tail.
2. **Insert a results table into the paper.** Recommended shape for §Evaluation (replaces the bullet list):

   | Stage | Median (ms) | p95 (ms) | Gas (units) |
   |---|---|---|---|
   | Discovery (A2A get_catalog) | … | … | — |
   | Quote (A2A request_quote) | … | … | — |
   | requestAgreement (consumer → chain) | … | … | … |
   | mint + deposit (provider → chain, atomic swap) | … | … | … |
   | activate (A2A → ownerOf check) | … | … | — |
   | SDN install (gNMI + tc) | … | … | — |
   | **Total (intent → flow)** | … | … | … |

   Even N=20 on Anvil with one SR Linux node is enough for "indicative."
3. **RQ1 is already provable** — adding `make eval` that runs the harness and exits non-zero on stage failure makes it reproducible.

### 3.4 PENDING state in paper sequence vs. code  📝 minor

`BandwidthEscrow.sol` has an explicit comment: *"the paper describes a PENDING state between provider deposit and swap. Here the swap is atomic inside deposit(), so PENDING is never externally observable."*

The paper sequence diagram (`d2_sequence_6stages.png`) shows "Swap" as Stage 4 separately. The figure caption already covers this: *"Arrows 4 and 5 are initiated by the smart contract, not the agents."* — which is accurate. **No change needed**, but you could make the diagram caption sharper: *"Stage 4 happens atomically inside `deposit()`; there is no externally observable PENDING state."*

### 3.5 Future-work items that the code already addresses  📝 minor

Paper §Conclusion lists:
- *"concurrent acquisitions"* — partly addressed by the multi-consumer compose profile (`docker compose --profile multi-consumer up`) and the fcntl-locked `SlotPool`. Worth promoting from "future work" to either a sentence in §Prototype ("the prototype supports concurrent acquisitions via a file-locked slot pool") or keeping in future work but qualifying as "production-grade concurrency under provider horizontal scaling."
- *"failed-provider refund paths"* — partly addressed by `BandwidthEscrow.cancel()` (consumer can cancel; anyone can cancel after 1h deadline). Honest framing: "manual cancel exists; automatic refund on provider crash is future work."
- *"expired-credential rejection"* — addressed by `provider/expiry.py` background sweep + `verify_credential_ownership` checking agreement status. Should move out of future work.

**Recommendation:** rewrite the future-work paragraph to claim more credit and move the goalposts: "concurrent acquisitions across horizontally-scaled providers (single-process today)", "automatic refund on provider crash (manual cancel today)", "DID/verifiable-credential identity layer (Ethereum-address identity today)", and the genuinely-still-open transferable-credential delegation use case.

### 3.6 Closest related work — `bandaraAgenticAIControl2026` framing  📝 minor

The paper differentiates from Bandara et al. on two dimensions: agents are general-purpose (not orchestration components) and trading is escrow-based (not market-spot). Code is consistent. **No change.** Optional: a one-line table row showing "specialized vs general-purpose agents" + "spot market vs escrow" would strengthen §Introduction; the commented-out comparison table at lines 104–121 of `main.tex` could be uncommented and extended to include Bandara.

---

## 4. Things to clean up in the repo before submission

These won't change the paper but will affect a reviewer who clones the repo.

1. **Delete legacy dead code.** `app.py`, `consumer_agent.py`, `provider_server.py`, `catalog.txt`, `agreements.json` are explicitly marked dead in `docs/04-architecture.md §1` and §11. They will confuse anyone trying to reproduce the paper's prototype. The `chore: legacy purge` PR is two `git rm` commands.
2. **Pin the model in `.env.example`.** As above, `qwen3:4b` should be the documented default if the paper says Qwen3-4B.
3. **Add `make eval`** that runs the harness from §3.3 and produces a `eval/results.json` (and a markdown table the paper imports).
4. **Add a tiny `forge test` for `BandwidthEscrow`** so `forge test --gas-report` produces canonical gas numbers for the table — gas measured from a unit test is more reproducible than gas measured from a demo run.
5. **`README.md` "Does not"** says *"Enforce bandwidth at the network layer (no QoS, no traffic shaping, no real hardware)"* — this is **wrong** since the SDN integration landed. The `make demo-real` path with ContainerLab + SR Linux + `tc` *does* enforce bandwidth. Update this list to match reality (move QoS/traffic-shaping into "Does:").
6. **Squash the `endpoint` field semantics.** NFT metadata stores `clab://{pe}/{subinterface}` informationally; activation actually uses `slot_pool.lookup(agreement_id)`. Either drop the `endpoint` field from the NFT (simpler) or make activation use it (truer to the paper's "consumer presents the NFT to the provider gateway"). For the paper as written, the current code is fine; just don't claim the endpoint is the activation address.

---

## 5. Things the paper says correctly that need a one-line cite-back-to-code

For reviewer trust, consider a paragraph or footnote in §Prototype ("What is real") that links each claim to a file path:

| Paper claim | Code |
|---|---|
| Wallet signing | `consumer/mcp_server.py::sign_message` (`Account.sign_message`) |
| On-chain execution | `provider/app.py::_handle_agreement`, `consumer/app.py::lock_payment` |
| NFT minting | `provider/mcp_server.py::mint_credential` → `BandwidthNFT.mint` |
| Ownership check | `provider/mcp_server.py::verify_credential_ownership` → `ownerOf()` |
| Gateway verification logic | A2A `activate` skill, `provider/agent_executor.py::_handle_activate` |
| Activation command issued to controller | `srl_bandwidth.allocate_bandwidth` (gNMI policer push) |

A reviewer who can `Ctrl-F` these names and find them lives a happier life.

---

## 6. Out-of-scope items the paper correctly disclaims (no action)

These are explicitly listed as "out of scope" or "limitations" and the code is consistent:

- **Economic value, provider reputation, legal enforcement** — disclaimed in §Prototype.
- **Physical-bandwidth guarantees, oracle delivery verification** — disclaimed in §Prototype + §Discussion.
- **Pre-intent autonomy** (wallets, contract addresses, offer formats are preconfigured) — disclaimed in §Discussion.
- **DID / verifiable credentials** — README says identity = Ethereum address; paper does not claim DID. Aligned.
- **Per-packet / microsecond-scale control** — disclaimed in §Discussion via `afrazBlockchainSmartContracts2023`.
- **Multi-round price negotiation** — disclaimed in README; paper does not claim it.

---

## 7. Recommended order of operations

Cheapest path to a defensible submission, in order:

1. **Decide §3.1 (LangGraph)** — pick (A) edit paper. ~30 min text change.
2. **Decide §3.2 (model)** — pick (A) standardize on `qwen3:4b` everywhere. ~10 min repo change, no paper change.
3. **Repo cleanup §4.1, §4.2, §4.5** — delete legacy, pin default, fix README "does not" list. ~20 min.
4. **Build the `eval/` harness §3.3** — half a day. Run it, paste numbers into §Evaluation table, fill in the abstract's "indicative latency and gas costs" with real values.
5. **Reframe future work §3.5** — 15 min text change.
6. **Optional polish §3.4, §3.6, §5** — sequence-figure caption, comparison table, code-cite footnote. 1 hour.

Total: roughly 1–2 working days of focused effort. After this, the paper and the repo tell the same story and the §Evaluation section has actual evidence.

---

## 8. One-line summary

> The architectural core (A2A + per-agent MCP + atomic on-chain swap + NFT-gated SDN activation) is faithfully implemented and is the paper's strongest contribution. The blockers are: paper claims LangGraph that doesn't exist (rewrite that paragraph), paper picks a model the repo doesn't default to (standardize on Qwen3-4B), and §Evaluation has no numbers (add a small benchmark harness). After those three fixes, the paper is honest and reproducible.
