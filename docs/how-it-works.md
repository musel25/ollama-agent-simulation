# How It Works — Beginner's Guide

This system lets an AI agent buy network bandwidth from a provider using a blockchain.
No middleman, no trust required — the rules are enforced by code running on Ethereum.

---

## What is an NFT?

NFT stands for **Non-Fungible Token**.

- A regular token (like ETH or a dollar) is **fungible** — one dollar is the same as any other dollar.
- An NFT is **non-fungible** — each one is unique and has its own ID and data attached to it.

In this system, an NFT represents **one bandwidth lease** — the right to use a certain amount of network bandwidth for a specific duration. It lives on the blockchain, has a unique ID (0, 1, 2, ...), and can only be owned by one wallet at a time.

The NFT contains this data, stored permanently on-chain:

| Field              | Example                  | Meaning                              |
|--------------------|--------------------------|--------------------------------------|
| `agreementId`      | `18392847...` (big int)  | Links this NFT to the purchase deal  |
| `bandwidthMbps`    | `100`                    | How many megabits per second         |
| `durationSeconds`  | `600`                    | How long the lease lasts (10 min)    |
| `startTime`        | `1713612000`             | Unix timestamp when it was minted    |
| `endpoint`         | `grpc://provider:8003`   | Where to connect to use the service  |

---

## The Two Smart Contracts

A **smart contract** is a program that lives on the blockchain. Once deployed, nobody can change it — not even the person who wrote it. It runs exactly as coded.

### `BandwidthNFT` — the certificate of ownership

This contract mints (creates) NFTs. Each NFT is a signed certificate that says:

> "Whoever owns token #3 has the right to 100 Mbps for 600 seconds, starting at time X."

Only the provider can mint NFTs (enforced by `onlyOwner`).

### `BandwidthEscrow` — the deal enforcer

This contract holds ETH and ensures a fair trade:
- The consumer locks their ETH here **before** receiving anything.
- The provider delivers the NFT and, **in the same transaction**, receives the ETH.

There is no moment where one party has both assets and the other has nothing. The swap is **atomic** — it either fully completes or fully reverts.

The contract tracks each deal (called an **Agreement**) through states:

```
NONE → REQUESTED → ACTIVE → (CLOSED in future)
                ↘ CANCELLED
```

---

## The Full Workflow, Step by Step

### Step 1 — Consumer queries the catalog

The consumer agent calls the provider's HTTP API to see what packages are available:

```
GET /catalog

Response:
  small:  50 Mbps / 600s / 0.01 ETH  (3 slots)
  medium: 100 Mbps / 600s / 0.02 ETH (2 slots)
  large:  500 Mbps / 600s / 0.08 ETH (1 slot)
```

Nothing happens on-chain yet. This is just browsing.

---

### Step 2 — Consumer requests a quote

The consumer picks a package and asks the provider for a **quote**. The provider generates a unique `agreementId` (a random 128-bit number) and sends it back along with the exact price.

```
POST /quote  { packageId: "medium", consumerAddress: "0xABC..." }

Response:
  agreementId:      18392847563910284756...  (huge random number)
  priceWei:         20000000000000000        (0.02 ETH in wei)
  bandwidthMbps:    100
  durationSeconds:  600
```

The `agreementId` is random so it can't be guessed or collided with another deal.

---

### Step 3 — Consumer locks ETH on-chain

The consumer agent calls `requestAgreement()` on the `BandwidthEscrow` contract, sending ETH along with it:

```
escrow.requestAgreement(
  agreementId,      // the random ID from the quote
  providerAddress,  // who the deal is with
  bandwidthMbps,    // what was agreed
  durationSeconds,  // what was agreed
  value = 0.02 ETH  // locked inside the contract
)
```

The ETH is now **locked inside the smart contract**. The consumer cannot spend it. The provider cannot take it. It is frozen until the deal completes or is cancelled.

