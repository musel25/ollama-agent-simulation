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
    # NB09 — Toy EVM

    Build a stack-machine interpreter for ~25 EVM opcodes. Run hand-written
    bytecode. Disassemble a real compiled contract's bytecode at the end.

    **Exports:** `_lib/evm.py` — `EVM`, `OPCODES`, `disasm`, `MOD`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. What is the EVM?

    The **Ethereum Virtual Machine** is a **stack machine** — there are no
    registers. Every operation pops its inputs from the top of the stack and
    pushes its result back. The full spec has ~140 opcodes; we implement ~25.

    ### Three memory areas

    | Area | Size | Description |
    |------|------|-------------|
    | **Stack** | 1024 × 256-bit words | LIFO; all arithmetic happens here |
    | **Memory** | byte-addressable, expands on demand | zero-initialised; used for temporary data |
    | **Storage** | 256-bit key → 256-bit value | *persistent*; survives across transactions; this is how Solidity state variables work |

    ### Programs are bytecode

    A compiled contract is a flat byte sequence. Each byte is either an
    opcode (executed immediately) or push data that follows a `PUSH` opcode.
    The program counter (`pc`) starts at 0 and advances one byte at a time —
    or jumps when a `JUMP`/`JUMPI` instruction fires.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Opcode table (the 25 we implement)

    | Op | Hex | Stack effect |
    |----|-----|--------------|
    | STOP | 00 | halt |
    | ADD | 01 | a, b → a+b |
    | MUL | 02 | a, b → a\*b |
    | SUB | 03 | a, b → a-b |
    | DIV | 04 | a, b → a//b (0 if b=0) |
    | MOD | 06 | a, b → a%b |
    | LT | 10 | a, b → 1 if a<b else 0 |
    | GT | 11 | a, b → 1 if a>b else 0 |
    | EQ | 14 | a, b → 1 if a==b else 0 |
    | ISZERO | 15 | a → 1 if a==0 else 0 |
    | AND | 16 | a, b → a&b |
    | OR | 17 | a, b → a\|b |
    | NOT | 19 | a → ~a (256-bit) |
    | POP | 50 | a → (discard) |
    | MLOAD | 51 | offset → mem[off:off+32] |
    | MSTORE | 52 | offset, val → write 32 bytes |
    | SLOAD | 54 | key → storage[key] |
    | SSTORE | 55 | key, val → write storage |
    | JUMP | 56 | dest → pc=dest |
    | JUMPI | 57 | dest, cond → if cond: pc=dest |
    | PC | 58 | → current pc |
    | JUMPDEST | 5b | no-op marker (valid jump target) |
    | PUSH1..PUSH32 | 60..7f | push N bytes of inline data |
    | DUP1 | 80 | duplicate top of stack |
    | SWAP1 | 90 | swap top two items |
    | RETURN | f3 | offset, len → halt; return mem[off:off+len] |

    > **Pop order:** `a = pop(); b = pop()`, then compute `a OP b`. For binary
    > ops, `a` is the stack top (the *last* item pushed). This matches the
    > Ethereum Yellow Paper convention.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. Interpreter — `EVM` class

    Split into four code cells to keep each manageable. Cell A: skeleton and
    arithmetic opcodes.
    """)
    return


@app.cell
def _():
    MOD = 2 ** 256  # all values are 256-bit unsigned integers

    class EVM:

        def __init__(self, code: bytes):
            self.code = _code
            self.pc = 0
            self.stack: list[int] = []
            self.memory = bytearray()
            self.storage: dict[int, int] = {}
            self.stopped = False
            self.return_data = b''

        def _push(self, v: int) -> None:
            if len(self.stack) >= 1024:
                raise RuntimeError('stack overflow')
            self.stack.append(v % MOD)

        def _pop(self) -> int:
            if not self.stack:
                raise RuntimeError('stack underflow')
            return self.stack.pop()

        def _expand_mem(self, end: int) -> None:
            if end > len(self.memory):
                pad = (end + 31) // 32 * 32 - len(self.memory)  # round up to 32-byte boundary (like the real EVM)
                self.memory.extend(b'\x00' * pad)

        def step(self) -> None:
            op = self.code[self.pc]
            self.pc += 1
            if op == 0:
                self.stopped = True  # ---- arithmetic ----
            elif op == 1:  # STOP
                a, b = (self._pop(), self._pop())
                self._push(a + b)  # ADD
            elif op == 2:
                a, b = (self._pop(), self._pop())  # MUL
                self._push(a * b)
            elif op == 3:  # SUB
                a, b = (self._pop(), self._pop())
                self._push(a - b)  # DIV
            elif op == 4:
                a, b = (self._pop(), self._pop())  # MOD
                self._push(0 if b == 0 else a // b)
            elif op == 6:
                a, b = (self._pop(), self._pop())
                self._push(0 if b == 0 else a % b)
            else:
                self._step_compare(op)
    print('EVM skeleton defined')
    return (EVM,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Cell B: comparison and bitwise opcodes — monkey-patched onto `EVM`.
    Python's class system lets us split the implementation across cells
    without losing any state.
    """)
    return


