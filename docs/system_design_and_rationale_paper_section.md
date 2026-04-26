# System Design and Rationale

## Output 1: Big Picture Narrative

Autonomous software agents are increasingly expected to act as operational principals rather than passive assistants. In current agent frameworks, an agent can inspect tool descriptions, call APIs, query databases, compose workflows, and delegate tasks with limited human intervention. This capability changes the interface requirements for digital infrastructure. Services that were formerly acquired through a human-mediated sequence of portal login, account creation, credential issuance, billing setup, and provider-specific API use now become candidates for machine-speed acquisition. Network service provisioning is a representative case. Bandwidth reservations, network slices, tunnels, and virtualized connectivity services are valuable precisely because they can be requested in response to changing workload demand, but their commercial and operational interfaces remain largely designed around enterprise procurement and operator-controlled orchestration. The resulting gap is not only one of automation convenience. It is the absence of a standardized, machine-native mechanism by which one autonomous agent can discover a service, acquire it, settle payment, receive a verifiable access credential, and present that credential to the provider without relying on an out-of-band account relationship.

Existing work addresses parts of this problem but does not close the loop. Agent coordination protocols such as A2A, ACP, DID-based discovery, and MCP standardize how agents describe capabilities, exchange messages, invoke tools, and in some cases authenticate one another. For example, A2A emphasizes agent cards, task exchange, and interoperable communication, while MCP standardizes the connection between LLM applications and external tools or data sources. These mechanisms are necessary for agent interoperability, but they generally stop before economic finality and resource activation. Conversely, smart-contract payment work, including escrow, dual-deposit fair exchange, x402-style payment handshakes, and A402-style payment-execution binding, provides mechanisms for programmable settlement, but these mechanisms are generic with respect to the thing being purchased. They do not, by themselves, define what a bandwidth lease is, how its metadata is verified, or how a gateway should translate payment into access. A third line of work on tokenized network infrastructure, 5G slicing marketplaces, and DLT-supported slice management demonstrates that network resources can be represented and traded through smart contracts, but much of this work assumes a human user interface, a centralized marketplace, or a management and orchestration stack that remains the locus of provisioning authority. The contribution of the present feasibility study is to compose these three threads: autonomous agent coordination, atomic trustless settlement, and a network resource represented as a tokenized asset.

The proposed architecture is bilateral and staged. A consumer agent and a provider agent first negotiate off-chain: the consumer discovers the provider, queries a catalog, and obtains a quote for a bandwidth tier. The consumer then locks ETH in an escrow contract by creating an agreement. The provider observes the agreement event, mints a bandwidth NFT containing service metadata, approves the escrow contract to move that NFT, and calls `deposit()`. Settlement occurs atomically: in one EVM transaction, the NFT is transferred to the consumer and the escrowed ETH is released to the provider. The resulting safety condition can be written informally as \( \Delta ETH_{provider} > 0 \Leftrightarrow ownerOf(tokenId)=consumer \), subject to successful execution of the `deposit()` transaction. This does not prove network delivery. It proves that payment release and credential delivery are coupled by the same transaction boundary.

The smart contract is the appropriate neutral settlement layer because neither agent should depend on the other's private database or execution trace to verify the exchange. The consumer can verify that funds are not released unless the matching credential is delivered; the provider can verify that the consumer's payment is already locked before minting and depositing the NFT. The NFT is the credential because each lease is unique, transferable under a standard ownership interface, and machine-verifiable through `ownerOf(tokenId)`. In this implementation, the NFT also stores `agreementId`, `bandwidthMbps`, `durationSeconds`, `startTime`, and `endpoint` directly on-chain, allowing both the escrow contract and the gateway to check the credential without dereferencing an external metadata store. The gateway is the bridge between the on-chain and off-chain worlds. Real network services cannot be delivered by a smart contract; the contract can only represent rights and settlement state. Therefore, the provider-side gateway reads the on-chain credential and translates ownership into an authorization decision.

