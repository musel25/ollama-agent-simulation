# Agentic Telco Two-Instance Restructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a restructured paper (`paper/main-v2.tex`) and slides (`paper/slides-v2.tex`) that reframe the architecture as a general pattern for bounded/gated/coarse-grained network *services* spanning two capability classes (capacity allocation; configuration authority), validated by two PoCs (bandwidth; telemetry-configuration), with an explicit applicability table — leaving the originals `main.tex` and `slides.tex` untouched.

**Architecture:** This is a LaTeX/prose task, not a code task. "Test" = the document compiles cleanly via `latexmk` with no *new* errors and the relevant section renders. Each task writes one section/figure, compiles, verifies, commits. `main-v2.tex` starts as a byte copy of `main.tex` and is restructured in place section by section; `slides-v2.tex` likewise from `slides.tex`. Source of truth for all content decisions: `docs/superpowers/specs/2026-05-11-agentic-telco-two-instance-design.md`.

**Tech Stack:** LaTeX (`article`, `biblatex`+`biber`, `pifont`, `booktabs`), `latexmk`, build dir `.out/`. Work happens in `/home/musel/Github/ollama-agent-simulation/paper/` (its own git repo, nested inside `ollama-agent-simulation`).

**Build command (used as the "test" throughout):**
```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; `.out/main-v2.pdf` produced; `.out/main-v2.log` contains no `! ` LaTeX error lines and no `Undefined control sequence`. (Overfull-hbox warnings are acceptable.) For slides, substitute `slides-v2.tex`.

**Commit convention:** the paper repo uses terse messages (`update`, `steps`, …) and the user's memory says keep things simple — use short conventional-ish messages like `feat(paper-v2): restructure §3 architecture for two capability classes`. End commit messages with the `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` line. Commit on `master` (the repo's working branch — it has no feature-branch convention and `main.tex`/`slides.tex` are untouched so there is no risk to stable content).

**Reference — current section structure of `main.tex`:** Introduction (itemize: motivation / building-blocks paragraph / the question / contributions enumerate) · Scenario and Workflow (consumer-needs-bandwidth + six-stage enumerate) · Architecture (itemize: communication / payment / authorization / activation / composition / applicability) · Prototype (itemize: bandwidth-as-instance / stack / stack-rationale / multi-provider-discovery / what-is-real / what-is-out-of-scope) · Evaluation (RQ1, RQ2) · Discussion and Limitations (itemize) · Conclusion (itemize) · `\printbibliography`. Three `figure*` blocks: `diagrams/d1_overview_hub`, `diagrams/d2_sequence_6stages`, `diagrams/d3_architecture_stack`.

---

### Task 1: Scaffold `main-v2.tex`

**Files:**
- Create: `paper/main-v2.tex` (byte copy of `paper/main.tex`)

- [ ] **Step 1: Copy the file**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && cp main.tex main-v2.tex
```

- [ ] **Step 2: Compile to establish a clean baseline**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; `.out/main-v2.pdf` exists; no `! ` errors in `.out/main-v2.log`.

- [ ] **Step 3: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add main-v2.tex
git commit -m "chore(paper-v2): scaffold main-v2.tex from main.tex

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Title + abstract

**Files:**
- Modify: `paper/main-v2.tex` (the `\title{...}` block ~lines 27-30 and the `abstract` environment ~lines 47-49)

- [ ] **Step 1: Edit the title block**

Keep the word "Service". Replace the `\title{...}` content with:

```latex
\title{\vspace{-1em}
Autonomous Agent-to-Agent Network Service Provisioning\\
via Smart-Contract Escrow and Tokenized Authorization
}
```

(This is unchanged from `main.tex` — the title stays. Included so the task is explicit: do **not** alter it.)

- [ ] **Step 2: Replace the abstract**

Replace the `abstract` body with:

```latex
We propose an architecture for autonomous agent-to-agent acquisition of
\emph{bounded, gated, coarse-grained} network services. A consumer agent
locks payment in a smart contract; a provider agent allocates the service
and issues an NFT authorization credential; a gateway converts the
credential into network activation. We characterize the service class the
pattern targets---three derived properties and two capability classes:
\emph{capacity allocation} (a reserved slice of forwarding-plane resource,
gated at the dataplane) and \emph{configuration authority} (a bounded right
to install state in the provider's infrastructure, gated at the management
plane). We instantiate the architecture once per class---a bandwidth
allocation and a token-gated telemetry-configuration grant---and show
end-to-end completion with indicative latency and gas costs for both.
```

- [ ] **Step 3: Compile**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; no new errors.

- [ ] **Step 4: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add main-v2.tex
git commit -m "feat(paper-v2): abstract reframed for two capability classes

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: §1 Introduction

**Files:**
- Modify: `paper/main-v2.tex` (the `\section{Introduction}` itemize, ~lines 55-106)