@app.cell
def _(EVM):
    def _step_compare(self, op: int) -> None:
        if op == 0x10:    # LT
            a, b = self._pop(), self._pop(); self._push(1 if a < b else 0)
        elif op == 0x11:  # GT
            a, b = self._pop(), self._pop(); self._push(1 if a > b else 0)
        elif op == 0x14:  # EQ
            a, b = self._pop(), self._pop(); self._push(1 if a == b else 0)
        elif op == 0x15:  # ISZERO
            a = self._pop(); self._push(1 if a == 0 else 0)
        elif op == 0x16:  # AND
            a, b = self._pop(), self._pop(); self._push(a & b)
        elif op == 0x17:  # OR
            a, b = self._pop(), self._pop(); self._push(a | b)
        elif op == 0x19:  # NOT
            a = self._pop(); self._push(~a)  # Python ~a is -(a+1); % MOD gives correct 256-bit NOT
        else:
            self._step_memory(op)


    EVM._step_compare = _step_compare
    print('comparisons + bitwise attached')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Cell C: stack manipulation, memory, and storage opcodes.
    """)
    return


@app.cell
def _(EVM):
    def _step_memory(self, op: int) -> None:
        if op == 0x50:    # POP
            self._pop()
        elif op == 0x51:  # MLOAD
            off = self._pop()
            self._expand_mem(off + 32)
            self._push(int.from_bytes(self.memory[off:off + 32], 'big'))
        elif op == 0x52:  # MSTORE
            off, val = self._pop(), self._pop()
            self._expand_mem(off + 32)
            self.memory[off:off + 32] = val.to_bytes(32, 'big')
        elif op == 0x54:  # SLOAD
            key = self._pop()
            self._push(self.storage.get(key, 0))
        elif op == 0x55:  # SSTORE  — first pop = key (top), second pop = value
            key, val = self._pop(), self._pop()
            self.storage[key] = val
        else:
            self._step_control(op)


    EVM._step_memory = _step_memory
    print('memory + storage attached')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Cell D: control flow (`JUMP`, `JUMPI`), push data, stack shuffling, and
    `RETURN`. Also attaches the `run()` method.
    """)
    return