The current implementation demonstrates Iteration 1 of this architecture: autonomous acquisition, atomic ETH/NFT settlement, and token-gated access to service metadata. It uses FastAPI services for the consumer, provider, and gateway; Ollama for local LLM-driven tool selection; deterministic Python functions for settlement-critical operations; Web3.py for chain interaction; Foundry and Anvil for the local EVM; and Solidity contracts for the NFT and escrow. The consumer agent does not allow the LLM to craft raw transactions. The LLM selects structured tools, while Python signs and broadcasts transactions. The provider watches `AgreementRequested` events by HTTP polling, mints the NFT, approves escrow, and completes `deposit()`. The gateway verifies an Ethereum signed timestamp nonce, checks `ownerOf(tokenId)`, and returns service metadata.

The implementation should not be described as production network provisioning. It runs on a local Anvil chain, uses no real money, carries no real internet traffic, and does not enforce bandwidth at the network layer. The provider inventory is a JSON-lines file that simulates capacity with per-tier slots and lease expiration timestamps. The gateway currently checks ownership but does not deny access based on expiry or non-`ACTIVE` status. The escrow enum includes `CLOSED`, but closure is not implemented. No automated behavioral smart-contract tests are present. Thus, the prototype demonstrates the transactional and credential foundation, corresponding to Tier 1 provider-asserted access. Iteration 2 should connect the credential to actual network provisioning in ContainerLab or EVE-NG, corresponding to Tier 2 infrastructure-enforced provisioning. A later Tier 3 would add oracle-monitored delivery verification, so that settlement or continued validity can depend on observed service delivery rather than provider assertion alone.

## Output 2: State-of-the-Art Justification Table and Commentary

| # | Decision | Chosen Option | Main Prior-Work Thread |
|---|---|---|---|
| 1 | Settlement layer | Smart-contract escrow | Thread 2; Thread 3 |
| 2 | Fair exchange | Single-transaction ETH/NFT swap | Thread 2 |
| 3 | State machine | `REQUESTED -> ACTIVE` directly | Distributed transaction design principle |
| 4 | Credential type | ERC-721 NFT | Thread 3; ERC-721 |
| 5 | Metadata location | On-chain NFT struct | Thread 2; Thread 3 |
| 6 | Service bridge | Off-chain gateway reads chain | Thread 3 |
| 7 | Gateway authentication | Ethereum signed timestamp nonce | Thread 1; EIP-4361 principles |
| 8 | Event watching | HTTP log polling | Deployment reliability principle |
| 9 | Capacity model | JSON-lines simulated inventory | Thread 3 abstraction |
| 10 | Service structure | FastAPI microservices per agent | Thread 1 |
| 11 | Local stack | Foundry, Anvil, Web3.py, Ollama | Feasibility-study methodology |
| 12 | LLM authority | Structured tools plus deterministic Python | Thread 1; least privilege |
| 13 | Roadmap | Settlement before enforcement | Threads 1, 2, and 3 |

**1. Smart Contract as Neutral Settlement Layer**  
Decision and chosen option: The design uses `BandwidthEscrow` as the neutral settlement layer between consumer and provider agents. In plain terms, the consumer does not pay the provider directly, and the provider does not issue an access credential on trust. The consumer locks ETH into escrow, and the provider receives payment only through contract logic that can also transfer the NFT credential.

Prior work that motivates or validates this: This maps to Thread 2. Fair-exchange work by Asgaonkar and Krishnamachari frames the buyer-seller dilemma as a problem of exchanging payment for a digital good without a trusted mediator. A402 similarly argues that agentic commerce needs payment and service execution to be bound more tightly than a simple pay-then-deliver flow. Thread 3 also motivates smart contracts for network marketplaces: 5GaaS uses DLT and smart contracts to support transparent slice-marketplace accounting and workflows. Tradeoff: The design accepts blockchain transaction overhead and smart-contract risk in exchange for a shared, externally verifiable settlement state.

**2. Atomic ETH/NFT Swap in One `deposit()` Transaction**  
Decision and chosen option: The provider calls a single `deposit()` function that validates NFT metadata, moves the NFT to the consumer, and releases ETH to the provider. The accepted correctness property is all-or-nothing settlement: either both assets move, or neither asset moves.