- [ ] **Step 1: Keep the motivation bullet and the building-blocks bullet unchanged.** (The first two `\item`s — agents executing workflows; the long building-blocks paragraph citing MCP/A2A/x402/SDN/slice-sharing/`chungAdvanceReservationAccess2018`/`bandaraAgenticAIControl2026`. Do not touch them.)

- [ ] **Step 2: Replace the "this paper asks" bullet** with:

```latex
  \item This paper asks: \emph{can two agents complete an end-to-end
        network-service acquisition---where the service is a reserved
        capacity allocation or a bounded grant of configuration authority
        over the provider's infrastructure---with payment escrowed on-chain,
        an NFT credential exchanged for that payment, and the credential
        triggering provider-side network activation?} The NFT is treated as
        a \emph{capability}: a bounded grant of authority, not merely a
        payment receipt; the provider gateway is the reference monitor that
        admits a flow (or a configuration) only against a valid, in-scope
        credential.
```

- [ ] **Step 3: Replace the contributions enumerate** with:

```latex
  \item Contributions:
        \begin{enumerate}
          \item An architectural pattern that separates and connects agent
                communication, escrowed payment, tokenized authorization, and
                SDN/management-plane activation, applicable to bounded, gated,
                coarse-grained network services.
          \item A characterization of the network-capability class to which
                the pattern applies---three derived properties, a two-class
                split (capacity allocation vs.\ configuration authority), and
                an applicability table mapping representative network services
                to their credential metadata, gating point, and activation
                primitive, or to the property they fail.
          \item Two proof-of-concept instances, one per capability class---a
                bandwidth allocation and a token-gated telemetry-configuration
                grant---demonstrating that the reused machinery (escrow, mint,
                atomic swap, gateway check, A2A/MCP, the six-stage workflow) is
                invariant across both, and that only credential metadata and
                the gateway-side activation primitive vary.
        \end{enumerate}
```

- [ ] **Step 4: Compile**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; no new errors.

- [ ] **Step 5: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add main-v2.tex
git commit -m "feat(paper-v2): rewrite intro question + contributions

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: §2 Scenario and Workflow

**Files:**
- Modify: `paper/main-v2.tex` (the `\section{Scenario and Workflow}` itemize, ~lines 127-152)

- [ ] **Step 1: Replace the first bullet (the bandwidth-specific scenario opener)** with:

```latex
  \item A consumer agent needs a temporary, bounded network service. A
        provider agent advertises a machine-readable offer---entitlement,
        duration, price, and slot availability---and returns per-quote details
        (an agreement identifier and an activation endpoint) when the consumer
        requests a quote against a chosen tier. We develop two concrete
        scenarios in parallel: \textbf{(A)} a \emph{bandwidth allocation}, in
        which the entitlement is a rate cap delivered at the customer edge;
        and \textbf{(B)} a \emph{telemetry-configuration grant}, in which the
        entitlement is the right to install a telemetry subscription
        (a path set, a sample interval, a device set) on the provider's
        network and to receive the resulting stream.
```

- [ ] **Step 2: Keep the six-stage enumerate verbatim, but append a closing sentence after the enumerate** (inside the same `\item` block, after `\end{enumerate}`):

```latex
        Stages 1--5 are capability-agnostic. Only stage~6 (Consumption)
        differs by class: in scenario~A the consumer runs traffic across the
        rate-capped link; in scenario~B the consumer opens a streaming
        subscription and receives telemetry samples.
```

- [ ] **Step 3: Update the figure captions** for `d1_overview_hub` and `d2_sequence_6stages`:
  - `d1_overview_hub` caption → `System overview: consumer and provider agents negotiate via A2A, lock payment and mint an NFT on-chain, and the blockchain credential triggers network activation---a dataplane QoS rule (capacity) or a management-plane configuration push (configuration authority).`
  - `d2_sequence_6stages` caption → append: ` Arrows 1--5 are identical for both capability classes; arrows 4 and 5 are initiated by the smart contract, not the agents.`

- [ ] **Step 4: Compile**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; no new errors.

- [ ] **Step 5: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add main-v2.tex
git commit -m "feat(paper-v2): generalize scenario section, two parallel scenarios

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: §3 Architecture — authorization, activation fork, composition

**Files:**
- Modify: `paper/main-v2.tex` (the `\section{Architecture}` itemize: `Communication layer` / `Payment` bullets stay; rewrite `Authorization` and `Activation` bullets; tweak `Composition`; the `Applicability` bullet is handled in Task 6)

- [ ] **Step 1: Leave the `Communication layer` and `Payment --- smart-contract escrow` bullets unchanged.** (The asymmetric-MCP-toolsets paragraph and the auditability/atomicity paragraph — do not touch.)

- [ ] **Step 2: Replace the `Authorization --- NFT credential` bullet** with:

```latex
  \item \textbf{Authorization --- NFT credential as capability token.} The
        NFT~\cite{entrikenERC721NonFungibleToken2018} is the object the
        gateway acts on, and it is a \emph{capability} in the access-control
        sense: a bounded, transferable grant of authority whose metadata
        encodes the entitlement (a rate cap and endpoint for capacity; a path
        set, sample interval, and device set for configuration authority). The
        principle that network admission requires a credential bound to the
        flow---not merely a logged agreement---is established in prior SDN
        reservation work~\cite{chungAdvanceReservationAccess2018}; the present
        design extends it by making that credential a transferable on-chain
        token issued through an autonomous agent workflow. Separating it from
        the payment receipt reflects an operational requirement: the gateway
        must decide whether to activate a flow---or apply a configuration---
        without re-querying or trusting the payment channel. Token ownership is
        checkable by anyone with read access to the chain; the gateway needs
        no shared secret with the contract or the consumer. The token persists
        after redemption, marked activated for audit, rather than disappearing
        as a transient signature in a log. Transferability is preserved as a
        design property (an agent could delegate consumption rights), though
        the present prototypes do not exercise it.
```

- [ ] **Step 3: Replace the `Activation --- gateway and SDN` bullet** with a forked version:

```latex
  \item \textbf{Activation --- gateway as reference monitor.} The provider
        gateway verifies token ownership, service validity, expiration,
        activation status, and that the requested entitlement is within the
        token's scope; only then does it issue the corresponding network
        action. The activation primitive is the one component that varies by
        capability class:
        \begin{itemize}
          \item \emph{Capacity allocation --- dataplane gating.} The gateway
                programs a QoS rule (a bandwidth cap) on the customer-edge
                forwarding node; the gating point is the dataplane. The same
                pattern accommodates flow rules, ACLs, or slice activations.
          \item \emph{Configuration authority --- management-plane gating.}
                The gateway issues a bounded configuration to the device's
                management interface---here, a telemetry sensor-group and
                subscription scoped to the token's path set, interval, and
                device set; the gating point is the management plane. The
                provider agent selects the device-appropriate dialect (e.g.\
                a gNMI \texttt{Set} against SR Linux, a configuration push to
                Cisco IOS-XR); this dialect selection is the one place in the
                workflow where the agent does non-mechanical work, and it is
                the value the agent abstraction adds over a fixed API.
        \end{itemize}
        In the prototypes the gateway role is co-located with the provider
        agent's A2A \texttt{activate} handler; the SDN principle of
        programmatic, software-driven configuration~\cite{mckeownOpenFlow2008}
        is preserved without a centralized controller, which is replaceable in
        production deployments.
```

- [ ] **Step 4: Edit the `Composition` bullet** — keep its existing text, append one sentence before the closing `}`:

```latex
        The gateway check does double duty: it binds authorization to
        activation, and---for configuration authority---confines the grant to
        its declared scope, acting as a reference monitor over a write into the
        provider's management plane.
```

- [ ] **Step 5: Update the `d3_architecture_stack` caption** → `Three-layer architecture: AI agents communicate via A2A; the blockchain layer handles escrow and NFT capability credentials; the network layer enforces the activation primitive---a dataplane QoS rule or a management-plane configuration---via the provider gateway.`

- [ ] **Step 6: Compile**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; no new errors. Note: nested `itemize` inside an `itemize` `\item` is fine with the `enumitem` setup already in the preamble.

- [ ] **Step 7: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add main-v2.tex
git commit -m "feat(paper-v2): capability-token framing + forked activation in architecture

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: §3 Applicability bullet + applicability table

**Files:**
- Modify: `paper/main-v2.tex` (replace the `Applicability` bullet ~lines 236-256; add a `table*` after the `d3_architecture_stack` figure)

- [ ] **Step 1: Replace the `Applicability` bullet** with:

```latex
  \item \textbf{Applicability.} The pattern targets services with three
        properties, each derived from a specific component: \emph{bounded
        entitlement} (capacity, time, or scope encodable in the credential), a
        \emph{gating point} (an admission node---dataplane or management
        plane---that checks ownership before enabling a flow or applying a
        configuration), and \emph{coarse granularity} (allocation horizon of
        seconds to hours). The granularity bound has two sources depending on
        the class: for capacity allocation it is the latency floor of on-chain
        settlement; for configuration authority it is the business model
        (windowed, diagnostic, or incident-scoped instrumentation rather than
        permanent state). A service is in scope iff all three properties hold;
        Table~\ref{tab:applicability} applies this test to representative
        network services---naming, for each in-scope service, its capability
        class, credential metadata, gating point, and activation primitive,
        and for each out-of-scope service, the property it fails. The two PoCs
        instantiate the simplest natural fit in each class; other in-scope
        services are \emph{predicted} by the same instantiation, not
        \emph{demonstrated}. We do not claim universality: services failing any
        of the three properties---real-time control loops, always-on
        subscriber broadband, open best-effort connectivity, regulated
        common-carrier services---fall outside the architecture's
        applicability.
```

- [ ] **Step 2: Add the applicability table** immediately after the `\end{figure*}` that closes `d3_architecture_stack`:

```latex
\begin{table*}[t]
\centering
\caption{Applicability of the pattern to representative network services. ``Class A'' = capacity allocation (dataplane gating); ``Class B'' = configuration authority (management-plane gating). Status: \textbf{D} = demonstrated PoC, \textbf{P} = predicted (same instantiation, not built).}
\label{tab:applicability}
\small
\begin{tabular}{@{}llp{0.30\linewidth}lp{0.22\linewidth}c@{}}
\toprule
Service & Class & Credential metadata & Gating point & Activation primitive & Status \\
\midrule
Bandwidth allocation        & A & rate cap, duration, edge endpoint                 & customer-edge dataplane & QoS rule push (gNMI + \texttt{tc})        & D \\
Network slice               & A & slice profile, SLA params, duration               & slice ingress           & slice instantiation                       & P \\
Site-to-site VPN tunnel     & A & endpoints, capacity, duration                     & PE router dataplane     & tunnel + policy push                      & P \\
DDoS-scrubbing admission    & A & prefix set, duration                              & scrubbing-center ingress& redirect/announce config                  & P \\
Telemetry-configuration grant & B & path set, sample interval, device set, duration & device management plane & sensor-group + subscription (gNMI \texttt{Set}) & D \\
ACL install                 & B & rule set, target device set, duration             & device management plane & ACL configuration push                    & P \\
\midrule
Always-on subscriber broadband & --- & \multicolumn{4}{l}{\emph{Out of scope:} entitlement is identity-bound, not a bounded per-acquisition grant.} \\
Open best-effort connectivity  & --- & \multicolumn{4}{l}{\emph{Out of scope:} no per-consumer gating state to check a credential against.} \\
Real-time control loop         & --- & \multicolumn{4}{l}{\emph{Out of scope:} fails coarse granularity---sub-second horizon below the settlement floor.} \\
Regulated common-carrier service & --- & \multicolumn{4}{l}{\emph{Out of scope:} no market semantics---allocation is not at the operator's discretion.} \\
\bottomrule
\end{tabular}
\end{table*}
```

- [ ] **Step 3: Compile**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; no new errors. Check `.out/main-v2.log` for `Table \ref{tab:applicability}` resolving (no `LaTeX Warning: Reference 'tab:applicability' on page ... undefined` after the second pass — `latexmk` runs enough passes automatically). The `table*` will float to a column-spanning position; an Overfull `\hbox` warning on the table is acceptable but if the table runs off the page, narrow the `p{}` widths by 0.02 each.

- [ ] **Step 4: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add main-v2.tex
git commit -m "feat(paper-v2): applicability table + non-universality framing

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: §4 Prototype — shared machinery, Instance A, Instance B

**Files:**
- Modify: `paper/main-v2.tex` (the `\section{Prototype}` itemize, ~lines 265-320)

- [ ] **Step 1: Replace the `Bandwidth as instance` bullet** with a shared-machinery bullet:

```latex
  \item \textbf{Two instances, shared machinery.} We instantiate the
        architecture twice, once per capability class. \emph{Shared and
        identical across both instances:} the escrow + atomic-swap contract,
        NFT minting, the gateway ownership/expiry/status/scope check, A2A
        negotiation between consumer and provider agents, the MCP toolsets for
        wallet signing and contract calls, and the six-stage LangGraph
        workflow. \emph{Per-instance, and the only things that vary:} the NFT
        credential metadata, the provider's catalog tiers, the stage-6
        activation primitive (and the gateway's post-check action), and the
        verification probe.
```

- [ ] **Step 2: Replace the `Stack` bullet with two bullets** — Instance A and Instance B:

```latex
  \item \textbf{Instance A --- bandwidth allocation.} Stack: local EVM chain
        (Foundry/Anvil~\cite{paradigmFoundry2022}), a Solidity contract
        implementing escrow and NFT exchange, a consumer agent, a provider
        agent with the gateway co-located in its A2A \texttt{activate} handler,
        a gNMI client targeting a Nokia SR~Linux dataplane, and a
        containerlab-based topology with Linux customer-edge nodes. The
        credential metadata is \texttt{(agreementId, mbps, duration, startTime,
        endpoint)}; the catalog tiers are bandwidth/duration/price/slots. What
        is real: wallet signing, on-chain execution, NFT minting, ownership
        checks, gateway verification logic, and the activation command---
        delivered via gNMI to a real SR~Linux dataplane and verified
        end-to-end by an iperf3 probe between two Linux customer-edge nodes.

  \item \textbf{Instance B --- telemetry-configuration grant.} The contract,
        agents, A2A/MCP layer, and workflow are reused unchanged. The
        credential metadata is \texttt{(agreementId, pathSet, sampleInterval,
        duration, startTime, deviceSet)}; the catalog tiers are telemetry
        scopes (e.g.\ interface counters at a 5\,s interval for one hour, or
        BGP-neighbor state at a 1\,s interval for thirty minutes). The
        activation primitive: on presentation of an in-scope token, the
        provider agent emits the device-appropriate telemetry configuration
        (here, a sensor-group and persistent subscription installed on
        SR~Linux via a gNMI \texttt{Set}; the same agent emits IOS-XR
        configuration for an XR device). Verification: a short gNMI
        \texttt{Subscribe} from the consumer that confirms samples arrive for
        the granted paths over the window. What is real for this instance
        mirrors Instance~A---signing, on-chain execution, mint, ownership and
        scope checks, the configuration \texttt{Set} delivered to a real
        SR~Linux device, and the streamed samples received by the consumer.
```

