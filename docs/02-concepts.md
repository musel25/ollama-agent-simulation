# Concepts Primer

> **Audience:** anyone who wants to understand the words used in the rest of this documentation. No prior knowledge assumed.
>
> **How to read this doc:** scan the table of contents, jump to whatever concept you don't already know, and skip the rest. Concepts are roughly ordered so that earlier ones are referenced by later ones.

## Table of Contents

1. [Programming and runtime](#1-programming-and-runtime)
2. [AI and agents](#2-ai-and-agents)
3. [Inter-agent protocols: MCP and A2A](#3-inter-agent-protocols-mcp-and-a2a)
4. [Blockchain fundamentals](#4-blockchain-fundamentals)
5. [Tokens and NFTs](#5-tokens-and-nfts)
6. [Payment, escrow, and atomic swap](#6-payment-escrow-and-atomic-swap)
7. [Networking and SDN](#7-networking-and-sdn)
8. [State machines](#8-state-machines)

---

## 1. Programming and runtime

### 1.1 Python

**One-liner:** A general-purpose programming language readable enough to look like English.

Python is one of the most popular languages in the world. It runs on almost every operating system, has a massive library ecosystem, and is the dominant language for AI and backend tooling. Unlike compiled languages (C, Java), Python is interpreted — you give it a file and it executes line by line. Python 3.13 is the version pinned here; the number matters because Python 3.9 and Python 3.13 have different syntax features and are not fully compatible.

**In this project:** every service — the consumer (`consumer/app.py`), the provider (`provider/app.py`), the shared library (`shared/`), and all tests — is Python 3.13. The version is pinned in `.python-version` and enforced by `requires-python = ">=3.13"` in `pyproject.toml`. Always run scripts with `uv run python ...`, never bare `python` (see §1.3).

---

### 1.2 Virtual environment

**One-liner:** An isolated folder that holds only the packages a specific project needs, so projects don't conflict with each other.

When you install Python packages globally, two projects that need different versions of the same library will break each other. A virtual environment solves this by giving each project its own private copy of every installed package. "Activating" an environment means telling your shell to look there first for `python` and installed tools.

**In this project:** the virtual environment lives in `.venv/` at the repository root. It is not committed to git (`.gitignore` excludes it). You never need to activate it manually — `uv run` (§1.3) handles that for you. If `.venv/` is absent, run `uv venv && uv sync` to recreate it.

---

### 1.3 uv (the package manager used here)

**One-liner:** A very fast Python package and virtual-environment manager that replaces `pip` and `virtualenv`.

Traditional Python packaging involves multiple tools: `pip` to install, `virtualenv` to isolate, `pip-tools` to lock versions. `uv` does all of that in a single command and runs about 10–100× faster. It reads the project's `pyproject.toml` for the list of dependencies, creates and manages `.venv/`, and writes a `uv.lock` file that pins every transitive dependency to an exact version so builds are reproducible.

**In this project:** run `uv sync` once after cloning to install everything. Use `uv run <command>` for anything that needs the project environment (e.g. `uv run pytest`). Add new packages with `uv add <package>`, which updates both `pyproject.toml` and `uv.lock`. Never use bare `pip install` — it bypasses `uv.lock` and can cause version drift.

---

### 1.4 pyproject.toml

**One-liner:** The single configuration file that declares what a Python project is, what it depends on, and how to build it.

Before `pyproject.toml` existed, Python projects scattered configuration across `setup.py`, `setup.cfg`, `requirements.txt`, and `tox.ini`. The modern standard ([PEP 517](https://peps.python.org/pep-0517/)) puts everything in one TOML file. The `[project]` table names the package, sets the minimum Python version, and lists runtime dependencies. Tool-specific config (like `uv`, `pytest`, `ruff`) goes in `[tool.<name>]` tables.

**In this project:** the `[project]` table is at the repo root (`pyproject.toml`). It declares `requires-python = ">=3.13"` and lists all production dependencies — FastAPI, web3, a2a-sdk, langgraph, etc. — and dev dependencies (pytest) under `[dependency-groups]`.

---

### 1.5 FastAPI

**One-liner:** A Python web framework for building HTTP APIs quickly and with automatic input validation.

A web framework is a library that handles the tedious parts of writing an HTTP server: routing (which function to call for which URL), request parsing, error handling, and generating responses. FastAPI is built on top of the Python `asyncio` concurrency model, which means it can handle many requests at once without threads. It uses Python type annotations to automatically validate incoming request bodies (via Pydantic) and auto-generates interactive API documentation (Swagger UI at `/docs`) from your code. The `async def` syntax lets each request handler yield control to other handlers while waiting for I/O, which is important here because many operations wait on the blockchain or network.

**In this project:** both `consumer/app.py:app` and `provider/app.py:app` are FastAPI applications. The consumer's `app` exposes `/chat`, `/catalog_proxy`, and `/address`. The provider's `app` exposes `/catalog`, `/quote`, `/inventory`, `/address`, and the A2A endpoint `/a2a`.

---

### 1.6 Uvicorn

**One-liner:** The web server that actually runs a FastAPI application and listens for network connections.

FastAPI defines what your app does, but it doesn't listen on a port by itself. It needs an ASGI server — a program that opens a TCP socket, accepts HTTP connections, and calls your application code. Uvicorn is the standard choice for FastAPI. You tell it which app object to serve and on which port.

**In this project:** the `CMD` in both Dockerfiles starts uvicorn. The consumer runs on port `:8001` (`uvicorn consumer.app:app --port 8001`) and the provider on port `:8002` (`uvicorn provider.app:app --port 8002`). See `docker-compose.yml` for the full entry points.

---

### 1.7 Streamlit

**One-liner:** A Python library that turns a Python script into a web UI with almost no HTML or JavaScript.

Streamlit is popular for data apps and demos. You write Python code top-to-bottom — `st.text_input(...)`, `st.chat_message(...)`, etc. — and Streamlit renders it as a web page, handling state and interactivity automatically. It is not a full frontend framework; it is best for demos and internal tools.

**In this project:** `consumer/ui.py` is the chat interface that a human uses to talk to the consumer agent. It runs on port `:8501`. The UI does not import any project Python directly — it calls `consumer/app.py` over HTTP (`POST /chat`, `GET /catalog_proxy`) and displays the responses.

---

### 1.8 HTTPX

**One-liner:** A Python library for making HTTP requests, supporting both synchronous and asynchronous usage.

When your Python code needs to call another service over the network, you need an HTTP client library. The classic choice is `requests`, but it is synchronous (it blocks the current thread while waiting for a response). `httpx` has the same simple API but also supports `async/await`, making it compatible with FastAPI and other asyncio code.

**In this project:** `httpx` is used inside `consumer/a2a_client.py` to open the outgoing HTTP connection to the provider's A2A endpoint, and inside the MCP servers when tools need to fetch the provider's Ethereum address (`GET /address`) before building a transaction.

---

### 1.9 Docker and Docker Compose

**One-liner:** Docker packages an application and all its dependencies into a portable container; Docker Compose runs multiple containers together as a system.

A container is like a lightweight virtual machine. It bundles your code, the Python interpreter, all libraries, and OS-level tools into one image that runs identically on any machine. Docker builds images from `Dockerfile` instructions. Docker Compose lets you declare multiple services (consumer, provider, blockchain node, LLM server) in a single `docker-compose.yml` file and start them all with one command.

**In this project:** `docker-compose.yml` at the repo root defines seven services: `anvil` (blockchain), `deployer` (one-shot contract deployment), `ollama` (LLM server), `ollama-pull` (one-shot model pull), `provider-agent`, `consumer-agent`, and `consumer-ui`. The `deployer` and `ollama-pull` services are one-shot — they exit after their job is done. `Dockerfile.consumer` and `Dockerfile.provider` define the images. Use `make up` to build and start everything, `make down` to stop.

---

### 1.10 Environment variable

**One-liner:** A named value stored in the shell's environment that programs can read at runtime to configure themselves without hardcoding secrets.

Instead of putting your private key or database URL directly in source code (which would be committed to git for the world to see), you put it in an environment variable. The program calls `os.environ.get("MY_SECRET")` to read it at startup. A `.env` file is a text file that sets these variables for local development; tools like Docker Compose load it automatically.

**In this project:** secrets and configuration live in `.env` (committed here for convenience with test-only keys; in production you would not commit this). `.env.example` documents every variable. The four most important ones are:
- `RPC_URL` — the Ethereum node to connect to (default `http://localhost:8545`)
- `CONSUMER_PRIVATE_KEY` / `PROVIDER_PRIVATE_KEY` — Ethereum signing keys for each agent
- `OLLAMA_MODEL` — which LLM model to use (default `llama3.2:3b`)
- `SDN_MOCK` — set to `true` to skip real network hardware (default `true`)

---

## 2. AI and agents

### 2.1 LLM (Large Language Model)

**One-liner:** A neural network trained on huge amounts of text that can generate, summarize, translate, and reason about language.

LLMs like GPT, Claude, and Llama are trained to predict the next word given what came before. Through this deceptively simple objective, they learn to write code, answer questions, follow instructions, and use tools. You interact with an LLM by sending it a "prompt" (text) and receiving generated text in return. The model has no persistent memory between calls — each call is independent unless you include prior history in the prompt.

"Large" refers to the number of parameters (weights) in the neural network — modern LLMs range from a few billion to over a trillion parameters. Larger models are generally more capable but slower and more expensive to run. The default model here (`llama3.2:3b`) is small enough to run on a laptop GPU or CPU, at the cost of some reasoning quality compared to frontier models.

**In this project:** the consumer agent uses a locally served LLM as its "brain." The LLM decides which bandwidth tier to buy (`pick_tier_node`) and writes the final summary sentence (`summary_node`). Everything else — on-chain transactions, A2A calls — is deterministic Python code, not LLM output.

---

### 2.2 Ollama

**One-liner:** A tool that lets you download and run open-source LLMs locally on your own machine.

Ollama handles the complexity of running LLMs locally: downloading model weights, managing GPU/CPU resources, and exposing a simple HTTP API that looks like OpenAI's. You `ollama pull <model>` to download a model, and then call `http://localhost:11434` to use it. This means no API keys, no network latency to cloud services, and no data leaving your machine.

**In this project:** the `ollama` service in `docker-compose.yml` runs the Ollama server. On first start, Docker Compose also runs an `ollama-pull` one-shot service that downloads whatever model `OLLAMA_MODEL` points to (default `llama3.2:3b`). Ollama serves at port `:11434`.

---

### 2.3 Prompt and system prompt

**One-liner:** A "prompt" is the text you send to an LLM to ask it something; a "system prompt" is special setup instructions placed before the conversation starts.

Every LLM call consists of a sequence of messages. A "user" message is the thing being asked. A "system" message (often called a system prompt) comes first and sets the assistant's persona, constraints, and background knowledge. The LLM reads all messages in order and generates the next one. Some models (like the Qwen and DeepSeek families) also produce internal "thinking" text (chain-of-thought reasoning in `<think>...</think>` tags) before their visible answer; the Llama 3.2 models used here do not.

Writing a good prompt is an iterative craft. The guiding principle here is: make each prompt as short and focused as possible. A prompt that says "you are a general-purpose agent; figure everything out" produces unpredictable behavior. A prompt that says "choose one word from {small, medium, large} that best matches this user request" produces reliable output.

**In this project:** the LangGraph workflow in `consumer/graph.py` makes focused, per-node LLM calls with short prompts tailored to that node's decision (e.g., "which tier does the user want?"). The overall workflow is driven by the graph structure itself, not by a single large system prompt that tries to orchestrate everything.

---

### 2.4 Tool calling

**One-liner:** A feature where an LLM can pause its response, invoke an external function, and then continue with the result incorporated.

Modern LLMs can do more than generate text — they can call functions. You send the LLM a list of available "tools" (functions with names, descriptions, and parameter schemas). When the LLM decides a tool is needed, it returns a structured request to call that tool (a JSON object with the tool name and arguments). Your code runs the tool, sends the result back to the LLM, and the LLM continues generating. This loop can repeat multiple times in a single interaction, letting the LLM accomplish multi-step tasks.

Tool calling is what makes an LLM an agent rather than just a chatbot. Without tools the model can only produce text; with tools it can execute code, read files, call APIs, send transactions, and observe the results.

**In this project:** the consumer's MCP server (`consumer/mcp_server.py`) defines the tools the LLM can invoke — `browse_catalog`, `request_quote`, `present_credential`, `lock_payment`, `await_settlement`, `wallet_address`, and `sign_message`. The LangGraph nodes in `consumer/graph.py` import these tool functions directly from `consumer/mcp_server.py` and call them as plain async coroutines — there is no MCP round-trip inside the graph. An in-memory `MCPClient` is instantiated separately in `consumer/app.py` and used for the `/catalog_proxy` and `/address` REST endpoints, demonstrating both invocation styles.

---

### 2.5 Agent (in this project)

**One-liner:** An autonomous program that uses an LLM to decide what to do, calls tools to act on those decisions, and repeats until a goal is reached.

Unlike a simple chatbot that only generates text, an agent can take actions: call APIs, read files, send transactions, call other agents. The LLM acts as the reasoning engine that decides what action to take next; the tools provide the ability to act. "Autonomous" means the agent runs the loop without human approval for each step.

There is a spectrum from "LLM with tools that does whatever the model decides" to "scripted workflow with an LLM at one decision node." This project deliberately sits closer to the scripted end: the consumer's purchase flow is a deterministic state machine; the LLM is consulted only where genuine natural-language understanding is needed (tier selection from a free-text user request). This makes behavior predictable and testable, which matters when on-chain money is involved.

**In this project:** there are two agents — the consumer (buyer) and the provider (seller). The consumer agent runs the LangGraph state machine that browses the catalog, picks a tier, gets a quote, locks ETH on chain, waits for settlement, and presents its NFT credential to activate the service. The provider agent listens for on-chain events and responds to A2A messages from the consumer.

---

### 2.6 Model context

**One-liner:** Everything the LLM "sees" on a single call — the prompt text, tool definitions, and conversation history.

LLMs do not have memory. Each call is isolated. The "context" is the entire input you hand the model: system instructions, conversation history, tool schemas, and the current user message. Context size is measured in "tokens" (roughly 0.75 words each). If the context grows too large, it is truncated or summarized.

**In this project:** each LangGraph node that calls the LLM builds a fresh, focused prompt containing only what that node needs. The tool list the LLM sees consists of the consumer's MCP tools. No conversation history is passed between nodes — the graph state carries structured data instead.

---

## 3. Inter-agent protocols: MCP and A2A

### 3.1 The two-protocol design (why both)

**One-liner:** MCP is for an agent talking to its own tools; A2A is for one agent talking to a different agent.

The paper proposes that multi-agent AI systems need two distinct communication layers. Within one agent, the LLM needs a standard way to invoke tools — that is MCP. Between agents, one agent needs a standard way to send tasks and receive results from another agent — that is A2A. Mixing them (e.g., having the LLM call the provider's tools directly via MCP) would tightly couple agents and make it impossible to swap in a different provider implementation.

**In this project:** MCP is used inside each agent — the consumer's LLM calls the consumer's own MCP tools; the provider's executor calls the provider's own MCP tools. A2A is used between agents — when the consumer needs something from the provider (catalog, quote, activation), it sends an A2A `message/send` request over the network. The paper §3 justifies this split.

---

### 3.2 MCP (Model Context Protocol)

**One-liner:** An open standard (by Anthropic) that lets an LLM discover and call tools through a structured JSON interface.

MCP defines how an LLM host discovers available tools, what schema each tool expects, how to invoke a tool, and how to get the result back. By standardizing this, any LLM that speaks MCP can use any MCP server's tools without custom integration code. FastMCP is a Python library that makes writing an MCP server as simple as decorating a function with `@mcp.tool()` — the decorator reads the function's docstring and type annotations to generate the tool's schema automatically.

MCP separates the AI model from the tools it uses. The model does not need to know how a tool works; it just knows the tool's name, description, and parameters. This means you can swap the LLM or add new tools independently. MCP servers can run in-process (in-memory), over standard I/O, or over HTTP — this project uses HTTP mounting and in-memory access.

**In this project:** both agents run FastMCP servers — `consumer/mcp_server.py` and `provider/mcp_server.py`. The consumer's MCP server runs entirely in-process and is never exposed over HTTP — `consumer/app.py` has no `app.mount()` call for it, and the LangGraph nodes in `consumer/graph.py` import the tool functions directly and call them as coroutines. The provider's MCP server is exposed over HTTP: `provider/app.py` calls `app.mount("/", _mcp_http_app)`, making the MCP endpoints reachable at `/mcp` on `:8002` (handled by FastMCP's own HTTP app). The consumer also instantiates an in-memory `MCPClient` in `consumer/app.py`, but only for the `/catalog_proxy` and `/address` REST endpoints — not inside the LangGraph flow.

---

### 3.3 A2A (Agent-to-Agent)

**One-liner:** An open protocol (by Google) that standardizes how one AI agent sends tasks to another AI agent and gets results back.

A2A defines how agents introduce themselves (Agent Cards), how to send a task (JSON-RPC `message/send`), and how to receive results (artifacts). It is designed so agents from different frameworks and vendors can interoperate. The `a2a-sdk` Python library implements the client and server sides of this protocol.

A key design decision in A2A: the calling agent does not need to know what framework or LLM the remote agent uses. The consumer does not know (or care) that the provider is Python — it just sends a `message/send` request to the `/a2a` endpoint and reads back an artifact. This is analogous to how REST APIs let services interoperate across languages. A2A adds discovery (Agent Cards) and a structured task model on top of that idea.

**In this project:** the `a2a-sdk` library (version `>=1.0,<2.0`) is used throughout. The provider runs an A2A server at `/a2a` on `:8002`, handled by `provider/agent_executor.py`'s `BandwidthProviderExecutor`. The consumer sends A2A messages via `consumer/a2a_client.py`'s `send_provider_action` helper. The three A2A actions are `get_catalog`, `request_quote`, and `activate`.

---

### 3.4 Agent Card

**One-liner:** A JSON document that an agent publishes to advertise its identity, capabilities, and communication endpoints.

Think of an Agent Card as a business card for an AI agent. It says who the agent is, what skills it offers, and which URL to use to call it. Other agents fetch the card (usually from `/.well-known/agent-card.json`) to discover how to communicate. The A2A protocol specifies the card format — it includes the agent's name, description, version, supported input/output modes, capabilities (e.g., streaming), and a list of skills. Each skill has an ID, human-readable name, description, example inputs, and tags.

The `/.well-known/` path convention (defined by RFC 8615) is the standard place to put well-known service metadata documents — you may recognize it from `/.well-known/openid-configuration` or `/.well-known/acme-challenge`. A2A adopts the same convention for agent discovery.

**In this project:** both agents publish Agent Cards. The canonical path is `/.well-known/agent-card.json` (with a legacy alias at `/.well-known/agent.json`). The consumer's card is built by `consumer/agent_card.py`. The provider's card is built by `provider/agent_card.py` and advertises three skills: `get_catalog`, `request_quote`, and `activate`.

---

### 3.5 JSON-RPC

**One-liner:** A simple protocol for calling functions over a network using JSON messages.

JSON-RPC defines a standard envelope for remote function calls: you send `{"method": "someMethod", "params": {...}, "id": 1}` and receive `{"result": {...}, "id": 1}` or `{"error": {...}, "id": 1}`. It is transport-agnostic (works over HTTP, WebSockets, etc.) and has a tiny spec — much simpler than SOAP or gRPC.

**In this project:** A2A uses JSON-RPC under the hood. A `message/send` call looks like:

```json
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "id": "abc123",
  "params": {
    "message": { "parts": [{ "data": { "action": "get_catalog" } }] }
  }
}
```

The provider's `/a2a` endpoint receives these and dispatches to `BandwidthProviderExecutor`.

---

## 4. Blockchain fundamentals

### 4.1 Ethereum

**One-liner:** A public blockchain network that runs programmable smart contracts and uses ETH as its currency.

Ethereum is the second-largest cryptocurrency network by market capitalization. Unlike Bitcoin (which only tracks coin balances), Ethereum runs a global computer: smart contracts are programs stored on the chain that execute when called. Every interaction with the chain costs ETH (the native currency) as "gas" (see §4.5). Ethereum is decentralized — thousands of nodes around the world all hold the same state.

**In this project:** a local simulation of Ethereum called Anvil (§4.10) runs at `:8545`, not the real network. The ETH used here is fake testnet ETH — there is no real money involved. The code is written exactly as it would be for a real deployment, though, so the on-chain mechanics are authentic.

---

### 4.2 Smart contract

**One-liner:** A program stored permanently on a blockchain that runs automatically when triggered by a transaction.

A smart contract is code with a stable address on the chain. Anyone can call it by sending a transaction to that address. The code runs on every node in the network simultaneously, and its output (state changes) is recorded immutably. "Smart" means self-executing; "contract" is a loose analogy to legal agreements — the code enforces the rules without a trusted third party. There is no admin who can edit the code after deployment, and no server that can go offline. The contract's logic is public and verifiable by anyone.

Two common points of confusion: (1) "smart contract" does not mean the code is legally enforceable in a court — it is just self-enforcing within the blockchain. (2) Contracts cannot call external APIs or access the internet; all inputs must come from transactions or on-chain state.

**In this project:** two smart contracts power the payment flow — `BandwidthEscrow.sol` holds ETH and orchestrates the atomic swap, and `BandwidthNFT.sol` mints the access credential. Both live under `contracts/src/`.

---

### 4.3 Solidity

**One-liner:** The programming language used to write Ethereum smart contracts.

Solidity is statically typed and compiles to EVM bytecode — the instruction set that Ethereum nodes execute. It looks roughly like a cross between JavaScript and C++. Once a Solidity contract is compiled and deployed to the chain, its code is immutable (cannot be changed). The compiler, `solc`, is bundled with the Foundry toolchain.

Key Solidity concepts you will see in this codebase: `payable` marks a function that can receive ETH; `view` means the function only reads state (no gas for pure reads); `emit` fires an event; `revert` aborts the transaction and undoes all state changes; `mapping(K => V)` is a hash table; `struct` is a value type grouping multiple fields.

**In this project:** `BandwidthEscrow.sol` and `BandwidthNFT.sol` are both written in Solidity `^0.8.20`. They use OpenZeppelin's audited base contracts (`ERC721`, `Ownable`, `ERC721Holder`) as building blocks.

---

### 4.4 Transaction

**One-liner:** A signed, atomic action sent to the blockchain — moving ETH, calling a contract function, or deploying new code.

A transaction is the only way to change state on Ethereum. It must be signed by a private key (proving who authorized it), broadcast to the network, included in a block by a validator, and confirmed. Transactions are atomic — they either fully succeed or fully revert, leaving no partial state. After a transaction is mined into a block, the caller gets back a "receipt" confirming the block number, gas used, and whether the transaction succeeded (`status = 1`) or reverted (`status = 0`).

A failed transaction (status 0) still costs gas — the miner did work to attempt execution — but no state changes persist. This is why the `_send_consumer_tx` helper in `consumer/mcp_server.py` checks `receipt["status"] != 1` and raises an error if the transaction reverted.

**In this project:** the key transaction in the demo is the consumer's `requestAgreement(...)` call on `BandwidthEscrow`. This locks the consumer's ETH and creates the agreement record on chain. The consumer calls this via the `lock_payment` MCP tool in `consumer/mcp_server.py`.

---

### 4.5 Gas

**One-liner:** The computational fee paid for every Ethereum operation — prevents abuse and compensates validators.

Every instruction in an Ethereum smart contract costs a small amount of "gas." Gas is priced in ETH (1 gwei = 10⁻⁹ ETH). A simple ETH transfer costs 21,000 gas; a complex contract call can cost hundreds of thousands or millions. You set a "gas limit" when submitting a transaction — if execution exceeds it, the transaction reverts (you still pay for the gas used up to that point). This economic mechanism prevents infinite loops, spam, and denial-of-service attacks on the network.

When writing Solidity, storage writes (`SSTORE`) are the most expensive operations. Reading from storage is cheaper; emitting an event is cheaper still.

**In this project:** Anvil is configured with a `--block-time 1` (one block per second) and no real gas price enforcement. Gas numbers appear in receipts, but the fake ETH costs nothing. The gas structure is identical to mainnet — the contracts would work unchanged on real Ethereum.

---

### 4.6 Private key and signing

**One-liner:** A private key is a secret number that proves ownership of an Ethereum account; "signing" means using it to cryptographically authorize an action.

An Ethereum "wallet" is just a private key (256 random bits). From it you derive a public key via elliptic curve math, and from that a 20-byte address (the visible account ID, shown as `0x1234...abcd`). When you sign data with your private key, you produce an ECDSA (Elliptic Curve Digital Signature Algorithm) signature — a pair of numbers that proves you hold the key. Anyone who knows the public address can verify the signature was made by that key's holder, without learning the private key itself. This asymmetry is the foundation of all Ethereum security.

Never commit a real private key to a public repository. The keys in `.env.example` and `.env` are Anvil's well-known test keys derived from the canonical test mnemonic; they have no value on real networks, but the pattern you see here (loading from environment variables) is the correct pattern to follow in production.

**In this project:** `CONSUMER_PRIVATE_KEY` and `PROVIDER_PRIVATE_KEY` in `.env` are the signing keys for each agent. They are used for two purposes: (1) signing Ethereum transactions sent to Anvil, and (2) signing a nonce as a credential challenge when the consumer presents its NFT (`present_credential` in `consumer/mcp_server.py`).

---

### 4.7 Nonce (chain context)

**One-liner:** A counter attached to each Ethereum account that ensures transactions are processed in order and cannot be replayed.

Every account on Ethereum has a nonce — a number that starts at 0 and increments by 1 for every transaction sent. When you submit a transaction, it must carry the next expected nonce. This prevents replay attacks (submitting the same signed transaction twice) and defines the order in which transactions from the same account are processed.

**In this project:** the chain nonce is managed automatically by `web3.py` (`_w3.eth.get_transaction_count(..., "pending")`) in both `consumer/mcp_server.py` and `provider/mcp_server.py`. Do not confuse this with the credential nonce — a Unix timestamp string the consumer signs to prove liveness to the provider (§4.6). The credential nonce has nothing to do with transaction ordering.

---

### 4.8 Event (chain log)

**One-liner:** A cheap way for smart contracts to emit structured records that are stored on the chain and can be watched by external code.

Ethereum smart contracts can emit "events" — named records with typed fields — that are appended to the block log. Events cost less gas than storing data in contract state. Off-chain services can subscribe to or poll for specific events using the `eth_getLogs` RPC call. Events cannot be read by other contracts (only by external code), which makes them ideal for notifications to off-chain services.

Events have "indexed" fields (up to 3) that can be filtered efficiently, and non-indexed fields stored in the log data. In `BandwidthEscrow.sol`, `agreementId`, `consumer`, and `provider` are indexed — this lets the provider filter `AgreementRequested` events to only ones that name it as the provider.

**In this project:** `BandwidthEscrow.sol` emits `AgreementRequested(agreementId, consumer, provider, mbps, duration, priceWei)` when the consumer calls `requestAgreement`. The provider's background loop in `provider/app.py` polls for this event. When it sees one, it mints the NFT, approves the escrow, and calls `deposit()`. `provider/expiry.py` is a separate background task that sweeps expired slots based on `start_time + duration` — it does not consume chain events.

---

### 4.9 RPC and JSON-RPC over HTTP

**One-liner:** The standard way external code (like Python) talks to an Ethereum node — sending calls and transactions over a JSON-RPC HTTP API.

"RPC" stands for Remote Procedure Call — calling a function on another machine. Ethereum nodes expose a JSON-RPC API over HTTP (or WebSocket). To read chain state or send a transaction from Python, you send a JSON-RPC request to the node's URL. The `web3.py` library handles this automatically when you give it a provider URL — you write `w3.eth.get_balance(address)` and `web3.py` translates that into a `eth_getBalance` JSON-RPC call under the hood.

Read-only calls (like `ownerOf`) are free and instant — they execute locally on the node without broadcasting a transaction. Write calls (like `requestAgreement`) require a signed transaction, cost gas, and take at least one block time (~1 second on Anvil) to confirm.

**In this project:** `RPC_URL=http://anvil:8545` (in Docker) or `http://localhost:8545` (locally). All on-chain calls in `consumer/mcp_server.py` and `provider/mcp_server.py` go through `Web3(Web3.HTTPProvider(RPC_URL))`.

---

### 4.10 Anvil

**One-liner:** A local fake Ethereum node that runs instantly, produces deterministic test accounts, and is perfect for development.

Anvil is part of the Foundry toolkit. It spins up a complete Ethereum node in seconds, pre-loads 10 test accounts with 10,000 ETH each, mines a new block every second (configurable), and accepts any valid transaction without real gas fees. Because it is deterministic and local, contracts deploy the same way every time and tests run fast. Anvil also supports instant mining mode (no delay) and can impersonate any address for testing.

Anvil is important for this project because the full purchase flow involves real on-chain transactions — you cannot mock the smart contract layer without fundamentally changing the demo. Anvil lets those real transactions run locally at no cost.

**In this project:** Anvil runs as the `anvil` service in `docker-compose.yml`, exposed on port `:8545`. The test accounts are derived from the BIP-39 mnemonic `"test test test test test test test test test test test junk"` — the keys in `.env.example` correspond to accounts `[0]`, `[1]`, and `[2]` of this mnemonic.

---

### 4.11 Foundry and Forge

**One-liner:** A fast Ethereum development toolkit; Forge is its test and build tool, and it also includes Anvil and Cast.

Foundry is the modern alternative to Truffle/Hardhat for Ethereum development. The toolkit has four components: `forge` (build, test, deploy contracts), `cast` (send transactions and query the chain from the command line), `anvil` (local testnet — see §4.10), and `chisel` (interactive Solidity REPL). `forge build` compiles Solidity contracts and generates ABI JSON files that Python's `web3.py` uses to call the contracts. `forge script` runs a Solidity deployment script, broadcasting transactions to the target chain.

Foundry is written in Rust and is significantly faster than the older JavaScript-based toolchains. Foundry tooling is distributed as Docker images, so you do not need to install it locally if you use Docker Compose.

**In this project:** `contracts/foundry.toml` configures the Foundry project. Deployment is done by running `forge script script/Deploy.s.sol` — this is the `deployer` service in `docker-compose.yml`. You can also trigger it manually with `make contracts`. After deployment, `contracts/deployments/local.json` is written with the deployed contract addresses.

---

## 5. Tokens and NFTs

### 5.1 ERC-721

**One-liner:** The Ethereum standard that defines how non-fungible tokens (NFTs) work — unique, non-interchangeable tokens each with a distinct ID and owner.

ERC-721 is an interface standard (a set of functions every compliant contract must implement). The key functions are `ownerOf(tokenId)` (who owns this token?), `transferFrom(from, to, tokenId)` (move it), and `approve(to, tokenId)` (allow someone else to move it). Unlike ERC-20 tokens (fungible coins where one token is identical to another — like dollars), each ERC-721 token has a unique integer ID and may carry distinct metadata. This makes ERC-721 suitable for representing anything unique: art, event tickets, game items, or — as here — service entitlements.

The standard was proposed in 2018 and is now implemented by OpenZeppelin's battle-tested `ERC721.sol` base contract, which handles bookkeeping (owner maps, approvals, safe transfers) so application contracts only need to add domain-specific logic.

**In this project:** `BandwidthNFT.sol` implements ERC-721. It extends OpenZeppelin's `ERC721` base contract. The symbol is `BWNFT`. Each token represents one bandwidth service entitlement, with on-chain metadata recording the agreement ID, Mbps, duration, and the network endpoint.

---

### 5.2 NFT as a credential

**One-liner:** Instead of a username/password or off-chain certificate, the NFT itself is the proof of access — whoever owns it on-chain holds the right to use the service.

A credential proves you are authorized to do something. Traditionally, credentials are stored in a database and verified by a server that trusts its own records. Using an NFT instead means the credential lives on the blockchain — immutable, publicly verifiable, and not controlled by the provider. The consumer holds the NFT in their wallet; the provider checks the chain to verify ownership.

**In this project:** when the consumer buys bandwidth, the provider mints a `BandwidthNFT` tied to that agreement. The NFT is transferred to the consumer's wallet. When the consumer wants to activate the service, it presents this NFT (via a signed nonce) — no passwords, no centralized database lookup needed.

---

### 5.3 ownerOf check

**One-liner:** Calling `ownerOf(tokenId)` on the NFT contract returns the current owner's address — the on-chain source of truth for credential validity.

`ownerOf` is part of the ERC-721 standard. Any code can call it (it is a `view` function, meaning it reads state and costs no gas). By calling it and comparing the result to the signer's recovered address, the provider can confirm the credential is genuine without any off-chain database. There is no way to fake this check — the blockchain's consensus enforces who actually owns the token.

The full verification sequence is: (1) check the nonce timestamp is within ±300 seconds of now (prevents replay attacks), (2) recover the signer address from the ECDSA signature over the nonce, (3) call `ownerOf(tokenId)` on chain and confirm the on-chain owner equals the recovered signer, (4) check the agreement status is `ACTIVE`. All four must pass for activation to proceed.

**In this project:** the provider's `verify_credential_ownership` MCP tool in `provider/mcp_server.py` calls `nft.functions.ownerOf(token_id).call()`. If the recovered ECDSA signer of the nonce matches the token's on-chain owner, the credential is valid. This check is the first thing the `activate` A2A action performs.

---

## 6. Payment, escrow, and atomic swap

### 6.1 Escrow

**One-liner:** A neutral holding account that keeps funds locked until both parties have fulfilled their obligations — then releases them automatically.

In a traditional purchase, you trust the seller to deliver after you pay, or the seller trusts you to pay after delivery. Escrow removes that trust requirement: a neutral third party (here, the smart contract) holds the payment until the conditions are met. Smart contracts make this trustless — the rules are code that neither party can change after deployment. This is particularly important for autonomous agents because there is no human to step in if a party misbehaves.

In real-world real estate, an escrow company holds the buyer's funds until title transfers. The smart contract here plays the same role, but the release logic is automated code rather than a human reviewing paperwork.

**In this project:** `BandwidthEscrow.sol` is the escrow. The consumer calls `requestAgreement()` with ETH attached, which locks it in the contract. The ETH stays there until the provider completes the swap by calling `escrow.deposit(agreementId, tokenId)`, at which point ETH flows to the provider and the NFT flows to the consumer simultaneously.

---

### 6.2 Atomic swap

**One-liner:** A trade where both sides of the exchange happen in one indivisible operation — either both complete or neither does.

"Atomic" in computing means "all or nothing." An atomic swap ensures that the buyer gets the goods if and only if the seller gets paid. On Ethereum, a single transaction either succeeds (all state changes apply) or reverts (all state changes undo). This makes it possible to swap two assets — ETH for an NFT — without any trust in the other party.

**In this project:** the `deposit()` function in `BandwidthEscrow.sol` performs the atomic swap. In a single transaction it: (1) sets the agreement status to ACTIVE, (2) transfers the NFT from provider to consumer, and (3) sends ETH to the provider. If the ETH transfer fails (line 122 of `BandwidthEscrow.sol`), the entire transaction reverts — the NFT is not moved and the ETH stays in escrow.

---

### 6.3 Status state machine on-chain (NONE → REQUESTED → ACTIVE)

**One-liner:** Each escrow agreement progresses through defined states — NONE, REQUESTED, ACTIVE, CLOSED, CANCELLED — and the contract enforces that transitions only happen in the allowed order.

The `Status` enum in `BandwidthEscrow.sol` tracks where an agreement is in its lifecycle:
- `NONE` (0) — agreement ID has never been used
- `REQUESTED` (1) — consumer locked ETH; waiting for provider
- `ACTIVE` (2) — atomic swap completed; NFT with consumer, ETH with provider
- `CLOSED` (3) — reserved for future use
- `CANCELLED` (4) — agreement cancelled; ETH refunded to consumer

The contract rejects any operation that violates the allowed transitions (e.g., you cannot `deposit()` into a `NONE` or `ACTIVE` agreement).

**In this project:** both Python services read the agreement status by calling `escrow.functions.getAgreement(agreementId).call()` and indexing into the result tuple. The `await_settlement` MCP tool in `consumer/mcp_server.py` polls until it sees status `ACTIVE`.

---

### 6.4 deposit() and refund()

**One-liner:** `deposit()` completes the swap (ETH → provider, NFT → consumer); `cancel()` refunds the consumer if the provider never responds.

The `deposit()` function is called by the provider after minting the NFT and approving the escrow contract to transfer it. It is the trigger for the atomic swap (§6.2). The refund path — called `cancel()` in `BandwidthEscrow.sol` — lets the consumer reclaim their ETH if the provider does not fulfill the agreement within one hour (`requestDeadline = block.timestamp + 1 hours`). Anyone can call `cancel()` after the deadline (to prevent ETH being locked forever if the provider goes offline).

The one-hour deadline is a safety valve. In the happy path, `deposit()` is called within a few seconds of `requestAgreement()`. The deadline only matters if the provider crashes or the network is congested. No mechanism currently auto-calls `cancel()` on behalf of the consumer — they would need to do it manually or have a watchdog service.

**In this project:** `provider/expiry.py` runs a 30-second background sweep (`expiry_sweep_loop`) that revokes SDN allocations for expired slots. The `cancel()` function on the contract handles on-chain refunds; `provider/expiry.py` handles the off-chain side (freeing the slot back to inventory via `slot_pool.release(agreement_id)`).

---

## 7. Networking and SDN

### 7.1 REST API

**One-liner:** A style for designing HTTP APIs where each URL represents a resource and HTTP verbs (GET, POST, DELETE) describe the action.

REST (Representational State Transfer) is a set of conventions — not a strict standard — for building HTTP APIs. `GET /catalog` means "give me the catalog." `POST /chat` means "create a new chat interaction." REST APIs return JSON (usually). When people say "call the API," they almost always mean making an HTTP request to a REST endpoint.

**In this project:** the consumer agent exposes a REST API on `:8001` with endpoints including `/chat` (start a purchase), `/catalog_proxy` (browse provider offerings), and `/address` (return the consumer's Ethereum address). The provider exposes REST at `:8002` with `/catalog`, `/quote`, `/inventory`, and `/address`.

---

### 7.2 Port (TCP)

**One-liner:** A number (0–65535) that identifies which program on a machine should receive an incoming network connection.

A machine can run many network services at once. Ports let the OS route each incoming connection to the right program. By convention, web traffic uses port 80 (HTTP) or 443 (HTTPS). In development, apps pick high-numbered ports to avoid conflicts. When you see `http://localhost:8001`, the `8001` is the port.

**In this project:** port assignments are fixed across all config files:
- `:8001` — consumer agent (FastAPI)
- `:8002` — provider agent (FastAPI)
- `:8501` — consumer UI (Streamlit)
- `:8545` — Anvil blockchain node (Ethereum JSON-RPC)
- `:11434` — Ollama LLM server

---

### 7.3 SDN (Software-Defined Networking)

**One-liner:** An approach to networking where a software controller programs network devices (routers, switches) rather than each device being manually configured.

Traditional networks require a human to log into each router or switch and type vendor-specific CLI commands. SDN separates the "control plane" (deciding where traffic goes and at what rate) from the "data plane" (actually forwarding packets at line speed). A central software controller pushes configuration to many devices at once via standard APIs (like gNMI). This makes networks programmable: a script or AI agent can provision a new service, change a rate limit, or revoke access — all without a human network engineer touching the CLI.

PE (Provider Edge) is industry shorthand for the router at the network provider's edge that connects to the customer. CE (Customer Edge) is the router or device at the customer's premises. The PE enforces the bandwidth policy; the CE is connected to the PE and gets its traffic shaped.

**In this project:** the paper this project accompanies proposes using SDN to automate bandwidth provisioning. When the consumer activates their credential, the provider's `allocate_bandwidth` MCP tool pushes a policer configuration to a Nokia SR Linux router (PE = Provider Edge) and applies Linux traffic shaping to the connected customer equipment (CE = Customer Edge).

---

### 7.4 Traffic shaping with `tc tbf`

**One-liner:** `tc tbf` is a Linux command that limits how fast a network interface can send data — the tool used to enforce bandwidth caps on CE containers.

`tc` is the Linux traffic control tool. `tbf` is "Token Bucket Filter" — a rate-limiting algorithm. The token bucket fills at the allowed rate (e.g., 5 Mbps); each packet sent consumes tokens. When the bucket empties, packets are queued or dropped. This is how internet service providers enforce data rate plans.

**In this project:** when `SDN_MOCK=false` and ContainerLab is running, the provider's `allocate_bandwidth` MCP tool calls `srl_bandwidth.allocate_bandwidth` from the sibling repo. That function runs a `tc tbf` command on the CE container (e.g., `clab-bandwidth-poc-ce3`) to cap egress at the purchased Mbps rate.

---

### 7.5 gNMI

**One-liner:** A protocol for pushing and reading configuration on network devices using a structured data model (YANG).

gNMI (gRPC Network Management Interface) is an open-source protocol that replaces older, clunkier methods (SSH + CLI, SNMP) for configuring network devices. It uses gRPC (Google's RPC framework) and structures configuration data using YANG models — a formal language for describing network configuration. Nokia SR Linux, a software router, supports gNMI natively.

YANG (Yet Another Next Generation) is a data modelling language (RFC 6020) designed specifically to describe the configuration and state of network devices. Each vendor provides YANG models for their device features; a gNMI `Set` RPC pushes a JSON or Protobuf payload that matches the model to configure the device programmatically — no screen scraping or CLI parsing needed.

**In this project:** when `SDN_MOCK=false`, the `srl_bandwidth` library (from the sibling repo `../srl-gnmi-bandwidth-poc`) uses gNMI to push a bandwidth policer configuration to the SR Linux PE router. This is real Nokia tooling that would work on a production SR Linux device, not just a simulation.

---

### 7.6 ContainerLab

**One-liner:** A tool that spins up a virtual network of routers and links using Docker containers, so you can test network automation without physical hardware.

ContainerLab defines a network topology in a YAML file and uses Docker to run network operating system containers (Nokia SR Linux, Arista cEOS, etc.) connected by virtual links. The result is a programmable test network that behaves like real hardware. Each node is a Docker container; links are virtual Ethernet pairs. You can SSH into each node, push gNMI configuration, and run traffic generators — all locally on a Linux host.

ContainerLab is widely used in the network automation community because it bridges the gap between simulation and production. The same automation code that configures a ContainerLab topology will configure real SR Linux hardware with no changes.

**In this project:** the real SDN demo requires ContainerLab. The Makefile includes `clab-up` and `clab-down` targets that delegate to the sibling repo at `../srl-gnmi-bandwidth-poc`. Run `make clab-up` first, then `make demo-real`. Without ContainerLab, keep `SDN_MOCK=true` (the default).

---

### 7.7 Mock vs real activation

**One-liner:** `SDN_MOCK=true` (default) lets you run the full purchase flow without needing real network hardware; `SDN_MOCK=false` drives actual ContainerLab routers.

The SDN activation step — pushing gNMI config and applying `tc tbf` — requires ContainerLab to be running, which needs a Linux host with Docker. For development, CI, and demo purposes, `SDN_MOCK=true` makes the `allocate_bandwidth` tool return a canned success response without touching any network hardware.

**In this project:** the `SDN_MOCK` environment variable (default `"true"`) is read at module load time in `provider/mcp_server.py`. When `SDN_MOCK=true`, the `allocate_bandwidth`, `revoke_bandwidth`, and `verify_bandwidth` tools all return mocked results (`gnmi_pushed: false`, `tc_applied: false`, `message: "mocked"`). Set `SDN_MOCK=false` in `.env` and run `make demo-real` to exercise the real path.

---

## 8. State machines

### 8.1 What a state machine is

**One-liner:** A model where a system is always in exactly one of a finite set of states, transitions happen only on defined triggers, and only allowed transitions are permitted.

A state machine has three parts: a set of possible states (e.g., IDLE, RUNNING, DONE), a set of inputs or events that can trigger transitions (e.g., START, STOP, ERROR), and a transition table that says "if in state X and event Y occurs, go to state Z." The system always has a "current state." State machines are useful for anything that has a lifecycle because they make illegal transitions impossible to reach. A traffic light is a classic example — it cycles GREEN → YELLOW → RED → GREEN and there is no direct GREEN → RED transition.

In software, state machines reduce bugs by eliminating implicit "invalid state" combinations. Instead of checking a dozen boolean flags, you check one current-state value. LangGraph (used here for the consumer's workflow) is a Python library that lets you define a state machine as a directed graph with typed state and conditional edges.

**In this project:** state machines appear at three levels — on-chain, in inventory management, and in the agent workflow. See §8.2 for details.

---

### 8.2 Three state machines in this project

**One-liner:** The project uses three interlocking state machines: the on-chain agreement status, the slot pool reservation lifecycle, and the consumer's LangGraph workflow.

**State machine 1: On-chain agreement status (`BandwidthEscrow.sol`)**

Already described in §6.3. Values: `NONE(0) → REQUESTED(1) → ACTIVE(2)`; also `CANCELLED(4)` if aborted. Enforced by the Solidity contract — no code can skip steps or go backward.

**State machine 2: SlotPool (free / active per slot)**

Each slot in `provider/inventory.txt` is in one of two states at the Python level: free (`agreementId = null`, `expiresAt = null`) or active (`agreementId = <id>`, `expiresAt = <timestamp>`). The `SlotPool` in `shared/slot_pool.py` transitions a slot from free to active on `reserve(...)` and back to free on `release(...)` or when `expiresAt` passes. Cross-reference §6.3 for the on-chain side.

**State machine 3: Consumer LangGraph workflow**

The consumer's purchase workflow, introduced in commit `18d8c6d` and implemented in `consumer/graph.py`, is a LangGraph state machine. Nodes are: `browse_node → pick_tier_node → quote_node → lock_node → settle_node → present_node → summary_node`. At each node, if an error is set in the state, control flows to `error_node → END` instead of the happy path. Cross-reference §3.2 (MCP) and §2.5 (agent) for how the nodes call tools.

**In this project:** all three state machines are in play on every purchase. The LangGraph workflow (state machine 3) drives the consumer; each node's side-effects update the on-chain status (state machine 1) and the slot reservation (state machine 2). A purchase is only fully complete when all three machines reach their terminal "active/done" state simultaneously.