Prior work that motivates or validates this: This maps directly to Thread 2. The fair-exchange literature motivates atomicity because separate payment and delivery steps create opportunities for one party to receive value while withholding its own obligation. Asgaonkar and Krishnamachari address this class of problem through smart-contract escrow, and A402 explicitly criticizes agent payment flows that lack end-to-end atomicity across payment, execution, and delivery. The EVM transaction model supplies the required atomic execution boundary for this prototype. Tradeoff: The design accepts a synchronous settlement point, rather than a more flexible multi-step workflow, to preserve the strongest exchange guarantee in Iteration 1.

**3. Collapsing `PENDING`: `REQUESTED` to `ACTIVE` in One Transaction**  
Decision and chosen option: The implementation does not expose a `PENDING` state between provider credential deposit and activation. Since the NFT deposit and swap occur inside one transaction, the externally visible state transition is `REQUESTED -> ACTIVE`.

Prior work that motivates or validates this: This decision is not directly specified by the named agent or network-slicing references. It follows the distributed-systems principle that protocol states should correspond to observable, recoverable phases. A `PENDING` state is useful if different actors must react between two commits. Here, the intermediate phase cannot be observed because EVM state changes become visible only after transaction completion. Tradeoff: The design accepts less state-machine granularity in exchange for a simpler contract with fewer unreachable or misleading states.

**4. ERC-721 NFT as Access Credential**  
Decision and chosen option: The service credential is an ERC-721 NFT rather than an API key, an ERC-20 token, or a W3C Verifiable Credential. Each bandwidth lease is represented by one non-fungible token whose ownership is checked by the gateway.

Prior work that motivates or validates this: This maps primarily to Thread 3, with support from Ethereum standards. Tokenized network-service work treats resources, slices, and service entitlements as tradable or auditable digital assets. ERC-721 is designed for distinguishable assets and exposes the `ownerOf()` ownership query needed by machines. ERC-20 would be inappropriate because bandwidth leases are not interchangeable units once duration, endpoint, and agreement metadata differ. W3C VCs would support portable claims, but they would not give the escrow contract a native on-chain asset to transfer atomically with ETH. Tradeoff: The design accepts NFT-specific transfer semantics and gas cost to obtain uniqueness and native on-chain ownership.

**5. On-Chain Metadata in the NFT Struct**  
Decision and chosen option: The NFT stores agreement metadata directly in a Solidity struct rather than relying on IPFS, `tokenURI`, or another off-chain metadata pointer. The escrow contract can therefore compare the NFT's `agreementId`, bandwidth, and duration with the requested agreement before activating settlement.

Prior work that motivates or validates this: This is partly motivated by Thread 2's need for verifiable exchange conditions and Thread 3's need for unambiguous resource representation. ERC-721 permits optional metadata URIs, but external URIs would add availability and integrity dependencies unless separately pinned and verified. For a settlement-critical credential, the relevant fields must be available to the contract at execution time. The general protocol-design principle is to put consensus-critical predicates on the same trust substrate as the state transition that depends on them. Tradeoff: The design accepts higher storage cost and a less flexible metadata schema to make contract-level validation deterministic.

**6. Off-Chain Gateway Reading On-Chain Ownership**  
Decision and chosen option: The gateway is an off-chain FastAPI service that reads `ownerOf(tokenId)` and NFT metadata from the chain. The chain represents entitlement; the gateway translates entitlement into service access.

Prior work that motivates or validates this: This maps to Thread 3. Network-slicing and 5GaaS architectures distinguish between smart-contract accounting or marketplace logic and actual network orchestration performed by controllers, slice managers, NFVOs, or RAN components. The same separation applies here: the EVM can settle ownership, but it cannot shape traffic or configure a tunnel. General systems design also favors separating control-plane authorization from data-plane delivery. Tradeoff: The design accepts trust in provider-operated gateway behavior until Tier 2 and Tier 3 add infrastructure enforcement and external delivery verification.