- [ ] **Step 3: Edit the `Stack rationale` bullet** — keep it, but update the LLM-hosting clause to acknowledge the dialect-selection task. Find the sentence beginning "a 3B-parameter model is sufficient for the workflow's bounded language tasks" and replace through "no tool-calling required" with:

```latex
        a 3B-parameter model is sufficient for the workflow's bounded language
        tasks---single-word tier classification, short-prose summarisation, and
        selecting the device-appropriate configuration dialect from a small
        fixed set---with no open-ended tool-calling required
```

- [ ] **Step 4: Keep the `Multi-provider discovery` bullet unchanged.**

- [ ] **Step 5: Replace the `What is real` bullet** — its content has moved into the two instance bullets, so delete the standalone `What is real` bullet entirely. **Edit the `What is out of scope` bullet** to add the new items:

```latex
  \item \textbf{What is out of scope.} Economic value, provider reputation,
        legal enforcement, physical-bandwidth guarantees, oracle-based
        delivery verification, per-subscription billing, multi-device fan-out,
        and real telemetry-analytics consumers.
```

- [ ] **Step 6: Compile**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; no new errors.

- [ ] **Step 7: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add main-v2.tex
git commit -m "feat(paper-v2): prototype section -> shared machinery + two instances

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: §5 Evaluation — per-instance RQ1/RQ2 + RQ3 scope enforcement

**Files:**
- Modify: `paper/main-v2.tex` (the `\section{Evaluation}` itemize, ~lines 322-329)

- [ ] **Step 1: Replace the Evaluation itemize body** with:

```latex
  \item \textbf{RQ1 --- End-to-end feasibility.} Does each workflow---bandwidth
        allocation and telemetry-configuration grant---complete, stage by
        stage, without human intervention after the initial intent?

  \item \textbf{RQ2 --- Indicative cost.} What are the approximate latency and
        gas costs for one successful run of each instance? Gas is expected to
        be near-identical across instances (the same escrow, mint, and swap
        calls); activation latency differs (a QoS/policer push versus a gNMI
        \texttt{Set} of a telemetry subscription).

  \item \textbf{RQ3 --- Scope enforcement.} Does the gateway reject an
        out-of-scope activation request---a token presented for a configuration
        (or rate, or device) outside its credential metadata---before issuing
        any network action? This exercises the reference-monitor role of the
        gateway check.
```

- [ ] **Step 2: Compile**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; no new errors.

- [ ] **Step 3: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add main-v2.tex
git commit -m "feat(paper-v2): evaluation -> per-instance RQ1/RQ2 + RQ3 scope enforcement

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 9: §6 Discussion and Limitations

**Files:**
- Modify: `paper/main-v2.tex` (the `\section{Discussion and Limitations}` itemize, ~lines 331-362)

- [ ] **Step 1: Replace the "audit byproduct" bullet** with the split-value-story version:

```latex
  \item A useful byproduct of the design: the on-chain record of the
        payment--credential exchange is itself the audit artifact, and it
        serves a different operator need per capability class. For capacity
        allocation it is settlement evidence---the same record that enables
        autonomy is what operators need for inter-operator wholesale
        reconciliation. For configuration authority it is an accountability and
        forensics record: who was authorized to install state on the network,
        with what scope, and when---a question operators face after any
        third-party configuration touch.
```

- [ ] **Step 2: Replace the "contract does not prove physical delivery" bullet** with a version that strengthens the Class B caveat:

```latex
  \item The contract does not prove physical delivery; the provider gateway
        remains trusted to translate a valid credential into a network action.
        Token ownership is a cryptographic fact verifiable by any chain reader,
        and the payment--authorization link is trustless (enforced by the
        atomic swap), while delivery relies on provider honesty---as it does in
        any API service subscription. The trust assumption is not symmetric
        across the two classes, however: for capacity allocation the consumer
        merely receives output at the edge, but for configuration authority the
        consumer's agent has caused a write into the provider's management
        plane, so the gateway's scope check is doing security-relevant work,
        not just billing-relevant work. A future direction---more pressing for
        the configuration-authority class---is resource-side token
        verification: a device that queries \texttt{ownerOf()} on-chain
        directly could admit a configuration autonomously without a trusted
        gateway intermediary, closing the remaining trust gap cryptographically.
```

- [ ] **Step 3: Add a new threat-model bullet** immediately after the bullet from Step 2:

```latex
  \item \textbf{Threat model.} The design addresses three agent-misbehaviour
        cases. Payment/credential defection (one side locks, the other walks)
        is prevented by the atomic swap. Out-of-scope activation (a token used
        for more than it grants) is prevented by the gateway's scope check.
        Credential replay after redemption is prevented by the activated-status
        flag the gateway checks. Three cases are \emph{not} yet handled and are
        future work: concurrent acquisitions racing for the same slot, refund
        paths when a provider fails to deliver after the swap, and rejection of
        expired credentials at the gateway rather than only at mint time.
```

- [ ] **Step 4: Keep the "autonomy is post-intent" bullet unchanged.**

- [ ] **Step 5: Edit the "latency makes the pattern suitable" bullet** — append:

```latex
        For the configuration-authority class the coarse-granularity bound is
        not the settlement floor but the business model: windowed or
        incident-scoped instrumentation, not permanent telemetry state.
```

- [ ] **Step 6: Edit the `Scope` bullet** — keep it, but add the non-universality sentence at the start:

```latex
  \item \textbf{Scope.} We do not claim universality. The pattern targets
        network services that are bounded, gated, and coarse-grained---a class
        characterized analytically by Table~\ref{tab:applicability} and
        validated empirically by two instances spanning both capability
        classes. Metered and multi-tenant services require token-semantic
        adaptations not evaluated here; always-on subscriber broadband, open
        best-effort connectivity, and regulated common-carrier services fall
        outside the architecture's applicability.
```

- [ ] **Step 7: Compile**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; no new errors; `tab:applicability` reference resolves.

- [ ] **Step 8: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add main-v2.tex
git commit -m "feat(paper-v2): discussion -> split value story, threat model, non-universality

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 10: §7 Conclusion

**Files:**
- Modify: `paper/main-v2.tex` (the `\section{Conclusion}` itemize, ~lines 364-382)

- [ ] **Step 1: Replace the Conclusion itemize body** with:

```latex
  \item Tokenized authorization paired with smart-contract escrow can close the
        autonomous acquisition loop between two agents, with A2A handling
        inter-agent negotiation and MCP exposing each agent's internal tools.

  \item Two proof-of-concept instances---a bandwidth allocation and a
        token-gated telemetry-configuration grant---demonstrate end-to-end
        feasibility across both capability classes; the same pattern is
        predicted to apply to other bounded, gated, coarse-grained network
        services (network slices, advance reservations, VPN tunnels,
        scrubbing admission, ACL grants), and is not intended for real-time,
        always-on, open, or common-carrier services.

  \item Future work includes concurrent acquisitions, failed-provider refund
        paths, expired-credential rejection at the gateway, and resource-side
        \texttt{ownerOf()} verification that would remove the trusted-gateway
        intermediary; the transferability property of the NFT credential also
        opens a direction where a large service is decomposed across
        sub-provider agents, each holding a delegated token for its allocated
        share.
```

- [ ] **Step 2: Compile**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; no new errors.

- [ ] **Step 3: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add main-v2.tex
git commit -m "feat(paper-v2): conclusion reworded for two instances

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 11: Conceptual "agentic telco as platform" figure

**Files:**
- Modify: `paper/main-v2.tex` (add `\usepackage{tikz}` to the preamble if not present; insert a new `figure*` near the start of §3 Architecture)

- [ ] **Step 1: Add to the preamble** (after `\usepackage{hyperref}`, only if `tikz` is not already loaded):

```latex
\usepackage{tikz}
\usetikzlibrary{positioning,fit,backgrounds}
```

- [ ] **Step 2: Insert a new `figure*`** at the top of `\section{Architecture}` (before the first existing `\item`):

```latex
\begin{figure*}[t]
\centering
\begin{tikzpicture}[font=\small,node distance=4mm and 8mm,
  layer/.style={draw,rounded corners,minimum height=11mm,align=center},
  elem/.style={draw,fill=black!4,rounded corners,minimum height=8mm,align=center,inner sep=3pt}]
  % three layers
  \node[layer,minimum width=0.95\linewidth] (agent) {};
  \node[layer,minimum width=0.95\linewidth,below=of agent] (chain) {};
  \node[layer,minimum width=0.95\linewidth,below=of chain] (net) {};
  \node[left=1mm of agent,rotate=90,anchor=south] {Agent};
  \node[left=1mm of chain,rotate=90,anchor=south] {Chain};
  \node[left=1mm of net,rotate=90,anchor=south] {Network};
  % elements on the agent layer
  \node[elem] at (agent.center) (comm) {Communication: A2A (inter-agent) + MCP (intra-agent)};
  % chain layer elements
  \node[elem,xshift=-3cm] at (chain.center) (pay) {Payment\\escrow};
  \node[elem,right=of pay] (auth) {Authorization\\NFT capability token};
  % network layer elements: the fork
  \node[elem,xshift=-3cm] at (net.center) (gw) {Activation\\gateway = reference monitor};
  \node[elem,above right=2mm and 12mm of gw,yshift=-2mm] (capA) {Class A: dataplane QoS push};
  \node[elem,below right=2mm and 12mm of gw,yshift=2mm] (capB) {Class B: management-plane config push};
  \draw[->] (gw) -- (capA);
  \draw[->] (gw) -- (capB);
  % six-stage arrow across the bottom
  \node[below=8mm of net.south west,anchor=west,align=left] (stages)
    {Workflow: 1 Discovery\,$\to$\,2 Payment Lock\,$\to$\,3 Credential Issuance\,$\to$\,4 Swap\,$\to$\,5 Activation\,$\to$\,6 Consumption\;\;(stages 1--5 class-invariant; only stage 6 forks)};
\end{tikzpicture}
\caption{Agentic telco as platform: three layers, four elements, one six-stage workflow. The architecture and workflow are invariant across capability classes; only the stage-6 activation primitive forks---a dataplane QoS rule (Class~A, capacity allocation) or a management-plane configuration push (Class~B, configuration authority).}
\label{fig:platform}
\end{figure*}
```

