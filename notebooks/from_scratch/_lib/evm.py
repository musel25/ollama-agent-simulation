"""evm.py — toy EVM interpreter (~25 opcodes).

Stack machine interpreter for a subset of the Ethereum Virtual Machine.
Supports arithmetic, comparisons, bitwise ops, memory, storage, JUMP/JUMPI,
PUSH/DUP/SWAP, and RETURN. Does not implement gas accounting.

Exported symbols: MOD, EVM, OPCODES, disasm
"""

MOD = 2**256  # all values are 256-bit unsigned integers


class EVM:
    def __init__(self, code: bytes):
        self.code = code
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
            pad = ((end + 31) // 32) * 32 - len(self.memory)
            self.memory.extend(b'\x00' * pad)

    def step(self) -> None:
        op = self.code[self.pc]
        self.pc += 1
        if op == 0x00:
            self.stopped = True
        elif op == 0x01:
            a, b = self._pop(), self._pop(); self._push(a + b)
        elif op == 0x02:
            a, b = self._pop(), self._pop(); self._push(a * b)
        elif op == 0x03:
            a, b = self._pop(), self._pop(); self._push(a - b)
        elif op == 0x04:
            a, b = self._pop(), self._pop(); self._push(0 if b == 0 else a // b)
        elif op == 0x06:
            a, b = self._pop(), self._pop(); self._push(0 if b == 0 else a % b)
        else:
            self._step_compare(op)

    def _step_compare(self, op: int) -> None:
        if op == 0x10:
            a, b = self._pop(), self._pop(); self._push(1 if a < b else 0)
        elif op == 0x11:
            a, b = self._pop(), self._pop(); self._push(1 if a > b else 0)
        elif op == 0x14:
            a, b = self._pop(), self._pop(); self._push(1 if a == b else 0)
        elif op == 0x15:
            a = self._pop(); self._push(1 if a == 0 else 0)
        elif op == 0x16:
            a, b = self._pop(), self._pop(); self._push(a & b)
        elif op == 0x17:
            a, b = self._pop(), self._pop(); self._push(a | b)
        elif op == 0x19:
            a = self._pop(); self._push(~a)
        else:
            self._step_memory(op)

    def _step_memory(self, op: int) -> None:
        if op == 0x50:
            self._pop()
        elif op == 0x51:
            off = self._pop()
            self._expand_mem(off + 32)
            self._push(int.from_bytes(self.memory[off:off + 32], 'big'))
        elif op == 0x52:
            off, val = self._pop(), self._pop()
            self._expand_mem(off + 32)
            self.memory[off:off + 32] = val.to_bytes(32, 'big')
        elif op == 0x54:
            key = self._pop()
            self._push(self.storage.get(key, 0))
        elif op == 0x55:
            key, val = self._pop(), self._pop()
            self.storage[key] = val
        else:
            self._step_control(op)

    def _step_control(self, op: int) -> None:
        if op == 0x56:
            dest = self._pop()
            if dest >= len(self.code) or self.code[dest] != 0x5b:
                raise RuntimeError(f'bad JUMP dest 0x{dest:x}')
            self.pc = dest
        elif op == 0x57:
            dest, cond = self._pop(), self._pop()
            if cond != 0:
                if dest >= len(self.code) or self.code[dest] != 0x5b:
                    raise RuntimeError(f'bad JUMPI dest 0x{dest:x}')
                self.pc = dest
        elif op == 0x58:
            self._push(self.pc - 1)
        elif op == 0x5b:
            pass
        elif 0x60 <= op <= 0x7f:
            n = op - 0x5f
            val = int.from_bytes(self.code[self.pc:self.pc + n], 'big')
            self.pc += n
            self._push(val)
        elif op == 0x80:
            if not self.stack:
                raise RuntimeError('stack underflow')
            self._push(self.stack[-1])
        elif op == 0x90:
            if len(self.stack) < 2:
                raise RuntimeError('stack underflow')
            self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]
        elif op == 0xf3:
            off, length = self._pop(), self._pop()
            self._expand_mem(off + length)
            self.return_data = bytes(self.memory[off:off + length])
            self.stopped = True
        else:
            raise RuntimeError(f'unknown opcode 0x{op:02x} at pc={self.pc - 1}')

    def run(self, max_steps: int = 100_000) -> None:
        n = 0
        while not self.stopped and self.pc < len(self.code):
            self.step()
            n += 1
            if n >= max_steps:
                raise RuntimeError('max_steps exceeded')
        if not self.stopped:
            self.stopped = True


OPCODES: dict[int, str] = {
    0x00: 'STOP',  0x01: 'ADD',    0x02: 'MUL',  0x03: 'SUB',
    0x04: 'DIV',   0x05: 'SDIV',   0x06: 'MOD',  0x07: 'SMOD',
    0x08: 'ADDMOD',0x09: 'MULMOD', 0x0a: 'EXP',  0x0b: 'SIGNEXTEND',
    0x10: 'LT',    0x11: 'GT',    0x12: 'SLT',  0x13: 'SGT',
    0x14: 'EQ',    0x15: 'ISZERO',0x16: 'AND',  0x17: 'OR',
    0x18: 'XOR',   0x19: 'NOT',   0x1a: 'BYTE', 0x1b: 'SHL',
    0x1c: 'SHR',   0x1d: 'SAR',
    0x20: 'KECCAK256',
    0x30: 'ADDRESS',   0x31: 'BALANCE',    0x32: 'ORIGIN',
    0x33: 'CALLER',    0x34: 'CALLVALUE',  0x35: 'CALLDATALOAD',
    0x36: 'CALLDATASIZE', 0x37: 'CALLDATACOPY', 0x38: 'CODESIZE',
    0x39: 'CODECOPY', 0x3a: 'GASPRICE',   0x3b: 'EXTCODESIZE',
    0x3c: 'EXTCODECOPY', 0x3d: 'RETURNDATASIZE', 0x3e: 'RETURNDATACOPY',
    0x3f: 'EXTCODEHASH',
    0x40: 'BLOCKHASH', 0x41: 'COINBASE',  0x42: 'TIMESTAMP',
    0x43: 'NUMBER',    0x44: 'DIFFICULTY',0x45: 'GASLIMIT',
    0x46: 'CHAINID',   0x47: 'SELFBALANCE',0x48: 'BASEFEE',
    0x50: 'POP',   0x51: 'MLOAD',  0x52: 'MSTORE', 0x53: 'MSTORE8',
    0x54: 'SLOAD', 0x55: 'SSTORE', 0x56: 'JUMP',   0x57: 'JUMPI',
    0x58: 'PC',    0x59: 'MSIZE',  0x5a: 'GAS',    0x5b: 'JUMPDEST',
    **{0x80 + i: f'DUP{i + 1}'  for i in range(16)},
    **{0x90 + i: f'SWAP{i + 1}' for i in range(16)},
    0xa0: 'LOG0', 0xa1: 'LOG1', 0xa2: 'LOG2', 0xa3: 'LOG3', 0xa4: 'LOG4',
    0xf0: 'CREATE',       0xf1: 'CALL',         0xf2: 'CALLCODE',
    0xf3: 'RETURN',       0xf4: 'DELEGATECALL', 0xf5: 'CREATE2',
    0xfa: 'STATICCALL',   0xfd: 'REVERT',       0xfe: 'INVALID',
    0xff: 'SELFDESTRUCT',
}


def disasm(code: bytes) -> list[str]:
    """Disassemble EVM bytecode into a list of human-readable lines."""
    out, pc = [], 0
    while pc < len(code):
        op = code[pc]
        if 0x60 <= op <= 0x7f:
            n = op - 0x5f
            data = code[pc + 1:pc + 1 + n].hex()
            out.append(f'{pc:04x}  PUSH{n} 0x{data}')
            pc += 1 + n
        else:
            name = OPCODES.get(op, f'?? (0x{op:02x})')
            out.append(f'{pc:04x}  {name}')
            pc += 1
    return out
