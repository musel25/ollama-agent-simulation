# Agentic Telco as Platform — Two-Instance Restructure (paper + slides)

**Date:** 2026-05-11
**Status:** design approved, pending spec review
**Scope:** paper restructure into a *new* `.tex` file (leave `main.tex` untouched) + a *new* slides `.tex` file (leave `slides.tex` untouched) + an upgraded applicability table. Assumes the telemetry-configuration provider agent / activation machinery already exists (per author); if it does not, that implementation is a separate effort tracked elsewhere.

---

## 1. Goal

Reframe the paper from *"an architecture for autonomous agent-to-agent provisioning of bounded/gated/coarse-grained network resources, demonstrated with bandwidth"* to *"an architecture for autonomous agent-to-agent provisioning of bounded/gated/coarse-grained network **services**, spanning two **capability classes** (capacity allocation; configuration authority), validated with one proof-of-concept per class — bandwidth allocation and a token-gated telemetry-configuration grant."*

The narrative anchor is **"agentic telco as platform"**: a telco exposes network capabilities; autonomous agents acquire them from one another without human mediation; a smart contract supplies the three things agent-to-agent commerce otherwise lacks — escrowed settlement, a transferable authorization token, and a tamper-evident record.

**Non-goals:**
- Do not edit `main.tex` (it remains the current single-PoC version).
- Do not claim universality ("works for *all* network services"). The claim is bounded to the three-property class, characterized analytically (applicability table) and validated empirically (two PoCs).
- Do not invert the logic ("the architecture generalizes the two PoCs"). The architecture and its three-property scoping come first; the PoCs are *instances* that validate it.
- Do not (in this spec) implement the telemetry PoC code — assumed to exist.

## 2. Files touched

| File | Action |
|---|---|
| `paper/main-v2.tex` | **new** — full restructured paper (copy of `main.tex` as starting point, then restructured per §4) |
| `paper/main.tex` | **untouched** |
| `paper/slides-v2.tex` | **new** — restructured slides (copy of `slides.tex` as starting point, then restructured per §5) |
| `paper/slides.tex` | **untouched** |
| `paper/references.bib` | add only if new citations are needed (e.g., a capability-security reference for the reference-monitor framing — optional) |
| `paper/diagrams/` | new conceptual figure: "agentic telco as platform" overview (three layers × four elements × six-stage arrow forking at stage 6). May start as a TikZ block inside the `.tex` or a placeholder pending a drawn asset. |

## 3. The unifying model (the content being encoded)

### 3.1 Architecture — three layers, four elements
- **Communication (agent layer):** A2A = inter-agent (discover, offer, quote, activate); MCP = intra-agent (wallet, contract, controller tools). *Invariant across instances.*
- **Payment (chain layer):** escrow locks consumer funds vs. `agreementId`. *Invariant.*
- **Authorization (chain layer):** NFT = **capability token**; metadata encodes the bounded entitlement. *Metadata varies per instance.*
- **Activation (network layer):** gateway = **reference monitor** — checks `ownerOf` + expiry + status + (requested scope ⊆ token scope), then issues the network action. *Activation primitive varies per instance.*

### 3.2 Workflow — six stages, stages 1–5 capability-agnostic
1. Discovery & Selection → `agreementId`
2. Payment Lock (escrow deposit vs. `agreementId`)
3. Credential Issuance (mint NFT bound to `agreementId`)
4. Swap (contract atomically exchanges payment ↔ NFT — contract-driven)
5. Activation (consumer presents NFT; gateway runs the reference-monitor check)
6. **Consumption — class-specific:** capacity → consumer runs traffic; configuration authority → consumer receives the configured stream

### 3.3 Two capability classes (the explicit use cases)

| | **Class A — Capacity allocation** | **Class B — Configuration authority** |
|---|---|---|
| What's sold | a reserved slice of forwarding-plane resource | a bounded right to install state in the operator's infra |
| Gating point | **dataplane** (customer-edge forwarding node) | **management plane** (device config/telemetry interface) |
| Activation primitive | QoS / policer / flow-rule push (gNMI + `tc`) | device-appropriate config push — the provider agent picks the dialect (SR Linux subscription, Cisco XR config, …) |
| Credential metadata | `(agreementId, mbps, duration, startTime, endpoint)` | `(agreementId, pathSet, sampleInterval, duration, startTime, deviceSet)` |
| "Coarse-grained" because… | on-chain settlement latency sets the floor | the business model is windowed (diagnostic / incident-scoped instrumentation) |
| Trust surface | buyer consumes output **at the edge** | buyer's agent acts **inside the management boundary** → gateway scope-check does real work; resource-side `ownerOf()` matters more |
| Audit value | inter-operator **settlement** evidence | **accountability/forensics** — who was authorized to configure, when |
| Example services | **bandwidth (demonstrated)**, slices, advance reservations, VPN tunnels, MEC bundles, wholesale capacity, scrubbing admission | **telemetry subscription (demonstrated)**, ACL installs, flow-rule grants |