- [ ] **Step 3: Reference the new figure** — in the first `\item` of §3 Architecture (the "Components are organized as…" bullet), append `(Figure~\ref{fig:platform})` after the first sentence.

- [ ] **Step 4: Compile**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; no `! Package tikz Error`; `fig:platform` reference resolves. If the TikZ picture overflows the column-spanning width, reduce the `xshift`/`node distance` values or wrap the stages node text. A messy-but-compiling figure is acceptable for this pass — note in the commit that the figure is a draft layout pending polish.

- [ ] **Step 5: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add main-v2.tex
git commit -m "feat(paper-v2): add agentic-telco-as-platform overview figure (draft layout)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 12: Full `main-v2.tex` review pass

**Files:**
- Modify: `paper/main-v2.tex` (fixes only if issues found)

- [ ] **Step 1: Clean rebuild**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && rm -f .out/main-v2.* && latexmk -pdf -outdir=.out main-v2.tex
```
Expected: exits 0; `.out/main-v2.pdf` produced.

- [ ] **Step 2: Grep the log for problems**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && grep -nE "^! |Undefined control sequence|undefined|Citation .* undefined|Reference .* undefined|Missing" .out/main-v2.log || echo "clean"
```
Expected: `clean` (Overfull/Underfull `\hbox` lines are fine and not matched by this grep). If anything else appears, fix it in `main-v2.tex` and rebuild.

- [ ] **Step 3: Sanity-read the PDF** — confirm: title still says "Service"; abstract mentions two capability classes; §1 contributions list has the three reworded items; Table~\ref{tab:applicability} renders with all rows; §4 has Instance A and Instance B bullets; §5 has RQ1/RQ2/RQ3; §6 has the threat-model bullet; Figure~\ref{fig:platform} appears. (This step is a manual check; no command.)

- [ ] **Step 4: Commit any fixes**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add main-v2.tex
git commit -m "fix(paper-v2): review-pass corrections"  # only if changes were made; otherwise skip
```

---

### Task 13: Scaffold `slides-v2.tex`

**Files:**
- Create: `paper/slides-v2.tex` (byte copy of `paper/slides.tex`)

- [ ] **Step 1: Copy**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && cp slides.tex slides-v2.tex
```

- [ ] **Step 2: Compile baseline**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out slides-v2.tex
```
Expected: exits 0; `.out/slides-v2.pdf` exists; no `! ` errors.

- [ ] **Step 3: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add slides-v2.tex
git commit -m "chore(slides-v2): scaffold slides-v2.tex from slides.tex

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 14: Restructure `slides-v2.tex` to the new spine

**Files:**
- Modify: `paper/slides-v2.tex`

> The executor must first **read `slides.tex` in full** to learn its frame structure (Beamer theme, how frames/sections are defined, how the existing bandwidth content is laid out) before editing — the steps below describe the target content, not exact line edits, because the deck's internal structure is not reproduced here.

- [ ] **Step 1: Read the deck**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && sed -n '1,80p' slides-v2.tex
```
(Then read the rest as needed to map frames to topics.)

- [ ] **Step 2: Update the title frame** — keep "Network Service Provisioning…"; update any subtitle/abstract frame to mention the two capability classes (capacity allocation; configuration authority) and two PoCs.

- [ ] **Step 3: Architecture frame** — present three layers / four elements; state the gateway is a reference monitor.

- [ ] **Step 4: Workflow frame** — six stages; highlight that stages 1–5 are class-invariant and only stage 6 forks (consume traffic vs. receive telemetry stream).

- [ ] **Step 5: Capability-classes frame** — a trimmed version of the §3.3 comparison: Class A (capacity, dataplane gating, QoS push) vs. Class B (configuration authority, management-plane gating, config push); one line on the agent picking the device dialect.

- [ ] **Step 6: Applicability frame** — a trimmed version of Table~\ref{tab:applicability}: ~4 in-scope rows + the out-of-scope ones with the failing property.