**7. Ethereum Signed Timestamp Nonce for Gateway Authentication**  
Decision and chosen option: The consumer authenticates to the gateway by signing a timestamp nonce with its Ethereum key. The gateway recovers the signer address, rejects stale timestamps, and compares the signer with the current NFT owner.

Prior work that motivates or validates this: This maps to Thread 1 and to established cryptographic authentication practice. Agent identity work based on DIDs and ledger-anchored identifiers emphasizes cryptographic control of an identifier rather than passwords or manually issued API keys. Sign-In with Ethereum similarly binds sessions to an Ethereum address and discusses nonce and expiration checks for replay prevention. This implementation is simpler than full SIWE: it uses a timestamp string rather than a structured login statement. Tradeoff: The design accepts weaker domain binding and replay protection than full SIWE/OAuth in exchange for a stateless machine-to-machine authentication path.

**8. Provider-Side HTTP Event Polling Instead of WebSocket Subscriptions**  
Decision and chosen option: The provider watches `AgreementRequested` events by polling logs over HTTP JSON-RPC rather than maintaining a WebSocket subscription. This makes the listener compatible with Anvil's HTTP endpoint and simple local deployment.

Prior work that motivates or validates this: This decision is not directly addressed by the named references. It follows a reliability and deployment principle: use the least demanding transport that satisfies latency requirements. In Iteration 1, block time and service duration make two-second polling sufficient, and missed events can be recovered by querying from a prior block range. WebSocket subscriptions would reduce latency but add connection lifecycle complexity. Tradeoff: The design accepts polling delay and duplicate-log handling concerns in exchange for simpler provider infrastructure.

**9. File-Based Inventory as Simulated Capacity Model**  
Decision and chosen option: Provider capacity is represented by a JSON-lines file with per-tier slots and lease expiration timestamps. It models scarcity but remains provider-controlled local state.

Prior work that motivates or validates this: This maps to Thread 3 only at the level of abstraction. Tokenized network-service literature requires resource availability and capacity to exist somewhere outside the settlement contract, often in a slice manager, marketplace database, or orchestrator. The current file is not a production inventory system; it is a controlled feasibility-study substitute for a real resource manager. The general modeling principle is to simulate only the part of capacity needed to test the settlement workflow. Tradeoff: The design accepts provider-asserted capacity and limited concurrency realism to keep Iteration 1 focused on transactional correctness.

**10. FastAPI Microservices Per Agent**  
Decision and chosen option: The consumer agent, provider agent, and gateway run as separate FastAPI services rather than as a monolith. This reflects the fact that the consumer and provider are different administrative parties.

Prior work that motivates or validates this: This maps to Thread 1. A2A and MCP assume independently operated agents and tool servers that communicate through standard interfaces. BlockA2A and DID-oriented work further motivate explicit trust boundaries between agents belonging to different domains. A monolith would obscure the central research condition: autonomous parties coordinate without sharing private process state. Tradeoff: The design accepts additional HTTP boundaries and deployment overhead to preserve administrative separation and clearer protocol observability.

**11. Foundry, Anvil, Web3.py, and Ollama Local Stack**  
Decision and chosen option: The feasibility study uses a local EVM stack: Foundry for Solidity development, Anvil as the local chain, Web3.py for transaction submission and contract reads, and Ollama for local LLM execution.

Prior work that motivates or validates this: This decision is primarily methodological rather than directly prescribed by Threads 1-3. It supports reproducibility and safe experimentation: Anvil avoids public testnet cost and instability, Foundry provides a standard Ethereum development workflow, Web3.py integrates the Python agents with contracts, and Ollama keeps agent reasoning local. This is consistent with feasibility-study practice, where internal validity is prioritized before external deployment. Tradeoff: The design accepts limited external validity because the prototype has not yet been deployed to a public testnet or production network.

**12. LLM Uses Structured Tools; Deterministic Python Executes Settlement-Critical Operations**  
Decision and chosen option: The LLM chooses among structured tools, but deterministic Python code constructs, signs, and broadcasts transactions. The LLM does not craft raw calldata or directly manipulate private keys.

