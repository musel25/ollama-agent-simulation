"""Test that shared.anvil can spin up and tear down a local Anvil."""
import shutil
import socket
import time

import pytest

from shared.anvil import anvil


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


@pytest.mark.skipif(shutil.which("anvil") is None,
                    reason="anvil binary not on PATH")
def test_anvil_spawns_and_terminates():
    with anvil(port=18545) as rpc_url:
        assert rpc_url == "http://127.0.0.1:18545"
        assert _port_open(18545)
    # Give the kernel a moment to release the port
    for _ in range(20):
        if not _port_open(18545):
            break
        time.sleep(0.1)
    assert not _port_open(18545)