### 3.4 Three derived properties (the scoping test — unchanged)
bounded entitlement (encodable in the credential) · a gating point (admission node that checks ownership) · coarse granularity (seconds-to-hours). A service is *in scope* iff all three hold; the applicability map is this test applied.

### 3.5 Invariant vs. varying (the "it generalizes" claim, made precise)
- **Invariant across both instances:** escrow + atomic-swap contract, mint, gateway ownership/expiry/status check, A2A negotiation, MCP wallet/contract toolsets, the six-stage workflow.
- **Varies, and *only* this varies:** NFT metadata struct, provider catalog tiers, the stage-6 activation primitive (+ the gateway's post-check action), the verification probe (iperf3 vs. gNMI Subscribe).

### 3.6 The breadth argument (deductive, not inductive)
1. **Claim:** the pattern applies to services satisfying the three properties — *not* all network services.
2. **Analytical evidence:** the applicability table — candidate network services classified; in-scope ones reduce to filling in the variation-point values.
3. **Empirical evidence:** two PoCs, one per capability class, confirm the instantiation procedure works and the invariant machinery is genuinely invariant.
4. **Therefore:** other in-scope services are *predicted, not demonstrated*; services failing any of the three properties are explicitly out of scope.

## 4. Paper restructure — section by section (`main-v2.tex`)

Start from a copy of `main.tex`; apply:

- **Title:** keep "...Network Service Provisioning..." (the word "service" stays). Introduce "capability" in the abstract/body as the precise term.
- **Abstract:** name the abstraction (bounded/gated/coarse-grained network capabilities — capacity allocations *or* configuration-authority grants); state two instances spanning both classes; end-to-end completion + indicative latency/gas for both.
- **§1 Introduction:**
  - Building-blocks paragraph: unchanged.
  - The question: generalize to "network-capability acquisition — capacity allocation *or* bounded configuration authority."
  - Contributions: (1) unchanged pattern; (2) *generalized* — characterization of the network-capability class: three properties + two-class split + applicability map; (3) *expanded* — two PoCs, one per class, showing the reused machinery is invariant and only metadata + activation primitive vary.
  - Plant the capability-token / reference-monitor framing (full treatment in §6).
- **§2 Scenario and Workflow:** open with the abstract scenario; develop two concrete scenarios (bandwidth, telemetry-config) in parallel; six stages stay verbatim; note stages 1–5 are class-invariant, only stage 6 forks.
- **§3 Architecture:**
  - Communication / Payment: unchanged.
  - Authorization: add the capability-token framing (bounded grant of authority, not merely a payment receipt; gateway check is the reference-monitor step for Class B).
  - Activation: **forks** into Class A (dataplane gating, QoS push via gNMI + `tc`) and Class B (management-plane gating, scope-checked device config push, agent picks the per-device dialect — call this out as where the agent does non-mechanical work).
  - Composition: add one sentence — the gateway check does double duty (binds authz→activation *and*, for Class B, confines the grant to declared scope).
  - Applicability: reorganize natural-fits by the two classes; telemetry-config moves from *predicted* to *demonstrated*; add the "coarse-grained holds for a different reason in Class B (business-model-windowed, not settlement-latency)" sentence.
- **§3.x NEW — Applicability table** (the variation-point mini-survey): ~5–6 representative services × {capability class, credential metadata, gating point, activation primitive, in-scope? / which property fails}. Include at least: bandwidth (demo, A), network slice (predicted, A), site-to-site VPN tunnel (predicted, A), telemetry subscription (demo, B), ACL install (predicted, B), always-on broadband (out — identity-bound entitlement), real-time control loop (out — granularity). This table *is* contribution #2 in one view.
- **§4 Prototype:**
  - Open with shared-machinery vs. per-instance split (verbatim from §3.5).
  - **Instance A — Bandwidth:** current §4 content, condensed (stack: Anvil, contract, agents, gNMI→SR Linux, containerlab; what's real: signing, on-chain, mint, ownership check, gNMI to real dataplane, iperf3 probe).
  - **Instance B — Telemetry configuration:** compact. NFT metadata struct; catalog tiers (e.g. "interface counters @5s/1h", "BGP-neighbor state @1s/30m"); activation = provider agent emits device-appropriate telemetry config (SR Linux `sensor-group` + `persistent-subscription` via gNMI Set; would emit Cisco XR config for an XR device); verification = short gNMI Subscribe confirming ≥N samples over the window; what's real / what's mocked mirroring Instance A; one line on the agent doing dialect selection.
  - Stack rationale: unchanged; **check** whether the per-router dialect reasoning still fits "3B model, no tool-calling" — if yes, say so explicitly (stronger result); if not, note the change.
  - Multi-provider discovery: unchanged.
  - What's out of scope: unchanged + add "per-subscription billing, multi-device fan-out, real telemetry consumers."
- **§5 Evaluation:**
  - RQ1 — end-to-end feasibility: now "do *both* workflows complete, stage by stage, post-intent?" Report per-instance.
  - RQ2 — indicative cost: latency + gas for *each* instance; note gas ≈ identical (same escrow/mint/swap), activation latency differs.
  - **RQ3 (NEW) — scope enforcement:** the gateway rejects an out-of-scope config request (Class B). Cheap; it's the concrete evidence behind the reference-monitor claim. Include it.
- **§6 Discussion and Limitations:**
  - Audit byproduct: **split the value story** — Class A → inter-operator settlement evidence; Class B → accountability/forensics record (who was authorized to configure, when).
  - Delivery trust: keep the point; **strengthen the caveat for Class B** — buyer acts inside the management boundary, "trust ≡ any API subscription" is too glib there, gateway scope-check does more work, resource-side `ownerOf()` matters more — tie the future direction to Instance B.
  - **NEW — threat model / misbehavior** paragraph: credential replay, out-of-scope config requests, slot double-claim; what the design handles (atomic swap prevents payment/credential defection; gateway scope-check prevents out-of-scope activation) and what it doesn't yet (concurrent claims, refunds, expiry rejection — already future work, now with the security framing).
  - Autonomy post-intent: unchanged.
  - Latency / coarse-grained: unchanged + the Class-B-different-reason sentence.
  - Scope: unchanged (metered / multi-tenant / always-on / open / common-carrier still out or adaptable). Add the explicit non-universality sentence: "We do not claim universality; the pattern covers the class of bounded, gated, coarse-grained network services — characterized analytically (the applicability table) and validated empirically (two instances spanning both capability classes)."
- **§7 Conclusion:** reword to "two instances, one per capability class"; keep predicted-fits list; keep future-work bullets (concurrent acquisitions, refund paths, expiry rejection, sub-tokenized decomposition) — note the threat-model framing makes these less optional.
- **Figures:**
  - NEW conceptual figure — "agentic telco as platform" overview: three layers down the side, four elements, six-stage arrow across, stage 6 forking into the two class-specific activation primitives. Augments/replaces `d1_overview_hub`. Start as TikZ-in-`.tex` or placeholder.
  - `d2_sequence_6stages`: stays; add a caption note that arrows 1–5 are class-invariant.
  - `d3_architecture_stack`: stays; minor caption tweak to mention the two activation primitives.

## 5. Slides restructure (`slides-v2.tex` — new file, `slides.tex` untouched)

Start from a copy of `slides.tex`; mirror the paper's new spine:
- Title/intro: "agentic telco as platform" framing.
- One slide for the three-layer / four-element architecture.
- One slide for the six-stage workflow with the stage-6 fork highlighted.
- One slide for the two capability classes (the §3.3 comparison table, trimmed).
- One slide for the applicability table (trimmed).
- Two slides (or one split slide) for the two PoCs — emphasize shared machinery vs. per-instance variation.
- Evaluation slide: RQ1/RQ2/RQ3 results per instance.
- Discussion slide: the doubled value story + threat model + non-universality.

## 6. Open items / risks
- **Page budget** (two-column, ~6 pp): the second instance + new table + RQ3 + threat-model paragraph add length. Mitigation: present Instance B as "everything reused except these three things"; keep the applicability table to ~6 rows; threat model is one tight paragraph.
- **The conceptual overview figure** needs a real drawn asset eventually; TikZ placeholder acceptable for now.
- **Does the telemetry PoC actually exist / run?** Spec assumes yes (per author). If "what's real" for Instance B can't be backed by a real run, either (a) build the minimal real path, or (b) honestly mark Instance B's activation as demonstrated-in-mock with the real path specified — but that weakens the "two demonstrated instances" claim and should be a conscious call.
- **`main-v2.tex` / `slides-v2.tex` filenames** — placeholders; rename if the author prefers something else.