Prior work that motivates or validates this: This maps to Thread 1. MCP formalizes tool invocation as a structured interface between AI applications and external systems, and the agent interoperability survey identifies typed tool access as a way to make agent integrations more secure and generalizable. The general security principle is least privilege: probabilistic reasoning can select intent-level actions, while deterministic code enforces schemas, parameter checks, and key custody boundaries. Tradeoff: The design accepts reduced LLM flexibility in exchange for a narrower and more auditable settlement path.

**13. Staged Architecture: Settlement First, Network Enforcement Second**  
Decision and chosen option: The project implements settlement and token-gated access first, then leaves actual network provisioning and delivery verification for later iterations. Iteration 1 proves the transaction and credential foundation; Iteration 2 should connect credentials to ContainerLab or EVE-NG; Tier 3 should add oracle-monitored delivery verification.

Prior work that motivates or validates this: This maps across all three threads. Thread 1 supplies agent coordination, Thread 2 supplies fair settlement, and Thread 3 supplies the long-term target of programmable network resources. 5GaaS and Bandara's 6G agentic control-plane work show that real slice orchestration involves many additional control-plane and monitoring functions. Treating settlement as a first milestone prevents overclaiming and allows the prototype to validate the part most distinct from traditional network provisioning. Tradeoff: The design accepts a narrower current demonstration in exchange for a staged path that can later add enforcement and measurement without weakening the settlement model.

## References Used

[A2A] Agent2Agent Protocol specification and documentation, including Agent Cards, JSON-RPC over HTTP, and task lifecycle concepts. https://google-a2a.github.io/A2A/specification/

[MCP] Model Context Protocol documentation, introduction to MCP as an open standard for connecting AI applications to external systems. https://modelcontextprotocol.io/docs/getting-started/intro

[Ehtesham2025] A. Ehtesham, A. Singh, G. K. Gupta, and S. Kumar, "A survey of agent interoperability protocols: MCP, ACP, A2A, and ANP," arXiv:2505.02279, 2025. https://arxiv.org/abs/2505.02279

[Vaziry2025] A. Vaziry, S. Rodriguez Garzon, and A. Kupper, "Towards Multi-Agent Economies: Enhancing the A2A Protocol with Ledger-Anchored Identities and x402 Micropayments for AI Agents," arXiv:2507.19550, 2025. https://arxiv.org/abs/2507.19550

[BlockA2A2025] "BlockA2A: Towards Secure and Verifiable Agent-to-Agent Interoperability," arXiv:2508.01332, 2025. https://arxiv.org/abs/2508.01332

[Asgaonkar2019] A. Asgaonkar and B. Krishnamachari, "Solving the Buyer and Seller's Dilemma: A Dual-Deposit Escrow Smart Contract for Provably Cheat-Proof Delivery and Payment for a Digital Good without a Trusted Mediator," IEEE ICBC 2019 / arXiv:1806.08379. https://arxiv.org/abs/1806.08379

[A4022026] Y. Li et al., "A402: Binding Cryptocurrency Payments to Service Execution for Agentic Commerce," arXiv:2603.01179, 2026. https://arxiv.org/abs/2603.01179

[5GaaS2024] K. Rasol et al., "5GaaS: DLT and Smart Contract-Based Network Slice Management in a Decentralized Marketplace," CNSM 2024. https://dl.ifip.org/db/conf/cnsm/cnsm2024/1571076515.pdf

[Bandara2026] E. Bandara et al., "An Agentic AI Control Plane for 6G Network Slice Orchestration, Monitoring, and Trading," arXiv:2602.13227, 2026. https://arxiv.org/abs/2602.13227

[Uriarte2021] R. B. Uriarte et al., "Distributed service-level agreement management with smart contracts and blockchain," Concurrency and Computation: Practice and Experience, vol. 33, no. 14, 2021.

[ERC721] ERC-721 Non-Fungible Token Standard. https://ercs.ethereum.org/ERCS/erc-721

[EIP4361] ERC-4361: Sign-In with Ethereum. https://eips.ethereum.org/EIPS/eip-4361