- [ ] **Step 7: PoC frame(s)** — one frame (or a split frame) for both instances, emphasizing shared machinery vs. per-instance variation (metadata, catalog tiers, activation primitive, verification probe); name what's real in each.

- [ ] **Step 8: Evaluation frame** — RQ1 (both complete), RQ2 (latency/gas per instance; gas ≈ equal, activation latency differs), RQ3 (gateway rejects out-of-scope request).

- [ ] **Step 9: Discussion frame** — split audit value (settlement vs. accountability); the asymmetric trust caveat (Class B writes into the management plane); threat model in one line; "we do not claim universality".

- [ ] **Step 10: Remove or repurpose** any old slides that were bandwidth-only and now duplicated by the generalized frames; keep the deck coherent and not bloated.

- [ ] **Step 11: Compile**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && latexmk -pdf -outdir=.out slides-v2.tex
```
Expected: exits 0; no `! ` errors; check `grep -nE "^! |undefined" .out/slides-v2.log || echo clean` → `clean`.

- [ ] **Step 12: Sanity-read `.out/slides-v2.pdf`** — frames appear in a sensible order; no obviously broken layout; both capability classes and both PoCs are covered. (Manual check.)

- [ ] **Step 13: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper
git add slides-v2.tex
git commit -m "feat(slides-v2): restructure deck for two capability classes + two PoCs

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 15: Final wrap

- [ ] **Step 1: Confirm originals untouched**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && git log --oneline -1 -- main.tex slides.tex && git diff --stat HEAD~12 -- main.tex slides.tex
```
Expected: no diff lines for `main.tex` or `slides.tex` across this work (their last-touching commit predates Task 1).

- [ ] **Step 2: Confirm both v2 docs build from clean**

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && rm -f .out/main-v2.* .out/slides-v2.* && latexmk -pdf -outdir=.out main-v2.tex && latexmk -pdf -outdir=.out slides-v2.tex && ls -la .out/main-v2.pdf .out/slides-v2.pdf
```
Expected: both PDFs present; both `latexmk` runs exit 0.

- [ ] **Step 3: Push** (the paper repo's convention is to push after committing — `git push`; if it's the first push of these commits, the executor should check `git status -sb` for the upstream and use `git push` or `git push -u origin master` accordingly).

```bash
cd /home/musel/Github/ollama-agent-simulation/paper && git push
```

---

## Self-Review

**Spec coverage:**
- New `main-v2.tex`, originals untouched → Tasks 1, 15. ✓
- New `slides-v2.tex`, originals untouched → Tasks 13–15. ✓
- Title keeps "service" → Task 2 Step 1. ✓
- Abstract names the abstraction + two classes + two instances → Task 2. ✓
- §1 generalized question + reference-monitor framing + three reworded contributions → Task 3. ✓
- §2 abstract opening + two parallel scenarios + stage-6 fork note + figure captions → Task 4. ✓
- §3 capability-token framing, forked activation, composition sentence → Task 5. ✓
- §3 applicability bullet rewrite + variation-point table (~6 in-scope + 4 out-of-scope rows) → Task 6. ✓
- §4 shared-machinery split + Instance A + Instance B + stack-rationale dialect note + out-of-scope additions → Task 7. ✓
- §5 per-instance RQ1/RQ2 + RQ3 scope enforcement → Task 8. ✓
- §6 split value story + strengthened Class B caveat + threat-model paragraph + coarse-grained-different-reason + non-universality → Task 9. ✓
- §7 reworded for two instances → Task 10. ✓
- "Agentic telco as platform" overview figure → Task 11. ✓
- Slides mirror the spine (architecture / workflow / classes / applicability / PoCs / eval / discussion) → Task 14. ✓
- Build/verify discipline throughout → every task's compile step + Tasks 12, 15. ✓

**Placeholder scan:** Task 14 intentionally describes target content rather than exact line edits, because `slides.tex`'s internal frame structure is not reproduced in this plan — the executor is instructed to read the deck first. This is a deliberate, bounded exception (the deck is the author's existing artifact and its structure is not knowable from `main.tex`), not a "fill in details" punt. All `main-v2.tex` tasks contain literal LaTeX. No "TBD"/"add error handling"/etc.

**Type/name consistency:** `\label{tab:applicability}` (Task 6) ↔ `\ref{tab:applicability}` (Tasks 6, 9). `\label{fig:platform}` (Task 11) ↔ `\ref{fig:platform}` (Task 11). Credential-metadata tuples consistent between Task 6 (table), Task 7 (Instance A: `(agreementId, mbps, duration, startTime, endpoint)`; Instance B: `(agreementId, pathSet, sampleInterval, duration, startTime, deviceSet)`) and the spec §3.3. Class labels "A = capacity allocation / dataplane", "B = configuration authority / management plane" used consistently in Tasks 4, 5, 6, 7, 8, 9, 11, 14.