@app.cell
def _(EVM):
    def _step_control(self, op: int) -> None:
        if op == 0x56:    # JUMP
            dest = self._pop()
            if dest >= len(self.code) or self.code[dest] != 0x5b:
                raise RuntimeError(f'bad JUMP dest 0x{dest:x}')
            self.pc = dest
        elif op == 0x57:  # JUMPI
            dest, cond = self._pop(), self._pop()
            if cond != 0:
                if dest >= len(self.code) or self.code[dest] != 0x5b:
                    raise RuntimeError(f'bad JUMPI dest 0x{dest:x}')
                self.pc = dest
        elif op == 0x58:  # PC
            self._push(self.pc - 1)   # pc was already incremented past the PC opcode
        elif op == 0x5b:  # JUMPDEST
            pass                       # valid jump-target marker; no-op at runtime
        elif 0x60 <= op <= 0x7f:      # PUSH1 .. PUSH32
            n = op - 0x5f             # number of data bytes to consume
            val = int.from_bytes(self.code[self.pc:self.pc + n], 'big')
            self.pc += n
            self._push(val)
        elif op == 0x80:  # DUP1
            if not self.stack:
                raise RuntimeError('stack underflow')
            self._push(self.stack[-1])
        elif op == 0x90:  # SWAP1
            if len(self.stack) < 2:
                raise RuntimeError('stack underflow')
            self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]
        elif op == 0xf3:  # RETURN
            off, length = self._pop(), self._pop()
            self._expand_mem(off + length)
            self.return_data = bytes(self.memory[off:off + length])
            self.stopped = True
        else:
            raise RuntimeError(f'unknown opcode 0x{op:02x} at pc={self.pc - 1}')


    EVM._step_control = _step_control


    def run(self, max_steps: int = 100_000) -> None:
        n = 0
        while not self.stopped and self.pc < len(self.code):
            self.step()
            n += 1
            if n >= max_steps:
                raise RuntimeError('max_steps exceeded')
        if not self.stopped:
            self.stopped = True   # ran off the end of bytecode (implicit STOP)


    EVM.run = run
    print('control flow + run() attached — EVM complete')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. Demo: `(2 + 3) * 4`

    Bytecode: `PUSH1 0x04  PUSH1 0x03  PUSH1 0x02  ADD  MUL  STOP`

    Let's trace every step:

    ```
    pc=0  60 04   PUSH1 0x04   stack: [4]
    pc=2  60 03   PUSH1 0x03   stack: [4, 3]
    pc=4  60 02   PUSH1 0x02   stack: [4, 3, 2]   (2 on top)
    pc=6  01      ADD          pop 2, pop 3 -> push 5    stack: [4, 5]
    pc=7  02      MUL          pop 5, pop 4 -> push 20   stack: [20]
    pc=8  00      STOP
    ```

    Notice that `PUSH1 0x04` takes two bytes: opcode `60` plus data byte `04`.
    So after the three PUSHes, `pc = 6`, not 3.
    """)
    return


@app.cell
def _(EVM):
    _code = bytes.fromhex('600460036002010200')
    _evm = EVM(_code)  # PUSH1 0x04
    _evm.run()  # PUSH1 0x03
    assert _evm.stack == [20], f'expected [20], got {_evm.stack}'  # PUSH1 0x02
    print('final stack:', _evm.stack)  # ADD  -> 2+3 = 5  # MUL  -> 5*4 = 20  # STOP  # [20]
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 5. Storage demo — `uint x = 42`

    ```
    PUSH1 0x2a   push 42 (value)
    PUSH1 0x00   push 0  (storage slot, becomes the key)
    SSTORE       storage[0] = 42
    PUSH1 0x00   push 0  (same slot)
    SLOAD        push storage[0] -> 42 on stack
    STOP
    ```

    This is exactly how a Solidity `uint x = 42;` works under the hood —
    `SSTORE` to slot 0. Every `uint` state variable gets its own numbered
    slot in the contract's persistent storage.
    """)
    return


