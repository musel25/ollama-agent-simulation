import marimo

__generated_with = "0.23.8"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 01a — Chain: contract model

    We study the two contracts before we deploy them.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## BandwidthEscrow

    The escrow contract holds two things during a trade: the consumer's ETH (locked) and (briefly) the provider's NFT. It coordinates the atomic swap.

    ### `Agreement` struct

    Each agreement is identified by an `agreementId` (chosen by the provider when issuing a quote). The struct fields:

    | Field | Type | Meaning |
    |---|---|---|
    | `consumer` | `address` | Who locked the ETH |
    | `provider` | `address` | Who must deposit the NFT to settle |
    | `bandwidthMbps` | `uint256` | Mbps the consumer paid for |
    | `durationSeconds` | `uint256` | Lease duration |
    | `priceWei` | `uint256` | Locked ETH amount (= `msg.value` at request) |
    | `requestDeadline` | `uint256` | `block.timestamp + 1 hours` — after this, anyone can cancel |
    | `tokenId` | `uint256` | Set on `deposit()` to bind the NFT to the agreement |
    | `status` | `Status` | The state machine cursor |

    ### `Status` enum (5 values)

    | Value | Meaning |
    |---|---|
    | `NONE` | Default; agreement does not exist |
    | `REQUESTED` | Consumer has locked ETH; awaiting provider deposit |
    | `ACTIVE` | Atomic swap fired inside `deposit()`; NFT now belongs to consumer, ETH to provider |
    | `CLOSED` | Reserved for future use (currently unreachable) |
    | `CANCELLED` | Consumer or anyone-after-deadline reclaimed the locked ETH |

    ### Custom errors

    `AgreementAlreadyExists`, `AgreementNotFound`, `NotProvider`, `NotConsumer`, `WrongStatus`, `DeadlineNotPassed`, `MetadataMismatch`, `ETHTransferFailed`, `ZeroPriceNotAllowed`. The custom-error pattern (Solidity 0.8.4+) is cheaper than `require(..., "string")` and gives callers structured failure info.

    ### Why `requestDeadline = block.timestamp + 1 hours`?

    So a consumer's locked ETH cannot be held forever by an unresponsive provider. After 1 hour, anyone (not just the consumer) can call `cancel()` to release the funds.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## BandwidthNFT

    ERC-721 token whose metadata IS the credential. **No `tokenURI`. No IPFS.** All metadata stored on-chain.

    ### `TokenMetadata` struct

    | Field | Type | Meaning |
    |---|---|---|
    | `agreementId` | `uint256` | Back-reference to the escrow agreement |
    | `bandwidthMbps` | `uint256` | Granted Mbps |
    | `durationSeconds` | `uint256` | Lease duration |
    | `startTime` | `uint256` | `block.timestamp` at mint |
    | `endpoint` | `string` | `clab://<pe>/<subinterface>` — the literal SDN endpoint |

    The provider EOA owns the contract (`Ownable(initialOwner)`); only the owner can `mint`. `getTokenMetadata` is public.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Why `ERC721Holder`?

    The escrow briefly holds the NFT during the atomic swap inside `deposit()`. `ERC721Holder` is OpenZeppelin's mixin that implements `onERC721Received`, signaling that the contract can safely receive ERC-721 tokens via `safeTransferFrom`. Without it, the swap would revert.
    """)
    return


@app.cell
def _():
    from IPython.display import Code, display
    display(Code(filename="contracts/src/BandwidthEscrow.sol", language="solidity"))
    return Code, display


@app.cell
def _(Code, display):
    display(Code(filename='contracts/src/BandwidthNFT.sol', language='solidity'))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Why ERC-721 for the credential?

    **Ownership transfer is credential transfer.** Selling, gifting, or revoking the credential is a single `transferFrom` call — no off-chain signature ceremony, no central authority.

    **On-chain enumerability.** Anyone can ask `ownerOf(tokenId)` or `getTokenMetadata(tokenId)`. The provider doesn't need a database of leases; the contract IS the database.

    **Off-chain verifiability via signed nonce.** The provider's `verify_credential_ownership` MCP tool checks: signer recovers from a fresh nonce, signer matches `ownerOf(tokenId)`, agreement is `ACTIVE`. No magic, no trusted intermediary.

    Next: [01b — escrow lifecycle](01b_chain_escrow_lifecycle.py).
    """)
    return


if __name__ == "__main__":
    app.run()