The agreement is now in state: **REQUESTED**.

---

### Step 4 — Provider detects the event and mints an NFT

The provider's backend is constantly watching the blockchain for `AgreementRequested` events. When it sees one:

1. It verifies the on-chain parameters match the quote it issued.
2. It reserves a slot in its inventory so no other consumer can take it.
3. It calls `nft.mint(...)` — this creates a new NFT owned by the provider, embedding all the service metadata including the `endpoint`.
4. It approves the escrow contract to move the NFT on its behalf.

At this point the provider owns the NFT but the ETH is still locked. Neither side has been paid yet.

---

### Step 5 — Atomic swap inside `deposit()`

The provider calls `escrow.deposit(agreementId, tokenId)`. Inside this single transaction:

```
1. Verify the NFT metadata matches the agreement
2. Mark agreement status = ACTIVE
3. Transfer NFT: provider → escrow → consumer   (two hops in one tx)
4. Transfer ETH: escrow → provider
```

Steps 3 and 4 happen atomically. If any step fails, the entire transaction reverts and nothing moves. This is the core guarantee — **you can't take the money without delivering the NFT, and you can't keep the NFT without receiving the money**.

After this, the agreement is **ACTIVE**. The consumer's wallet now holds the NFT.

---

### Step 6 — Consumer checks status and accesses the service

The consumer calls `check_agreement_status(agreementId)`, which:

1. Reads the on-chain agreement — if ACTIVE, extracts the `tokenId`.
2. Signs a timestamp nonce with its private key (`X-Signature` header).
3. Calls the gateway: `GET /service?tokenId=3` with the signature.

The gateway then:

1. Recovers the caller's Ethereum address from the signature.
2. Calls `nft.ownerOf(tokenId)` on-chain — gets the NFT's owner address.
3. Rejects the request if `signer != owner`.
4. If they match, reads the NFT metadata and returns the service info.

```json
{
  "token_id": 3,
  "bandwidth_mbps": 100,
  "seconds_remaining": 587,
  "endpoint": "grpc://provider:8003",
  "status": "ACTIVE"
}
```

---

## Why the tokenId Being Sequential (0, 1, 2...) Is Fine

You might wonder: if anyone can guess `tokenId=0`, can they access the service?

No. Knowing the tokenId gets you nothing because:

- The gateway recovers your **Ethereum address** from your signature.
- It checks that address against the **on-chain NFT owner**.
- These must match — you must hold the private key of the wallet that owns the token.

The tokenId is public (everything on a blockchain is public). The credential is your **private key**. This is the same model as a physical key and a door — knowing the door number (apartment #3) doesn't open it.

---

## Diagram

```
Consumer Agent                   Provider Agent              Blockchain (Anvil)
──────────────                   ──────────────              ──────────────────

GET /catalog ──────────────────>
             <─────────────────  tiers + prices

POST /quote ───────────────────>
            <──────────────────  { agreementId, priceWei }

requestAgreement() + ETH ───────────────────────────────>  ETH locked in escrow
                                                            status = REQUESTED

                                event listener sees ──────> AgreementRequested
                                mint NFT ────────────────>  NFT minted (tokenId=N)
                                approve escrow ──────────>
                                deposit() ───────────────>  NFT → consumer
                                                            ETH → provider
                                                            status = ACTIVE

check_agreement_status() ───────────────────────────────>  reads tokenId from chain
sign nonce ──────────────────────────────────────────────>
GET /service?tokenId=N ────────> verify ownerOf(N)==signer
                <──────────────  { bandwidth_mbps, endpoint, seconds_remaining }
```

---

## Cancellation

If the provider never responds (or takes more than 1 hour), the consumer can call `cancel(agreementId)` and get their ETH fully refunded. This protects the consumer from a dishonest or offline provider.

Anyone can trigger the cancel after the deadline passes — this prevents the ETH from being permanently locked if both parties disappear.
