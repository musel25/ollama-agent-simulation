"""§99 — Stop anvil and tidy up."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md("## Teardown\n\nKill the anvil process. Re-run this notebook from the top to start fresh."),
        code(
            "if anvil_proc.poll() is None:\n"
            "    anvil_proc.terminate()\n"
            "    anvil_proc.wait(timeout=5)\n"
            "    print('anvil stopped')\n"
            "else:\n"
            "    print('anvil was already stopped')"
        ),
    ]