@app.cell
def _(EVM):
    _code = bytes.fromhex('602a60005560005400')
    _evm = EVM(_code)  # PUSH1 42     (value)
    _evm.run()  # PUSH1 0      (key = storage slot 0)
    print('stack:  ', _evm.stack)  # SSTORE       storage[0] = 42
    print('storage:', _evm.storage)  # PUSH1 0      (same slot)
    assert _evm.stack == [42]  # SLOAD        push storage[0]
    assert _evm.storage == {0: 42}  # STOP  # [42]  # {0: 42}
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 6. JUMPI loop — sum 1..10

    Compute `sum = 1 + 2 + ... + 10 = 55` entirely in EVM bytecode.
    We use storage slots as variables: slot 0 = `sum`, slot 1 = `i`.

    Pseudocode:
    ```
    storage[0] = 0   # sum
    storage[1] = 1   # i
    loop:
      if i > 10: goto end
      storage[0] = storage[0] + storage[1]   # sum += i
      storage[1] = storage[1] + 1            # i += 1
      goto loop
    end:
      STOP
    ```

    For the GT check: we push 10 first, then `i` (so `i` is on top). Then
    `GT` pops `a=i` and `b=10` and pushes `1 if i > 10`. When `i` first
    reaches 11 the JUMPI fires and we exit.

    ```
    pc   hex              ASM                    note
    0    60 00 60 00 55   PUSH1 0  PUSH1 0  SSTORE   storage[0]=0
    5    60 01 60 01 55   PUSH1 1  PUSH1 1  SSTORE   storage[1]=1
    10   5b               JUMPDEST              loop label
    11   60 0a            PUSH1 10              10 on stack (b for GT)
    13   60 01 54         PUSH1 1  SLOAD        i on top   (a for GT)
    16   11               GT                    a>b = i>10?
    17   60 2a 57         PUSH1 0x2a  JUMPI     if true jump to end (0x2a=42)
    20   60 01 54         PUSH1 1  SLOAD        load i
    23   60 00 54         PUSH1 0  SLOAD        load sum
    26   01               ADD                   sum+i
    27   60 00 55         PUSH1 0  SSTORE       storage[0]=sum+i
    30   60 01 54         PUSH1 1  SLOAD        load i
    33   60 01            PUSH1 1
    35   01               ADD                   i+1
    36   60 01 55         PUSH1 1  SSTORE       storage[1]=i+1
    39   60 0a 56         PUSH1 0x0a  JUMP      goto loop (0x0a=10)
    42   5b               JUMPDEST              end label
    43   00               STOP
    ```
    """)
    return


@app.cell
def _(EVM):
    # Build the bytecode programmatically so the offsets are provably correct.
    loop_code = bytearray()
    loop_code.extend([96, 0, 96, 0, 85])
    # ---- initialise storage ----
    # SSTORE pops key (top) then value; push value first, then key.
    loop_code.extend([96, 1, 96, 1, 85])  # storage[0] = 0 (sum)
    LOOP = len(loop_code)  # storage[1] = 1 (i)
    loop_code.extend([91])
    loop_code.extend([96, 10])  # pc=10 — loop JUMPDEST
    loop_code.extend([96, 1, 84])  # JUMPDEST loop
    loop_code.extend([17])
    # ---- condition: i > 10? ----
    # Push 10 first (b), then i (a); GT pops a then b -> 1 if a>b = i>10
    JUMPI_ARG = len(loop_code) + 1  # PUSH1 10
    loop_code.extend([96, 0, 87])  # PUSH1 slot1, SLOAD -> i
    loop_code.extend([96, 1, 84])  # GT  (i > 10?)
    loop_code.extend([96, 0, 84])
    loop_code.extend([1])  # index of the end-dest byte (filled later)
    loop_code.extend([96, 0, 85])  # PUSH1 <end>, JUMPI  (placeholder)
    loop_code.extend([96, 1, 84])
    # ---- loop body ----
    loop_code.extend([96, 1])  # load i
    loop_code.extend([1])  # load sum
    loop_code.extend([96, 1, 85])  # ADD -> sum+i
    loop_code.extend([96, LOOP, 86])  # storage[0] = sum+i
    END = len(loop_code)  # load i
    loop_code[JUMPI_ARG] = END  # PUSH1 1
    loop_code.extend([91])  # ADD -> i+1
    loop_code.extend([0])  # storage[1] = i+1
    loop_code = bytes(loop_code)  # PUSH1 <loop>, JUMP
    print(f'bytecode ({len(loop_code)} bytes): {loop_code.hex()}')
    # ---- end label ----
    print(f'LOOP dest=0x{LOOP:02x}  END dest=0x{END:02x}')  # pc=42
    assert loop_code[LOOP] == 91, 'loop JUMPDEST missing'  # back-patch the JUMPI target
    assert loop_code[END] == 91, 'end  JUMPDEST missing'  # JUMPDEST end
    _evm = EVM(loop_code)  # STOP
    _evm.run()
    assert _evm.storage[0] == 55, f'sum was {_evm.storage[0]}, expected 55'
    print('sum 1..10 =', _evm.storage[0])  # 55
    return (loop_code,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 7. Disassembler

    A disassembler reads bytecode and prints human-readable assembly. The
    tricky part is `PUSH` instructions: after each `PUSH1`..`PUSH32` opcode
    byte, there are `N` data bytes that must be consumed before the next
    opcode. We extend the opcode table with a few hundred real Ethereum
    opcodes so real contract bytecode prints cleanly.
    """)
    return


