# Running the Project

> **Audience:** you want to run the demo on your machine. This doc takes you from a
> clean laptop to seeing the consumer agent buy bandwidth.

---

## Prerequisites

You need four tools installed before starting anything. All four are required
for both the Docker path and the bare-metal path.

### Foundry

Foundry provides `anvil` (the local Ethereum chain) and `forge` (the contract
compiler and deployer). Install it with the official installer:

```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

Verify:

```bash
forge --version   # e.g. forge 0.2.0 (...)
anvil --version   # e.g. anvil 0.2.0 (...)
```

Both commands must succeed before continuing. If `foundryup` says it cannot
find the binaries, open a new shell — the installer modifies `~/.bashrc` /
`~/.zshrc` but the change only takes effect in a fresh session.

### Docker and Docker Compose

Install Docker Desktop (Mac / Windows) or Docker Engine plus the Compose
plugin (Linux) from <https://docs.docker.com/get-docker/>.

Verify that you have Compose **v2** — the `docker compose` subcommand, not the
older `docker-compose` standalone binary:

```bash
docker compose version   # must report v2.x
```

If the command is not found or reports v1, follow the Docker docs to install
the Compose plugin.

### Ollama

Ollama runs the LLM locally. Install it from <https://ollama.com/> following
the instructions for your OS.

Verify:

```bash
ollama --version
```

**Docker mode:** the `ollama-pull` container pulls `$OLLAMA_MODEL` (default
`llama3.2:3b`) automatically on first `make up`. Only that one model is
pulled; if you want a different model, either change `OLLAMA_MODEL` in `.env`
or pull it manually: `docker compose exec ollama ollama pull <name>`.

**Bare-metal mode:** you must pull the model yourself before starting the
agents:

```bash
ollama pull llama3.2:3b
```

The `llama3.2:3b` download is roughly 2.0 GB. The consumer's LangGraph nodes
use plain text completion (no tool-calling required), so any small chat model
works — set `OLLAMA_MODEL` accordingly.

### uv

`uv` is the Python package manager used by both agents. Install it with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify:

```bash
uv --version
```

`uv` is only required for the bare-metal path. Docker builds the virtualenv
inside the image.

---

## Configuring

### The `.env` file

The project ships an `.env.example` that contains working defaults for a local
Anvil chain. Copy it before running anything:

```bash
cp .env.example .env
```

Docker Compose and the bare-metal commands all `source .env` (or read it via
Docker's `env_file` / `environment` keys). Never rename or delete this file
once it exists.

### Variables that must be set

The following variables hold Ethereum private keys and addresses. For a local
Anvil session the `.env.example` defaults are Anvil's well-known prefunded
accounts (`mnemonic: "test test … junk"`), so you can leave them unchanged.

If you switch to a different chain or a custom mnemonic, you must update all
of them:

| Variable | Role |
|---|---|
| `DEPLOYER_PRIVATE_KEY` | Signs the `forge script` deployment transaction |
| `DEPLOYER_ADDRESS` | Ethereum address derived from `DEPLOYER_PRIVATE_KEY` |
| `PROVIDER_PRIVATE_KEY` | Signs provider-side on-chain calls (NFT mint, deposit) |
| `PROVIDER_ADDRESS` | Ethereum address derived from `PROVIDER_PRIVATE_KEY` (used in the escrow contract) |
| `CONSUMER_PRIVATE_KEY` | Signs consumer-side on-chain calls (requestAgreement) |
| `CONSUMER_ADDRESS` | Ethereum address derived from `CONSUMER_PRIVATE_KEY` |

Each `*_PRIVATE_KEY` has a corresponding `*_ADDRESS` that **must stay in
sync**. The `.env.example` defaults already pair them correctly for the
standard Anvil prefunded accounts, so no action is needed unless you replace
the keys.

Do not commit a `.env` that contains real private keys.

### Variables with sensible defaults

These variables have defaults that work out of the box with the Docker Compose
setup. You only need to change them if you are running outside Docker or
pointing at a different host.

| Variable | Default (Docker) | Notes |
|---|---|---|
| `RPC_URL` | `http://anvil:8545` | Use `http://localhost:8545` for bare-metal |
| `OLLAMA_MODEL` | `llama3.2:3b` | Any tool-calling model works; see [Changing the AI model](#changing-the-ai-model) |
| `SDN_MOCK` | `true` | Set to `false` only for the real SDN path |
| `OLLAMA_HOST` | `http://ollama:11434` | Use `http://localhost:11434` for bare-metal |
| `PROVIDER_BASE_URL` | `http://provider-agent:8002` | Consumer uses this to reach the provider |
| `PROVIDER_A2A_URLS` | `http://provider-agent:8002` | A2A discovery URL list (comma-separated) |

The `.env.example` uses `http://localhost:*` values. The Docker Compose
`environment:` blocks override these with container-network hostnames at
runtime, so the file values only matter for bare-metal.

> **Note:** `OLLAMA_HOST` is injected automatically by `docker-compose.yml`
> and does **not** need to be set in `.env` for Docker-based runs. For
> bare-metal (terminal mode), set it manually if your host or port differs
> from the defaults above.

---

## Running with Docker (recommended)

### `make up`

```bash
make up
```

This runs `docker compose up --build -d`, which builds all images and starts
the seven default-profile services in the background. On first run Docker must
build the images and the `ollama-pull` container must download the model —
allow three to five minutes.

To stream all service logs while it starts:

```bash
make logs
# or, to tail a specific service:
docker compose logs -f consumer-agent
```

The UI is served at **http://localhost:8501** once all services are healthy.

### What you should see

The services come up in dependency order:

1. **anvil** starts and becomes healthy (block-number RPC call succeeds).
2. **deployer** runs `forge script`, deploys `BandwidthNFT` and
   `BandwidthEscrow`, writes `contracts/deployments/local.json`, then exits 0.
3. **ollama** starts. **ollama-pull** pulls `$OLLAMA_MODEL` and exits 0.
4. **provider-agent** starts (waits for deployer to exit 0).
5. **consumer-agent** starts (waits for provider-agent and the pull job).
6. **consumer-ui** starts (waits for consumer-agent).

Check the current state at any time:

```bash
docker compose ps
```

All services except `deployer` and `ollama-pull` should show `running`.
Those two are one-shot and show `exited (0)` when successful.

### Stopping and cleaning up

```bash
# Stop containers but keep the ollama model volume (fastest restart next time)
make down

# Stop containers AND delete the ollama model volume (forces a fresh model pull)
make down-clean
```

Use `make down` for normal day-to-day stopping. Use `make down-clean` if you
want to reset completely or if the ollama volume is corrupted.

---

## Running locally without Docker

Use this path when you are actively developing and need faster iteration
cycles. You need five terminals open simultaneously.

### Five-terminal flow

Each terminal runs one long-lived process. Start them in order — later
terminals depend on earlier ones being ready.

### Terminal 1 — Anvil

```bash
anvil --block-time 1
```

Starts the local Ethereum chain on `localhost:8545` with one-second block
times. Anvil pre-funds the first ten accounts derived from the default
mnemonic — the `.env.example` keys map to accounts[0]–accounts[3].

Leave this running for the entire session.

### Terminal 2 — Deploy contracts

```bash
source .env
cd contracts && forge script script/Deploy.s.sol \
  --rpc-url http://localhost:8545 \
  --broadcast \
  --private-key $DEPLOYER_PRIVATE_KEY
```

Compiles and deploys `BandwidthNFT` and `BandwidthEscrow` to the local chain.
On success, Foundry writes `contracts/deployments/local.json` with the
deployed contract addresses. Both agents read this file at startup.

This terminal exits after deployment. If you restart Anvil you must re-run
this step.

### Terminal 3 — Provider agent

```bash
source .env && uv run uvicorn provider.app:app --port 8002
```

Starts the provider FastAPI app on `:8002`. It mounts a FastMCP server at
`/mcp`, an A2A JSON-RPC endpoint at `/a2a`, and serves the agent card at
`/.well-known/agent-card.json`. It also starts a background listener for
`AgreementRequested` events on the smart contract.

### Terminal 4 — Consumer agent

```bash
source .env && uv run uvicorn consumer.app:app --port 8001
```

Starts the consumer FastAPI app on `:8001`. The LLM (via Ollama) runs here.
The consumer exposes `/chat` for the UI and its own agent card at
`/.well-known/agent-card.json`.

Make sure Ollama is running and the model is already pulled before starting
this terminal.

### Terminal 5 — Streamlit UI

```bash
source .env && uv run streamlit run consumer/ui.py
```

Starts the Streamlit chat interface on `:8501`. Open
**http://localhost:8501** in your browser.

---

## Verifying it works

### `make demo`

The scripted demo runs a full purchase flow without touching the browser:

```bash
make demo
```

It first checks that both agents are reachable, then executes three steps:

1. **Catalog fetch** — `GET http://localhost:8001/catalog_proxy` — retrieves
   the provider's tier list through the consumer's MCP proxy.
2. **Chat request** — `POST http://localhost:8001/chat` with the message
   `"I need 5 Mbps for 10 minutes"` — triggers the full LLM → MCP → A2A →
   on-chain flow. This step takes 30–60 seconds.
3. **Inventory check** — `GET http://localhost:8002/inventory` — reads the
   provider's slot table to confirm the purchase was recorded.

### Reading the demo output

After `make demo` completes you should see three JSON blocks:

**(1) Catalog** — a list of tier objects, for example:

```json
[
  {"tier": "small",  "mbps": 2, "price_eth": "0.001", "slots": 3},
  {"tier": "medium", "mbps": 5, "price_eth": "0.002", "slots": 3},
  {"tier": "large",  "mbps": 8, "price_eth": "0.004", "slots": 3}
]
```

**(2) Chat response** — the consumer agent's reply with the purchase
result embedded:

```json
{
  "response": "I have secured a medium bandwidth package ...",
  "agreementId": "0x...",
  "tokenId": "1",
  "mbps": 5,
  "endpoint": "192.168.3.10:5000"
}
```

The `agreementId` is the on-chain escrow ID. The `tokenId` is the NFT minted
by the provider. Both fields being present confirms the atomic swap succeeded.

**(3) Inventory** — the provider's slot table after the purchase. One slot
in the `medium` tier should now show a taken entry with an expiry timestamp,
confirming the slot is leased.

---

## Real SDN mode (`make demo-real`)

By default, `SDN_MOCK=true` and `allocate_bandwidth` returns success without
touching any network device. To run against a real ContainerLab topology with
Nokia SR Linux nodes and Linux `tc` rate-shaping:

**Step 1 — Prerequisites.** You need the
[`srl-gnmi-bandwidth-poc`](https://github.com/Musel25/srl-gnmi-bandwidth-poc)
repository cloned as a sibling of this repo:

```
../srl-gnmi-bandwidth-poc/
```

**Step 2 — Deploy ContainerLab** (one-time per session; may require `sudo` — ContainerLab usually does):

```bash
make clab-up
```

This runs `scripts/deploy.sh` and `scripts/push-config.sh` from the sibling
repo and then waits 60 seconds for SR Linux to boot. The topology is a
7-node fabric:

| Tier   | Mbps | PE  | Subinterface   | CE  |
|--------|------|-----|----------------|-----|
| small  | 2    | pe1 | ethernet-1/2.0 | ce1 |
| medium | 5    | pe1 | ethernet-1/3.0 | ce3 |
| large  | 8    | pe2 | ethernet-1/2.0 | ce2 |

**Step 3 — Run the demo with real enforcement:**

```bash
make demo-real
```

This stops the running `provider-agent` container, restarts it with
`SDN_MOCK=false`, waits five seconds, and then runs the normal `make demo`
flow. After the demo completes it runs an `iperf3` verification:

```bash
# Expected output: Sender Mbps: ~5.0 (for a medium tier purchase)
```

The iperf3 test fires a 5-second UDP stream at 15 Mbps from `ce3` to `ce4`
and reads the received throughput. The `tc` shaper on `pe1 ethernet-1/3.0`
should cap it to roughly 5.0 Mbps.

**Step 4 — Tear down:**

```bash
make clab-down   # destroys the ContainerLab topology
make down        # stops the Docker Compose services
```

---

## Changing the AI model

The default model is `llama3.2:3b`. The `ollama-pull` one-shot service auto-pulls
whatever `$OLLAMA_MODEL` is set to. To use a different one, set `OLLAMA_MODEL`
before starting the stack:

```bash
OLLAMA_MODEL=llama3.2:1b make up
# or set it permanently in .env
```

To pull additional models without changing the default (e.g. for ad-hoc testing),
pull them manually against the running ollama container:

```bash
docker compose exec ollama ollama pull <model-name>
```

**Models tested with this project:**

| Model | Size | Notes |
|---|---|---|
| `llama3.2:3b` | ~2.0 GB | Default. Best tier-selection accuracy. |
| `llama3.2:1b` | ~1.3 GB | Faster. Occasionally picks the wrong tier on ambiguous requests. |

The consumer's LangGraph nodes use plain text completion (no tool-calling
required), so any small chat model works.

---

## Troubleshooting

### Provider unreachable on `:8002`

**Symptom.** `make demo` prints `ERROR: provider agent not running on :8002`
or `curl` to `http://localhost:8002/address` returns `Connection refused`.

**Cause.** The provider container usually fails to start for one of two
reasons: (a) the deployer container has not finished yet and the provider
cannot read `contracts/deployments/local.json`, or (b) the deployer exited
with an error and no deployment file was written.

**Fix.**
1. Check the deployer logs: `docker compose logs deployer`.
2. If the deployer failed, check the provider logs: `docker compose logs provider-agent`.
3. If the deployment file is missing or empty, run `make down-clean && make up`
   to restart from scratch.

---

### Deployer hangs / contract deploy fails

**Symptom.** `docker compose logs deployer` shows `forge script` hanging
indefinitely or printing a revert / connection error.

**Cause.** Anvil was not yet healthy when the deployer started (a race
condition on slow machines), or `DEPLOYER_PRIVATE_KEY` in `.env` is wrong and
Foundry cannot sign the transaction.

**Fix.**
1. Verify that `DEPLOYER_PRIVATE_KEY` in `.env` matches the value in
   `.env.example` (or the key you intend to use).
2. Run `make down-clean && make up`. The deployer has a `depends_on:
   condition: service_healthy` on anvil, so a clean restart usually resolves
   the race.
3. If it still fails, run `docker compose logs anvil` to confirm the chain is
   reachable.

---

### `ollama pull` fails or times out

**Symptom.** `docker compose logs ollama-pull` shows a network error, a
timeout, or a "429 Too Many Requests" from the Ollama model hub.

**Cause.** Slow network connectivity or a temporary rate limit from the Ollama
registry.

**Fix.**
1. Wait a few minutes and run `make up` again. The pull jobs are idempotent —
   if the model is already cached in the `ollama` volume they exit immediately.
2. If you are behind a proxy, configure Docker's proxy settings in
   `~/.docker/config.json`.

---

### Anvil port `:8545` already in use

**Symptom.** `docker compose up` fails with `Error starting userland proxy:
listen tcp 0.0.0.0:8545: bind: address already in use`.

**Cause.** Another `anvil` process (or any other service) is already listening
on port 8545 on the host.

**Fix.**
1. Find and stop the conflicting process:
   ```bash
   lsof -ti tcp:8545 | xargs kill
   ```
2. Then re-run `make up`.
3. If you cannot stop the conflict, change the host port in
   `docker-compose.yml` (`ports: - "8546:8545"`) and update `RPC_URL` in
   `.env` to match.

---

### "Consumer agent not running on :8001"

**Symptom.** `make demo` exits immediately with
`ERROR: consumer agent not running on :8001`.

**Cause.** The consumer container is still waiting for the `ollama-pull`
job to complete, which can take several minutes on first run. The container
may also have crashed.

**Fix.**
1. Check whether the pull job has finished: `docker compose logs ollama-pull`.
2. If it is still running, wait and retry.
3. If the consumer container itself is the problem:
   `docker compose logs consumer-agent` will show the startup error.

---

### Wallet has zero ETH

**Symptom.** The consumer's `requestAgreement` transaction reverts with
`insufficient funds` or a similar error visible in `docker compose logs consumer-agent`.

**Cause.** Anvil automatically seeds 10 ETH into each of its prefunded
accounts. The `.env.example` keys map to accounts[0]–[3], all of which are
pre-funded. If you replaced any key with a non-Anvil key, that address has
zero ETH.

**Fix.**
1. Revert `CONSUMER_PRIVATE_KEY` in `.env` to the `.env.example` default.
2. Alternatively, fund your custom address via the Anvil console:
   ```bash
   cast send <your-address> --value 10ether \
     --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
     --rpc-url http://localhost:8545
   ```

---

### `make demo-real` reports wrong Mbps

**Symptom.** The `iperf3` verification at the end of `make demo-real` prints a
`Sender Mbps` value far from the expected 5.0 for a medium-tier purchase.

**Cause.** The ContainerLab containers may not be wired or configured
correctly. SR Linux needs a full boot (60 s) and the gNMI config push must
complete before the `tc` shapers are in place.

**Fix.**
1. Tear down and re-deploy the topology:
   ```bash
   make clab-down && make clab-up
   ```
2. Check the sibling repo's `scripts/push-config.sh` output for gNMI errors.
3. Re-run `make demo-real`.

---

### LLM picks the wrong tier

**Symptom.** You asked for "100 Mbps" but the agent bought the `small` (2
Mbps) tier, or the chat response contains a tier that does not match your
request.

**Cause.** Small models (`llama3.2:1b`) occasionally misread bandwidth numbers
or pick based on price rather than Mbps. This is a model capability issue, not
a bug in the agents.

**Fix.**
1. Switch to the larger model: set `OLLAMA_MODEL=llama3.2:3b` in `.env` and
   restart.
2. Rephrase the request to be more explicit, for example:
   `"I need the medium tier, 5 Mbps, for 10 minutes"`.
3. If the wrong tier is consistently selected regardless of model, open the
   provider logs to verify the catalog is returning the expected tiers:
   `docker compose logs provider-agent`.

---

## Notebook path (no Docker)

The `notebooks/` directory contains five Jupyter notebooks that exercise every layer in-process. No Docker, no `make`, no compose — just `anvil`, `forge`, and (for notebook 05) `ollama`.

### Prerequisites

- `anvil` + `forge` (install from [Foundry](https://book.getfoundry.sh/getting-started/installation))
- Python 3.13 + `uv`
- For notebook 05 only: `ollama serve` running with `llama3.2:3b` pulled (`ollama pull llama3.2:3b`)

### Run

```bash
uv sync
uv run jupyter lab notebooks/
```

Open the notebooks in order:

1. `01_chain.ipynb` — deploy the contracts, walk one trade.
2. `02_mcp.ipynb` — exercise the provider's MCP tools in-process.
3. `03_a2a.ipynb` — drive the provider's A2A executor without a port.
4. `04_consumer_graph.ipynb` — step through the consumer's LangGraph state machine.
5. `05_end_to_end.ipynb` — full negotiation, end-to-end (uses Ollama).

Each notebook is self-contained: it spins up everything it needs in a `try`, demonstrates the layer, and tears down in a `finally`.
