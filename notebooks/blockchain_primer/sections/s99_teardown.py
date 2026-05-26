"""§99 — Stop anvil and tidy up."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md("## Teardown\n\nKill the anvil process. Re-run this notebook from the top to start fresh."),
        code(
            "_anvil_proc.terminate()\n"
            "_anvil_proc.wait(timeout=5)\n"
            "print('anvil stopped')"
        ),
    ]