@app.cell
def _(loop_code):
    OPCODES: dict[int, str] = {0: 'STOP', 1: 'ADD', 2: 'MUL', 3: 'SUB', 4: 'DIV', 5: 'SDIV', 6: 'MOD', 7: 'SMOD', 8: 'ADDMOD', 9: 'MULMOD', 10: 'EXP', 11: 'SIGNEXTEND', 16: 'LT', 17: 'GT', 18: 'SLT', 19: 'SGT', 20: 'EQ', 21: 'ISZERO', 22: 'AND', 23: 'OR', 24: 'XOR', 25: 'NOT', 26: 'BYTE', 27: 'SHL', 28: 'SHR', 29: 'SAR', 32: 'KECCAK256', 48: 'ADDRESS', 49: 'BALANCE', 50: 'ORIGIN', 51: 'CALLER', 52: 'CALLVALUE', 53: 'CALLDATALOAD', 54: 'CALLDATASIZE', 55: 'CALLDATACOPY', 56: 'CODESIZE', 57: 'CODECOPY', 58: 'GASPRICE', 59: 'EXTCODESIZE', 60: 'EXTCODECOPY', 61: 'RETURNDATASIZE', 62: 'RETURNDATACOPY', 63: 'EXTCODEHASH', 64: 'BLOCKHASH', 65: 'COINBASE', 66: 'TIMESTAMP', 67: 'NUMBER', 68: 'DIFFICULTY', 69: 'GASLIMIT', 70: 'CHAINID', 71: 'SELFBALANCE', 72: 'BASEFEE', 80: 'POP', 81: 'MLOAD', 82: 'MSTORE', 83: 'MSTORE8', 84: 'SLOAD', 85: 'SSTORE', 86: 'JUMP', 87: 'JUMPI', 88: 'PC', 89: 'MSIZE', 90: 'GAS', 91: 'JUMPDEST', **{128 + i: f'DUP{i + 1}' for i in range(16)}, **{144 + i: f'SWAP{i + 1}' for i in range(16)}, 160: 'LOG0', 161: 'LOG1', 162: 'LOG2', 163: 'LOG3', 164: 'LOG4', 240: 'CREATE', 241: 'CALL', 242: 'CALLCODE', 243: 'RETURN', 244: 'DELEGATECALL', 245: 'CREATE2', 250: 'STATICCALL', 253: 'REVERT', 254: 'INVALID', 255: 'SELFDESTRUCT'}
      # ---- arithmetic ----
    def disasm(code: bytes) -> list[str]:
        """Disassemble EVM bytecode into a list of human-readable lines."""
        out, pc = ([], 0)
        while pc < len(_code):  # ---- comparison / bitwise ----
            op = _code[pc]
            if 96 <= op <= 127:
                n = op - 95
                data = _code[pc + 1:pc + 1 + n].hex()
                out.append(f'{pc:04x}  PUSH{n} 0x{data}')  # ---- hashing / env ----
                pc += 1 + n
            else:
                name = OPCODES.get(op, f'?? (0x{op:02x})')
                out.append(f'{pc:04x}  {name}')
                pc += 1
        return out
    print('OPCODES and disasm defined')
    print('\nDisassembly of loop_code:')
    for _line in disasm(loop_code):
    # Sanity: disassemble our loop bytecode
        print(' ', _line)  # ---- memory / storage / control ----  # ---- DUP1..DUP16, SWAP1..SWAP16 ----  # ---- logging ----  # ---- system ----  # PUSH1 .. PUSH32
    return (disasm,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 8. Read REAL deployed bytecode

    Foundry writes compiled artifacts to `out/<Contract>.sol/<Contract>.json`.
    The `deployedBytecode.object` field holds the hex-encoded bytecode that
    lives at the contract's address on-chain.
    """)
    return


@app.cell
def _(disasm):
    import json, pathlib
    _HERE = pathlib.Path(__file__).resolve().parent
    art_path = _HERE.parent / 'blockchain_primer' / 'out' / 'Counter.sol' / 'Counter.json'
    if not art_path.exists():
        print(f'WARNING: {art_path} not found — using hardcoded fallback.')
        deployed = bytes.fromhex('608060405234801561001057600080fd5b50')
    else:  # ERC-20-like selector dispatcher prefix; illustrative only
        art = json.loads(art_path.read_text())
        deployed_hex = art['deployedBytecode']['object'].removeprefix('0x')
        deployed = bytes.fromhex(deployed_hex)
        print('loaded from Counter.json')
    print(f'deployed bytecode: {len(deployed)} bytes')
    print('\nfirst 50 instructions:')
    for _line in disasm(deployed)[:50]:
        print(' ', _line)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### What you just read

    You are looking at the actual EVM instructions Solidity emitted for
    `Counter.sol`. The pattern at the top of every contract is the
    **selector dispatcher**:

    1. Load the first 4 bytes of calldata (`CALLDATALOAD` + shift) — these
       are the **function selector**: the first 4 bytes of
       `keccak256("functionName(paramTypes)")`.
    2. Compare the selector to each known selector via `EQ`.
    3. `JUMPI` to the matching function body.

    Our toy EVM cannot *run* this contract — we are missing `CALLDATALOAD`,
    `KECCAK256`, `CALL`, `LOG`, `REVERT`, `CREATE`, and about 110 other
    opcodes. But you can **read** it. That is a real, practical skill: when
    something goes wrong on-chain, this is what engineers look at.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 9. What is not here

    The ~115 opcodes we skipped include:

    - **`CALL` / `DELEGATECALL` / `CREATE` / `CREATE2`** — cross-contract
      calls; the engine for composability and proxy patterns.
    - **`LOG0`..`LOG4`** — emit events that off-chain listeners consume.
    - **`REVERT`** — roll back state changes and return an error message.
    - **Gas accounting** — every opcode costs gas; the EVM halts when gas
      runs out. We didn't track `gas` or charge anything.
    - **`KECCAK256`** — in-EVM hashing; used by mappings and the selector
      dispatcher.
    - **Precompiles** — built-in contracts at addresses 0x01..0x0a for
      ECDSA recovery, hashing, BN128 pairing, etc.
    - **`PUSH0`** (0x5f, added in Shanghai fork) — push a zero byte cheaply.

    The spine is built. From here, `notebooks/blockchain_primer/` takes over:
    real Solidity contracts, Foundry tests, and a live local chain.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 10. Export `_lib/evm.py`

    Write all reusable symbols to `_lib/evm.py` so future notebooks can
    `from _lib.evm import EVM, disasm`.
    """)
    return


@app.cell
def _(loop_code):
    import importlib, sys
    # Force a clean reload in case evm.py was imported in a previous run
    if '_lib.evm' in sys.modules:
        del sys.modules['_lib.evm']

    import _lib.evm as _evm

    # Smoke-test: arithmetic demo via the imported class
    _e = _evm.EVM(bytes.fromhex('6004600360020102' + '00'))
    _e.run()
    assert _e.stack == [20], f'lib smoke-test failed: {_e.stack}'

    # Verify disasm works on loop_code
    lines = _evm.disasm(loop_code)
    assert len(lines) > 0

    print('_lib/evm.py: EVM, OPCODES, disasm, MOD all present and working')
    return


if __name__ == "__main__":
    app.run()
