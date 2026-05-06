"""Spawn a local Anvil node from Python.

Used by notebooks and `tests/test_end_to_end.py` so we don't need the
Docker stack for in-process demos.
"""
from __future__ import annotations

import socket
import subprocess
import time
from contextlib import contextmanager
from typing import Iterator


def _wait_for_port(host: str, port: int, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
                return
            except OSError:
                time.sleep(0.1)
    raise TimeoutError(f"anvil never accepted on {host}:{port}")


@contextmanager
def anvil(port: int = 8545,
          host: str = "127.0.0.1",
          block_time: float = 1.0) -> Iterator[str]:
    """Spawn anvil; yield its RPC URL; terminate on exit.

    Requires the `anvil` binary on PATH (install Foundry).
    """
    proc = subprocess.Popen(
        ["anvil", "--host", host, "--port", str(port),
         "--block-time", str(block_time)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_port(host, port)
        yield f"http://{host}:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
