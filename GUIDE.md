# Complete Beginner's Guide to Ollama Agent Simulation

> **Who this is for:** Someone who has never written code, never used a terminal, and has no idea what "blockchain," "API," or "AI agent" means. Every concept is explained from scratch.

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [The Big Picture — A Story](#2-the-big-picture--a-story)
3. [Every File and Folder](#3-every-file-and-folder)
4. [Every Technology Used](#4-every-technology-used)
5. [Every Key Concept](#5-every-key-concept)
6. [How Data Flows](#6-how-data-flows)
7. [How to Run and Use the Project](#7-how-to-run-and-use-the-project)
8. [What Can Go Wrong](#8-what-can-go-wrong)
9. [Glossary](#9-glossary)

---

## 1. What This Project Is

### In Plain English

Imagine you want to rent a parking spot. Normally you would call the parking lot owner, agree on a price, pay, and get a ticket. If either side cheats — say the lot owner takes your money but never gives you the spot — you have a problem.

This project does the same thing, but with **internet bandwidth** (how fast your internet connection is) and **no humans involved**. Two computer programs — one acting as a buyer and one acting as a seller — talk to each other, agree on a price, and swap money for a service ticket, all automatically and all in a way that makes cheating impossible.

The clever part: neither side can run off with the money. A piece of neutral code called a **smart contract** (think of it as a robotic escrow officer that follows its rules perfectly and cannot be bribed) holds the money in the middle until both sides have delivered what they promised. Only then does it release the money to the seller and give the service ticket to the buyer.

### What Problem It Solves

In the future, AI programs will buy and sell things from each other constantly — computing power, data storage, internet access, and more. But how do you make sure a machine pays only after it gets what it paid for? And how does the seller know it will be paid before handing over the goods?

This project is a working proof of concept (a real, running demonstration) that answers those questions. It shows a path toward AI agents doing safe, trustless commerce with each other.

### Who Would Use It

- **Researchers** studying how AI agents can trade with each other
- **Software engineers** building systems where programs buy and sell services automatically
- **Students** learning about blockchain, smart contracts, or AI agents
- **Anyone curious** about what the automated economy of the future might look like

---

## 2. The Big Picture — A Story

Let's walk through exactly what happens from the moment you type a message to the moment you see a result.

### Meet the Characters

- **You** — sitting at a browser, typing what you want
- **The Consumer Agent** — an AI assistant whose job is to buy bandwidth for you
- **The Provider Agent** — a program that sells bandwidth and manages inventory
- **The Gateway** — a bouncer at the door who checks your ticket before letting you in
- **The Blockchain** — a shared, tamper-proof record book that holds money and records deals
- **The Smart Contracts** — two robot rule-enforcers living inside the blockchain

### The Story

**You type:** *"I need 100 Mbps for 10 minutes."*

**Step 1 — The Buyer Wakes Up**
Your message arrives at the Consumer Agent. The Consumer Agent is powered by a local AI language model (think of it like a pocket-sized ChatGPT running on your own computer). It reads your message and begins to think about what to do.

**Step 2 — Window Shopping**
The Consumer Agent calls out to the Provider Agent: *"What do you have for sale?"* The Provider Agent replies with a menu — three options called "small," "medium," and "large," each with a different speed and price. This conversation uses a protocol (a shared language for programs) called MCP, which stands for Model Context Protocol. Think of MCP as a standardized ordering form both agents understand.

**Step 3 — Placing an Order**
The AI decides the "medium" package (100 Mbps) matches your request. It asks for a quote — like asking for a price before buying. The Provider Agent creates a unique order number (called an `agreementId`) and sends back the price.

**Step 4 — Locking the Money**
Now the Consumer Agent takes that price in ETH (a digital currency, like tokens in an arcade) and sends it to the Smart Contract, a neutral robotic escrow officer. The contract locks the money safely. Neither side can touch it yet. The contract records: *"A deal is pending — someone wants 100 Mbps for 0.02 ETH."*

**Step 5 — The Seller Hears the Bell**
The Provider Agent has been quietly watching the blockchain, like a shop owner glancing at the door every few seconds. It sees that money has just been locked for a deal. Time to fulfill the order.

**Step 6 — Minting the Service Ticket**
The Provider Agent creates a digital certificate — called an NFT (a Non-Fungible Token, essentially a unique, unforgeable receipt) — that says: *"The holder of this token is entitled to 100 Mbps of bandwidth for 600 seconds, starting now, reachable at this address."* This certificate is stored on the blockchain, so it cannot be faked.

**Step 7 — The Atomic Swap**
This is the magic moment. The Provider Agent calls the Smart Contract and says: *"Here is the service ticket — now complete the deal."* The Smart Contract does both things in one single action: it gives the service ticket to the buyer AND releases the money to the seller. It cannot do one without the other. Either both happen, or neither does. This is called an **atomic swap**.

**Step 8 — Showing the Ticket at the Door**
The Consumer Agent now owns the NFT. It goes to the Gateway and says: *"I own ticket number 3, and here is my signature to prove it."* The Gateway checks the blockchain, confirms the ticket is real and belongs to the Consumer Agent, and responds with the actual service details: the speed, how much time is left, and where to connect.

**Step 9 — You See the Result**
The Consumer Agent reports back to your browser with the full story: which package was chosen, what was paid, the ticket number, and confirmation that the service is live.

The entire process takes about 30–60 seconds.

---

## 3. Every File and Folder

This section walks through every file and folder in the project. Think of it as a guided tour of a building — we'll visit every room and explain what happens inside.

### The Root Level (the front lobby)

These files sit at the very top of the project, not inside any subfolder.

---

**`pyproject.toml`**
*What it is:* A configuration file (a settings document) that lists all the software libraries this project needs. Think of it as a shopping list — when you set up the project for the first time, a tool called `uv` reads this list and installs everything.
*What breaks without it:* Nothing would install. The project could not run at all.
*Beginner note:* You rarely need to touch this file unless you are adding a new library.

---

**`uv.lock`**
*What it is:* A detailed record of the exact versions of every library installed. While `pyproject.toml` says "I need version 6 or higher of web3," `uv.lock` records "I installed version 6.20.3 exactly."
*What breaks without it:* The project might install slightly different versions and behave unexpectedly.
*Beginner note:* Never edit this file by hand. It is managed automatically.

---

**`.env.example`**
*What it is:* A template showing what secret settings the project needs (like private keys and web addresses). It contains example values that are safe to share publicly.
*What breaks without it:* Nothing directly, but new users would not know what settings to provide.
*Beginner note:* Copy this file to `.env` and fill in your own values before running the project.

---

**`.env`**
*What it is:* Your personal settings file. It contains private keys (like passwords for your fake blockchain wallet) and the addresses of all the running services.
*What breaks without it:* The program cannot connect to the blockchain or to the other agents.
*Beginner note:* This file is hidden from git (version control) on purpose — it should never be uploaded to the internet.

---

**`Makefile`**
*What it is:* A file full of shortcuts. Instead of typing long, complex commands, you type `make up` (to start everything) or `make down` (to stop everything) and the Makefile runs the long command for you.
*What breaks without it:* Nothing breaks, but you would have to type much longer commands yourself.
*Beginner note:* Think of it like a TV remote — it is just convenience.

---

**`docker-compose.yml`**
*What it is:* A blueprint that tells Docker (a tool for running isolated mini-computers) how to start all six services of this project at once, in the right order, with the right settings.
*What breaks without it:* You could still run everything manually in separate terminals, but the one-command startup (`make up`) would not work.
*Beginner note:* This is one of the most important files for running the whole system.

---

**`Dockerfile.consumer` and `Dockerfile.provider`**
*What they are:* Recipes for building the isolated mini-computers (called containers) that run the consumer and provider agents. Each Dockerfile says: "Start from a clean Python environment, install these libraries, copy in this code, and run this command."
*What breaks without them:* Docker cannot build the containers, so `make up` fails.
*Beginner note:* You do not need to edit these unless you are adding files or changing how the app starts.

---

**`README.md`**
*What it is:* The first document anyone reads when they find the project. It gives a quick overview and setup instructions.
*What breaks without it:* Nothing in the software breaks, but newcomers have no guidance.

---

### The `contracts/` Folder (the rule book)

This folder contains the smart contracts — the robot rule-enforcers that live on the blockchain.

---

**`contracts/src/BandwidthNFT.sol`**
*What it is:* Code written in a language called Solidity that defines the service ticket (the NFT). It records on-chain: the agreement number, the bandwidth speed, how long the service lasts, when it started, and the address to connect to.
*What breaks without it:* There would be no way to issue or verify service tickets.
*Beginner note:* `.sol` files are "smart contracts" — programs that run permanently on the blockchain and cannot be changed after they are deployed.

---

**`contracts/src/BandwidthEscrow.sol`**
*What it is:* The most important contract. It holds money in the middle and performs the atomic swap (giving the buyer the ticket while paying the seller) in a single, un-cheatable step.
*What breaks without it:* The whole payment system collapses. There is nothing to ensure fair exchange.
*Beginner note:* This contract has a "state machine" — the deal goes through stages: NONE → REQUESTED → ACTIVE. Each stage has rules about what can happen next.

---

**`contracts/script/Deploy.s.sol`**
*What it is:* A script (a set of instructions) that deploys (publishes) the two contracts to the blockchain and saves their addresses (like street addresses, but for blockchain programs) to a file.
*What breaks without it:* You would have to deploy contracts manually, which is complex.

---

**`contracts/deployments/local.json`**
*What it is:* An automatically generated file that records where each contract was deployed (their blockchain addresses).
*What breaks without it:* The Python code cannot find the contracts. Everything fails.
*Beginner note:* This file is created automatically when you run the deployment script. Do not create it by hand.

---

**`shared/abi/BandwidthNFT.json` and `shared/abi/BandwidthEscrow.json`**
*What they are:* ABI files. ABI stands for Application Binary Interface — think of it as a menu that tells the Python code exactly which functions the contracts have and what inputs they accept.
*What breaks without them:* Python cannot communicate with the contracts at all.
*Beginner note:* These files are also generated automatically during compilation.

---

### The `consumer/` Folder (the buyer's brain)

---

**`consumer/app.py`**
*What it is:* The heart of the Consumer Agent. It runs a web server on port 8001, receives your chat message, loads the AI language model, runs the negotiation and payment logic, and returns the result.
*What breaks without it:* The entire buyer side of the system goes down.
*Beginner note:* This is the most complex file in the project. It connects the AI, the blockchain, and the other agents.

---

**`consumer/mcp_client.py`**
*What it is:* A helper file that handles the Consumer Agent's communication with the Provider Agent using the MCP protocol. It discovers what tools the provider offers and calls them.
*What breaks without it:* The consumer has no way to contact the provider to get the catalog or a quote.

---

**`consumer/ui.py`**
*What it is:* The browser interface — the web page you look at. It sends your typed message to the Consumer Agent and displays the response in a nice, step-by-step timeline.
*What breaks without it:* You would have no visual interface. You could still send requests using technical tools, but the friendly chat window would be gone.
*Beginner note:* This file is much simpler than `app.py`. It is mostly layout and display code.

---

### The `provider/` Folder (the seller's business)

---

**`provider/app.py`**
*What it is:* The main Provider Agent server running on port 8002. It hosts the catalog of services, creates quotes, runs the MCP server (so the consumer can discover its tools), and continuously watches the blockchain for new orders.
*What breaks without it:* The seller side of the system is completely gone.

---

**`provider/mcp_server.py`**
*What it is:* Defines the two tools that the Provider Agent exposes through MCP: `get_catalog` (returns the service menu) and `request_quote` (generates a price for a specific package).
*What breaks without it:* The Consumer Agent cannot discover what the provider sells.

---

**`provider/catalog.py`**
*What it is:* Defines the three bandwidth packages (small, medium, large), their prices, slot counts, and durations. Also handles generating unique order numbers and managing how many slots are available.
*What breaks without it:* There is no product to sell. The catalog is empty.

---

**`provider/gateway.py`**
*What it is:* A separate web server on port 8003 that acts as the bouncer. Before it gives out service details, it checks that you actually own the NFT (the service ticket). It does this by asking you to sign a short message with your private key, proving you are who you say you are.
*What breaks without it:* Anyone could pretend to own a service they did not pay for. The access control is gone.

---

**`provider/inventory.txt`**
*What it is:* A simple text file used as a database (a storage system) to track how many slots of each bandwidth tier are currently in use and when they expire.
*What breaks without it:* The provider has no memory of what is already sold. It would oversell, giving out more slots than it has.
*Beginner note:* In a real production system you would use a proper database. Here, a text file is used for simplicity.

---

### The `shared/` Folder (the connective tissue)

---

**`shared/contracts.py`**
*What it is:* A utility file that reads the contract addresses from `deployments/local.json` and the ABIs from the `abi/` folder, then creates Python objects you can use to call contract functions.
*What breaks without it:* Both the consumer and provider lose their ability to interact with the blockchain.

---

### The `tests/` Folder (the quality checkers)

---

**`tests/test_catalog.py`**
*What it is:* Automated tests (small programs that check whether the catalog logic works correctly). It verifies there are exactly three tiers, that the pricing is correct, and that quotes can be generated.
*What breaks without it:* Nothing in the running system, but you lose the ability to automatically verify that the catalog still works after you make changes.

---

**`tests/test_mcp_client.py`**
*What it is:* Tests that verify the MCP communication utilities correctly translate between MCP's tool format and the format the AI model understands.
*What breaks without it:* Again, nothing in production, but you lose automated safety checks.

---

### The `docs/` Folder (the paper trail)

Contains implementation plans, design specifications, and notes used during development. These are reference documents for the developers — removing them breaks nothing in the running system.

---

### The `paper/` Folder (the research)

Contains the academic paper this project is based on, written in LaTeX (a document formatting system common in academia). Removing this breaks nothing in the software.

---

## 4. Every Technology Used

### Python

*What it is:* The main programming language this project is written in. Python is one of the most popular languages in the world, known for being readable — it almost looks like English.
*Why it was chosen:* Python has excellent libraries for AI, blockchain, and web services. It is also widely known, making the project easier for others to understand and contribute to.
*Real-world equivalent:* Think of Python as the everyday spoken language everyone in the office uses to get things done.

---

### FastAPI

*What it is:* A Python library (a pre-built set of tools you import into your code) for building web servers — programs that listen for requests over the internet and send back responses.
*Why it was chosen:* It is fast, modern, and automatically generates documentation for your server's endpoints.
*Real-world equivalent:* A receptionist at a company. When someone calls (sends a request), the receptionist (FastAPI) takes the message and routes it to the right person (your code).
*Where it appears:* Every agent — consumer, provider, and gateway — uses FastAPI to host its web server.

---

### Uvicorn

*What it is:* The program that actually runs the FastAPI server. FastAPI describes *what* the server should do; Uvicorn is the engine that keeps it running and listening for requests.
*Why it was chosen:* It is the standard, high-performance way to run FastAPI applications.
*Real-world equivalent:* If FastAPI is the building design, Uvicorn is the construction crew that actually builds and maintains it.

---

### Streamlit

*What it is:* A Python library that lets you build browser-based web interfaces with just a few lines of Python code, without needing to know web design.
*Why it was chosen:* It makes creating a visual chat interface incredibly simple, which is ideal for a research prototype.
*Real-world equivalent:* A pre-built storefront kit — you just fill in your content and instantly have a shop window.
*Where it appears:* `consumer/ui.py` — the chat interface you see in the browser.

---

### Ollama

*What it is:* A tool that lets you run AI language models (programs that understand and generate human-like text) entirely on your own computer, with no internet connection required.
*Why it was chosen:* Privacy, speed, and no usage fees. Everything stays local.
*Real-world equivalent:* Having a personal assistant who lives in your house rather than calling a remote call center every time you have a question.
*Where it appears:* `consumer/app.py` uses Ollama to run the AI that reasons about what to buy.

---

### Web3.py

*What it is:* A Python library that allows Python code to talk to the Ethereum blockchain — sending transactions, reading data, calling smart contract functions.
*Why it was chosen:* It is the standard Python library for Ethereum interaction.
*Real-world equivalent:* An interpreter who speaks both Python (the language of your code) and Ethereum (the language of the blockchain), translating back and forth.
*Where it appears:* `shared/contracts.py`, `consumer/app.py`, and `provider/app.py` all use it to interact with the contracts.

---

### Solidity

*What it is:* A programming language designed specifically for writing smart contracts on the Ethereum blockchain.
*Why it was chosen:* It is the dominant language for Ethereum contracts and compiles to code that runs directly on the blockchain virtual machine.
*Real-world equivalent:* The language lawyers use to write binding contracts — very precise, very formal, very hard to misinterpret.
*Where it appears:* `contracts/src/BandwidthNFT.sol` and `contracts/src/BandwidthEscrow.sol`.

---

### Foundry (Anvil and Forge)

*What it is:* A toolkit for Ethereum development. **Forge** compiles and tests Solidity contracts. **Anvil** runs a fake, local Ethereum blockchain on your computer with no real money.
*Why it was chosen:* It is fast, modern, and developer-friendly. Anvil is perfect for testing because it resets every time you restart it.
*Real-world equivalent:* Anvil is like a board game version of the stock market — same rules, but you play with fake money so you can learn without risk.
*Where it appears:* `docker-compose.yml` starts Anvil as a service. Forge is used to compile and deploy the contracts.

---

### FastMCP

*What it is:* A Python library that makes it easy to build an MCP server — a server that exposes tools for AI agents to discover and call.
*Why it was chosen:* MCP is an emerging standard for AI agent communication. FastMCP removes the complexity of implementing the protocol manually.
*Real-world equivalent:* A standardized job posting board. Instead of every employer inventing their own format, everyone uses the same board so job seekers (AI agents) know exactly where to look and what format to expect.
*Where it appears:* `provider/mcp_server.py`.

---

### HTTPX

*What it is:* A Python library for making HTTP requests (sending messages from one program to another over the internet). It is used for direct REST API calls (a common way programs communicate) where MCP is not used.
*Why it was chosen:* It supports asynchronous requests (making multiple calls without waiting for each one to finish), which improves performance.
*Real-world equivalent:* A telephone — you pick it up, dial another program, speak (send a request), and listen (receive a response).

---

### Ethereum / ETH

*What it is:* Ethereum is a blockchain (a shared, distributed, tamper-proof ledger). ETH is its native currency, like dollars in the US economy.
*Why it was chosen:* Ethereum supports smart contracts — programmable rules that run automatically without a central authority.
*Real-world equivalent:* Imagine a public bulletin board where anyone can post a contract, and once posted, the contract executes itself without anyone's involvement.

---

### NFT (ERC-721 Token)

*What it is:* A Non-Fungible Token. "Non-fungible" means each one is unique — unlike dollars where every dollar is identical, each NFT is one-of-a-kind. An ERC-721 token is a specific technical standard for NFTs on Ethereum.
*Why it was chosen:* NFTs are ideal for representing unique service entitlements — this particular ticket represents this particular bandwidth allocation, not a generic one.
*Real-world equivalent:* A paper ticket to a specific concert seat. Each ticket is unique (different seat, different show) and proves you paid.

---

### Docker and Docker Compose

*What they are:* Docker creates isolated mini-computers (called containers) inside your real computer. Each container runs one piece of the project in isolation. Docker Compose is a tool that starts multiple containers at once from a single configuration file.
*Why they were chosen:* They guarantee the project runs the same way on every computer, regardless of what software you already have installed.
*Real-world equivalent:* Docker is like shipping containers on a cargo ship — each container holds one thing, is self-contained, and looks the same whether it is in Shanghai or Rotterdam.

---

### uv

*What it is:* A tool for managing Python dependencies (the libraries your code needs). It replaces older tools like `pip`.
*Why it was chosen:* It is much faster and more reliable than traditional Python package managers.
*Real-world equivalent:* A grocery delivery service that brings exactly the right items in exactly the right quantities, instead of you driving to multiple stores.

---

### MCP (Model Context Protocol)

*What it is:* An open standard (a shared rulebook) that defines how AI agents discover what tools are available on a server and how they call those tools.
*Why it was chosen:* It allows the consumer agent to discover the provider's capabilities without being hardcoded. Any MCP-compatible agent could plug in.
*Real-world equivalent:* Like a universal electrical outlet standard — any appliance with the right plug works anywhere, without needing special adapters.

---

## 5. Every Key Concept

### Smart Contracts

**Plain English:** A smart contract is a program that lives on a blockchain. Once deployed (published), no one can change its rules. It runs automatically when triggered, following its code exactly. It holds and moves money without trusting any single person.

**Analogy:** Imagine a vending machine. You put in a dollar, press the button for chips, and the machine gives you chips. No human cashier is involved. The machine cannot cheat you (give you nothing after taking your dollar) because it was built to execute the rules mechanically. A smart contract is a vending machine for financial agreements.

**In this project:** Two contracts — `BandwidthNFT` and `BandwidthEscrow` — live on the local Anvil blockchain. The Escrow contract acts as the neutral intermediary that makes the atomic swap happen.

---

### State Machine

**Plain English:** A state machine is a system that can only be in one "state" (condition) at a time, and can only move to the next state by following specific rules.

**Analogy:** A traffic light. It can only be red, yellow, or green. It cannot jump from red straight to yellow — it must follow the sequence. If something tries to break the rules (turn green from yellow without going red), the state machine rejects it.

**In this project:** Each agreement has a state: `NONE → REQUESTED → ACTIVE → CLOSED or CANCELLED`. The smart contract enforces these transitions. For example, you cannot cancel an already-active agreement, and you cannot activate an agreement that never existed.

---

### Escrow

**Plain English:** An escrow is a neutral holding place for money or assets during a transaction. A third party (in this case, the smart contract) holds the money until both sides deliver on their promises.

**Analogy:** When you buy a house, a title company holds your money while the paperwork is checked. Once everything is confirmed, the title company releases the money to the seller and gives you the title. Neither the buyer nor the seller can back out or steal the money in the middle.

**In this project:** `BandwidthEscrow.sol` holds the consumer's ETH after they call `requestAgreement()`. It releases the ETH to the provider only when the provider calls `deposit()` with the NFT.

---

### Atomic Swap

**Plain English:** An atomic swap is a transaction where two things are exchanged simultaneously. Either the exchange completes fully or it does not happen at all — there is no state where one party has both assets.

**Analogy:** Think of a simultaneous handoff in a spy movie — both agents hold their briefcases out, count to three, and swap at exactly the same instant. If either one lets go before the other, neither swap happens.

**In this project:** The `deposit()` function in `BandwidthEscrow.sol` transfers the NFT to the consumer AND the ETH to the provider in one single blockchain transaction. If any step fails, the entire transaction is rolled back.

---

### Blockchain and Transactions

**Plain English:** A blockchain is a shared record book that thousands of computers copy and verify. Every "transaction" (an action that changes something) is recorded permanently. No single person controls it.

**Analogy:** Imagine a public whiteboard in a town square where everyone can write. Before any new entry is added, the whole crowd verifies it is legitimate. Once written, no one can erase it. That is a blockchain.

**In this project:** We use Anvil, a fake blockchain that runs only on your computer. It behaves exactly like real Ethereum, but the "ETH" is not real money.

---

### Private Key and Signing

**Plain English:** A private key is a secret password that proves you are the owner of a blockchain account. When you "sign" a message with your private key, you create a mathematical proof that you — and only you — created that message. Anyone can verify the signature without knowing your private key.

**Analogy:** A wax seal on a letter. Only you have your unique signet ring (private key). Anyone can look at the seal and confirm it came from you, but they cannot copy the seal because they do not have your ring.

**In this project:** The consumer signs a nonce (a one-time number) when visiting the gateway. The gateway checks the signature to confirm the request truly came from the wallet address that owns the NFT.

---

### Nonce (in Authentication)

**Plain English:** A nonce is a number used exactly once, usually based on the current time. It prevents "replay attacks" — where someone records your valid request and sends it again later to trick the server.

**Analogy:** Imagine a bouncer who asks you to write down the current time and sign it. If someone takes your signed paper and tries to use it tomorrow, the bouncer rejects it because the timestamp is old.

**In this project:** The gateway uses time-based nonces. The consumer signs the current Unix timestamp (seconds since January 1, 1970). The gateway rejects signatures older than 5 minutes.

---

### Event and Event Listener

**Plain English:** When a smart contract does something significant (like receiving a payment), it can emit an "event" — a public announcement recorded on the blockchain. Other programs can watch for these announcements.

**Analogy:** A hotel front desk rings a bell when a guest checks in. Staff throughout the hotel hear the bell and know a new guest has arrived, without anyone calling each room individually.

**In this project:** When a consumer locks ETH in the escrow, the contract emits an `AgreementRequested` event. The provider agent runs a loop every 2 seconds, checking for new events. When it sees one, it knows to mint the NFT and complete the swap.

---

### API and REST API

**Plain English:** An API (Application Programming Interface) is a set of rules for how two programs talk to each other. A REST API is a common style of API where you communicate by sending requests to specific web addresses.

**Analogy:** A restaurant menu is an API. It tells you exactly what you can order (the available requests) and what you will get back (the responses). You do not need to know how the kitchen works.

**In this project:** The consumer, provider, and gateway all expose REST APIs. For example, the consumer exposes a `/chat` endpoint — when you send it a POST request with a message, it processes the request and returns a response.

---

### LLM (Large Language Model)

**Plain English:** A large language model is an AI program trained on vast amounts of text that can understand and generate human language. It can answer questions, follow instructions, and reason about problems.

**Analogy:** A very well-read assistant who has read millions of books and can help you make decisions, draft letters, or plan actions.

**In this project:** The consumer agent uses a local LLM (run through Ollama) to read your request, decide which bandwidth tier matches, and choose the right sequence of tool calls to fulfill the order.

---

### Tool Calling

**Plain English:** Modern AI language models can not only talk — they can also take actions by "calling tools." The developer defines a set of actions the AI can take (like "get the catalog" or "execute a payment"), and the AI decides when and how to use them.

**Analogy:** A human assistant who can not only give you advice but can also pick up the phone and make calls on your behalf, based on what you need.

**In this project:** The Consumer Agent's LLM has four tools available: `get_catalog`, `request_quote`, `execute_agreement`, and `check_agreement_status`. It reasons about your request and calls these in sequence.

---

### Port

**Plain English:** A port is like an apartment number inside a building. Your computer is the building, and different programs live in different apartments. When programs communicate, they use port numbers to find each other.

**In this project:** The consumer agent lives at port 8001, the provider at 8002, the gateway at 8003, the blockchain at 8545, and the browser UI at 8501.

---

## 6. How Data Flows

Let's follow a single user request — *"Buy me the cheapest bandwidth"* — all the way through the system and back.

### Stage 1: User Input

```
Your Browser (http://localhost:8501)
  ↓ You type: "Buy me the cheapest bandwidth"
  ↓ Streamlit sends: POST http://localhost:8001/chat
      Body: { "message": "Buy me the cheapest bandwidth" }
```

### Stage 2: Consumer Agent Receives the Request

```
Consumer Agent (port 8001, consumer/app.py)
  ↓ Receives the POST request
  ↓ Passes message to the LLM with a system prompt:
      "You are a bandwidth procurement agent. 
       You have these tools: get_catalog, request_quote, 
       execute_agreement, check_agreement_status."
  ↓ The LLM thinks: "I should get the catalog first."
```

### Stage 3: Catalog Fetch via MCP

```
Consumer Agent (via consumer/mcp_client.py)
  ↓ Opens MCP connection to: http://localhost:8002/mcp
  ↓ Sends: call_tool("get_catalog", {})
  
Provider Agent (port 8002, provider/mcp_server.py)
  ↓ Receives the MCP tool call
  ↓ Calls catalog.get_catalog_with_availability()
  ↓ Reads inventory.txt to check available slots
  ↓ Returns: [
      { "id": "small",  "bandwidthMbps": 50,  "priceEth": 0.01, "availableSlots": 10 },
      { "id": "medium", "bandwidthMbps": 100, "priceEth": 0.02, "availableSlots": 8  },
      { "id": "large",  "bandwidthMbps": 500, "priceEth": 0.08, "availableSlots": 5  }
    ]

Consumer Agent
  ↓ The LLM reads the catalog
  ↓ Decides: "The cheapest is 'small' at 0.01 ETH."
  ↓ Thinks: "Now I should request a quote for 'small'."
```

### Stage 4: Quote Request via MCP

```
Consumer Agent
  ↓ Calls: call_tool("request_quote", {
      "package_id": "small",
      "consumer_address": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"
    })

Provider Agent (provider/catalog.py)
  ↓ Generates a unique agreementId (e.g., 7391284650)
  ↓ Stores the quote in memory: pending_quotes[agreementId] = { package, consumer, price }
  ↓ Returns: {
      "agreementId": 7391284650,
      "priceWei":    "10000000000000000",   ← 0.01 ETH in smallest units
      "bandwidthMbps": 50,
      "durationSeconds": 600
    }

Consumer Agent
  ↓ The LLM receives the quote
  ↓ Thinks: "Now I should execute the agreement on-chain."
```

### Stage 5: On-Chain Transaction

```
Consumer Agent (consumer/app.py, execute_agreement function)
  ↓ Connects to blockchain at: http://localhost:8545 (Anvil)
  ↓ Loads BandwidthEscrow contract using:
      - address from deployments/local.json
      - ABI from shared/abi/BandwidthEscrow.json
  ↓ Builds a transaction:
      escrow.functions.requestAgreement(
        agreementId=7391284650,
        provider="0x70997970...",
        bandwidthMbps=50,
        durationSeconds=600
      )
      value=10000000000000000  ← the price in Wei
  ↓ Signs the transaction with CONSUMER_PRIVATE_KEY
  ↓ Sends it to Anvil
  ↓ Waits for confirmation (about 1 second)
  
Blockchain (Anvil)
  ↓ Processes the transaction
  ↓ BandwidthEscrow.sol:
      - Creates Agreement struct in storage
      - Sets status = REQUESTED
      - Locks the 0.01 ETH
      - Emits: AgreementRequested(agreementId=7391284650, consumer, provider, ...)
  ↓ Transaction confirmed in block #N
```

### Stage 6: Provider Detects the Event

```
Provider Agent (background task in provider/app.py)
  ↓ Running every 2 seconds:
      new_events = escrow.events.AgreementRequested.get_logs(
        from_block=last_checked_block
      )
  ↓ Finds: AgreementRequested event for agreementId=7391284650
  ↓ Calls _handle_agreement(agreementId=7391284650)
  
  ↓ Looks up the quote: pending_quotes[7391284650]
      → package=small, consumer=0x3C44..., priceWei=10000000000000000
  
  ↓ Mints NFT on-chain:
      nft.functions.mint(
        to="0x70997970...",         ← provider receives the NFT first
        agreementId=7391284650,
        bandwidthMbps=50,
        durationSeconds=600,
        endpoint="grpc://localhost:8003"
      )
  ↓ NFT created with tokenId=3 (fourth NFT ever minted)
  
  ↓ Approves the escrow to move the NFT:
      nft.functions.approve(escrow_address, tokenId=3)
  
  ↓ Calls deposit:
      escrow.functions.deposit(agreementId=7391284650, tokenId=3)
  
  Blockchain executes deposit():
      1. Transfers NFT from provider → escrow
      2. Transfers NFT from escrow → consumer
      3. Sends 0.01 ETH from escrow → provider
      4. Sets agreement.status = ACTIVE
      5. Emits: AgreementActive(agreementId, tokenId)
```

### Stage 7: Consumer Verifies

```
Consumer Agent
  ↓ The LLM thinks: "I should check if the agreement is now active."
  ↓ Calls check_agreement_status(agreementId=7391284650)
  
  ↓ Reads on-chain:
      agreement = escrow.functions.getAgreement(7391284650).call()
      → status = ACTIVE, tokenId = 3
  
  ↓ Signs a nonce for the Gateway:
      nonce = str(current_unix_time)      ← e.g., "1745800000"
      signature = sign(nonce, CONSUMER_PRIVATE_KEY)
  
  ↓ Calls Gateway:
      GET http://localhost:8003/service?tokenId=3
      Headers:
        X-Nonce: "1745800000"
        X-Signature: "0x5f4a..."
  
Gateway (provider/gateway.py)
  ↓ Checks: nonce is within last 5 minutes ✓
  ↓ Recovers signer from signature: "0x3C44..." ✓
  ↓ Checks: NFT owner on-chain is "0x3C44..." ✓
  ↓ Reads NFT metadata from blockchain
  ↓ Returns: {
      "tokenId": 3,
      "bandwidthMbps": 50,
      "durationSeconds": 600,
      "secondsRemaining": 598,
      "endpoint": "grpc://localhost:8003",
      "status": "ACTIVE"
    }
```

### Stage 8: Response Back to the Browser

```
Consumer Agent
  ↓ The LLM composes a human-readable summary
  ↓ Returns to Streamlit: 
      "Agreement settled. tokenId=3, 50 Mbps, 598 seconds remaining,
       endpoint=grpc://localhost:8003. Payment: 0.01 ETH."

Streamlit (consumer/ui.py)
  ↓ Receives the response
  ↓ Parses the inter-agent log (every tool call and result)
  ↓ Renders a timeline:
      ✓ Catalog   ✓ Quote   ✓ On-chain TX   ✓ Gateway
      
      [Catalog] get_catalog → 3 tiers available
      [Quote] request_quote(small) → 0.01 ETH, agreementId=7391284650
      [Blockchain] requestAgreement() → TX confirmed
      [Gateway] Service ACTIVE, 598s remaining
  
  ↓ You see the result in your browser.
```

---

## 7. How to Run and Use the Project

### What You Need to Install First

Before you start, your computer needs the following programs. Each link goes to the official installation page.

1. **Docker Desktop** — The system that runs the isolated mini-computers. Download from [docker.com](https://www.docker.com/products/docker-desktop/).

2. **Git** — The tool for downloading the project code. Download from [git-scm.com](https://git-scm.com/).

3. **Ollama** — The tool for running the AI model locally. Download from [ollama.com](https://ollama.com/).

4. **Foundry** — The Ethereum development toolkit. Install by opening your terminal and running:
   ```
   curl -L https://foundry.paradigm.xyz | bash
   foundryup
   ```

5. **uv** — The Python package manager. Install by running:
   ```
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

### Step-by-Step Setup

**Step 1: Download the project**

Open your terminal (on Mac, press Command+Space and type "Terminal"; on Windows, press the Windows key and type "PowerShell"). Type:

```bash
git clone https://github.com/Musel25/ollama-agent-simulation.git
cd ollama-agent-simulation
```

This downloads all the project files and puts you inside the project folder.

---

**Step 2: Download the AI model**

Before the project can run, you need to download the AI brain. Run:

```bash
ollama pull qwen3:1.7b
```

This downloads a small but capable language model (about 1 GB). It will run entirely on your computer.

---

**Step 3: Copy the settings file**

The project needs a settings file with configuration values. Run:

```bash
cp .env.example .env
```

This copies the example template to a real file called `.env`. The example values work fine for local testing — you do not need to change them.

---

**Step 4: Install Python dependencies**

```bash
uv sync
```

This reads `pyproject.toml` and installs all the Python libraries the project needs. This only needs to be done once.

---

**Step 5: Start everything with Docker**

```bash
make up
```

This single command:
1. Starts Anvil (the fake blockchain)
2. Compiles and deploys the smart contracts
3. Starts the Provider Agent
4. Starts the Gateway
5. Starts the Consumer Agent
6. Starts the browser UI

Wait about 30–60 seconds for all services to start. You will see a lot of logs scrolling by — that is normal.

---

**Step 6: Open the browser interface**

Open your web browser (Chrome, Firefox, etc.) and go to:

```
http://localhost:8501
```

You should see a chat interface.

---

**Step 7: Try your first request**

In the chat box, type something like:

- *"I need 100 Mbps for 10 minutes"*
- *"Buy me the cheapest bandwidth package"*
- *"What bandwidth options do you have?"*
- *"Get me the fastest available service"*

Press Enter or click Send. Watch the timeline update as the agents negotiate and settle the deal. The full process takes 30–60 seconds.

---

**Step 8: Stop everything when you are done**

```bash
make down
```

This stops all the services cleanly.

---

### Running Tests (Optional)

If you want to verify everything is working correctly:

```bash
uv run pytest tests/
```

You should see all tests pass.

---

### Running Without Docker (Advanced)

If you prefer not to use Docker, you need six separate terminal windows, running these commands in order:

**Terminal 1 — Blockchain:**
```bash
anvil --block-time 1
```

**Terminal 2 — Deploy contracts (run once, then close):**
```bash
source .env
cd contracts
forge script script/Deploy.s.sol \
  --rpc-url http://localhost:8545 \
  --broadcast \
  --private-key $DEPLOYER_PRIVATE_KEY
```

**Terminal 3 — Provider Agent:**
```bash
source .env
uv run uvicorn provider.app:app --port 8002 --reload
```

**Terminal 4 — Gateway:**
```bash
source .env
uv run uvicorn provider.gateway:app --port 8003 --reload
```

**Terminal 5 — Consumer Agent:**
```bash
source .env
uv run uvicorn consumer.app:app --port 8001 --reload
```

**Terminal 6 — Browser UI:**
```bash
source .env
uv run streamlit run consumer/ui.py
```

---

## 8. What Can Go Wrong

### "Model not found" or "Error loading model"

**What it means:** Ollama does not have the AI model downloaded yet.

**How to fix:**
```bash
ollama pull qwen3:1.7b
```
Wait for the download to finish, then try again.

---

### "Connection refused" on port 8001, 8002, or 8003

**What it means:** One of the agents is not running yet, or crashed during startup.

**How to fix:**
1. Run `docker compose logs consumer` (or `provider` or `gateway`) to see error messages.
2. Wait a bit longer — services can take up to 60 seconds to start.
3. Try `make down` then `make up` to restart everything.

---

### "Contract not deployed" or "Contract address is None"

**What it means:** The smart contracts were not deployed to the blockchain, so their addresses are not in `deployments/local.json`.

**How to fix:**
1. Make sure Anvil is running first.
2. Run the deploy script again:
   ```bash
   cd contracts
   forge script script/Deploy.s.sol \
     --rpc-url http://localhost:8545 \
     --broadcast \
     --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
   ```
3. Verify `deployments/local.json` now has two addresses.

---

### The chat sends the message but nothing comes back / it times out

**What it means:** The LLM is either slow, stuck, or chose the wrong tool sequence.

**How to fix:**
1. Try a smaller model: open `.env` and change `OLLAMA_MODEL=qwen3:1.7b` to `OLLAMA_MODEL=qwen3:1.7b` (already small).
2. Make sure your computer is not running too many other programs.
3. Try rephrasing: instead of vague requests, be specific: *"Buy a small bandwidth package."*

---

### "Transaction reverted" on the blockchain

**What it means:** The smart contract rejected the transaction because a rule was violated. Common causes:
- Trying to use an agreement ID that already exists
- Sending the wrong amount of ETH
- The agreement deadline has passed

**How to fix:**
1. Restart everything with `make down && make up` to reset the blockchain to a clean state.
2. Check the logs: `docker compose logs consumer`

---

### "Nonce too old" from the Gateway

**What it means:** The Consumer Agent's signed timestamp is more than 5 minutes old. This happens if the LLM took too long to reason.

**How to fix:** This should not happen in normal use. If it does, try again — the consumer will generate a fresh nonce each time.

---

### Inventory shows 0 available slots

**What it means:** All slots for a tier are in use (10 active small agreements, for example).

**How to fix:**
1. Wait for active agreements to expire (they last 600 seconds = 10 minutes).
2. Or restart the system to reset the inventory file.
3. Or ask for a different tier: *"Buy me a large bandwidth package instead."*

---

### `.env` file not found

**What it means:** You forgot to copy the example file.

**How to fix:**
```bash
cp .env.example .env
```

---

### "forge: command not found"

**What it means:** Foundry is not installed or not on your PATH (the list of places your terminal looks for programs).

**How to fix:**
```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```
Then close and reopen your terminal.

---

### "uv: command not found"

**What it means:** uv (the Python package manager) is not installed.

**How to fix:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Then close and reopen your terminal.

---

## 9. Glossary

Every technical term used in this document, defined in one plain-English sentence.

**Agent** — A computer program that acts on your behalf, making decisions and taking actions without you manually controlling each step.

**ABI (Application Binary Interface)** — A description file that tells Python what functions a smart contract has and how to call them.

**Anvil** — A fake Ethereum blockchain that runs on your computer, used for testing with no real money.

**API (Application Programming Interface)** — A set of rules for how two programs communicate with each other, like a menu defining what you can order.

**Atomic Swap** — An exchange of two assets that either fully succeeds or fully fails — there is no in-between state.

**Authentication** — The process of proving who you are, typically by showing a signature or password.

**Bandwidth** — How much data per second can flow through an internet connection, measured in Mbps (megabits per second).

**Blockchain** — A shared, permanent, tamper-proof record book that thousands of computers maintain together.

**Container** — An isolated mini-computer running inside your real computer, used to ensure software runs the same everywhere.

**Contract (Smart Contract)** — A program on a blockchain that runs automatically, holds assets, and cannot be modified after deployment.

**Dependency** — A library that your project relies on, installed from an external source.

**Deploy** — To publish a smart contract to the blockchain so it can be used.

**Docker** — A tool that creates and manages isolated containers for running software.

**Docker Compose** — A tool that starts multiple Docker containers at once using a configuration file.

**Endpoint** — The address at which a service is reachable, usually a URL plus a port number.

**Escrow** — A neutral holding place for money or assets while a transaction is being verified.

**ETH (Ether)** — The digital currency of the Ethereum blockchain.

**Event** — A public announcement emitted by a smart contract when something significant happens.

**Event Listener** — A program that watches for events and reacts when it sees one.

**FastAPI** — A Python library for building web servers that respond to HTTP requests.

**Foundry** — A toolkit for developing and deploying Ethereum smart contracts.

**Framework** — A pre-built set of tools and conventions that makes building a certain type of software easier.

**Git** — A tool for tracking changes to code and collaborating with others.

**HTTP** — The standard protocol (communication language) used to transfer data on the web.

**Library** — A package of pre-written code that you can import and use in your own programs.

**LLM (Large Language Model)** — An AI program trained on vast text data that can understand and generate human language.

**Makefile** — A file of shortcuts that lets you run complex commands with simple names like `make up`.

**MCP (Model Context Protocol)** — A standard for how AI agents discover and call tools on remote servers.

**Mbps** — Megabits per second — a unit measuring internet connection speed.

**NFT (Non-Fungible Token)** — A unique, one-of-a-kind digital certificate stored on the blockchain.

**Nonce** — A number used only once, typically for security purposes to prevent reuse of old messages.

**Ollama** — A tool for running AI language models locally on your own computer.

**Port** — A number (like an apartment number) that identifies a specific service running on a computer.

**Private Key** — A secret code that proves ownership of a blockchain account and allows you to sign transactions.

**Protocol** — A standardized set of rules for how two systems communicate.

**Replay Attack** — A security attack where someone records a valid message and sends it again later to trick a system.

**REST API** — A common style of web API where different web addresses correspond to different actions.

**Signature** — A mathematical proof created with a private key that proves a message came from a specific account.

**Slot** — One available unit of a bandwidth tier (e.g., there are 10 small slots, meaning 10 simultaneous small agreements can be active).

**Solidity** — The programming language used to write smart contracts on Ethereum.

**State Machine** — A system that can only be in one defined state at a time and transitions between states by following strict rules.

**Streamlit** — A Python library that lets you create browser-based visual interfaces with minimal code.

**Terminal** — A text-based interface for typing commands directly to your computer's operating system.

**Transaction** — An action sent to the blockchain, like sending ETH or calling a smart contract function.

**uv** — A fast, modern Python package manager that installs and manages dependencies.

**Uvicorn** — The engine that runs a FastAPI web server.

**Wei** — The smallest unit of ETH (1 ETH = 1,000,000,000,000,000,000 Wei).

**Web3.py** — A Python library for interacting with the Ethereum blockchain.

---

*This document was written to accompany the `ollama-agent-simulation` project. It covers the codebase as of the `feat/mcp-a2a` branch.*
