"""§0 — Notebook setup: imports, run() helper, start anvil.

This section is invisible to the reader as a "section" — its purpose is to
establish the runtime environment used by every later section.
"""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "# 01a0 — Blockchain & smart contracts primer\n"
            "\n"
            "A ground-up, hands-on tour. We drive a real local Ethereum chain "
            "(`anvil`) through `cast` and `forge`, naming each concept after we've "
            "executed it. By the last section you'll be able to read "
            "[BandwidthEscrow.sol](../../contracts/src/BandwidthEscrow.sol) line by line.\n"
            "\n"
            "**Prereq:** `anvil`, `cast`, `forge` on PATH (Foundry installed). "
            "Run cells top to bottom — anvil is started in the next cell and "
            "killed in the very last cell."
        ),
        code(
            "# --- Notebook runtime setup ---------------------------------------\n"
            "import atexit, subprocess, time, shutil, sys, pathlib, json, os\n"
            "\n"
            "PRIMER_DIR = pathlib.Path.cwd().resolve()\n"
            "REPO_ROOT = PRIMER_DIR.parent.parent\n"
            "RPC = 'http://127.0.0.1:8545'\n"
            "\n"
            "def run(cmd, cwd=None, check=True):\n"
            "    \"\"\"Run a shell command, show it, return stdout.\"\"\"\n"
            "    print('$', ' '.join(str(c) for c in cmd))\n"
            "    r = subprocess.run(cmd, cwd=cwd or PRIMER_DIR, capture_output=True, text=True)\n"
            "    if r.stdout: print(r.stdout.rstrip())\n"
            "    if r.returncode != 0:\n"
            "        if r.stderr: print(r.stderr.rstrip(), file=sys.stderr)\n"
            "        if check: raise SystemExit(f'command failed: {cmd}')\n"
            "    return r.stdout.strip()\n"
            "\n"
            "for tool in ('anvil', 'cast', 'forge'):\n"
            "    assert shutil.which(tool), f'{tool} not found on PATH'\n"
            "print('Foundry tools OK')"
        ),
        code(
            "# --- Start anvil --------------------------------------------------\n"
            "_anvil_proc = subprocess.Popen(\n"
            "    ['anvil', '--host', '127.0.0.1', '--port', '8545', '--silent'],\n"
            "    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,\n"
            ")\n"
            "atexit.register(_anvil_proc.terminate)\n"
            "\n"
            "# Wait for RPC to respond.\n"
            "for _ in range(30):\n"
            "    try:\n"
            "        run(['cast', 'block-number', '--rpc-url', RPC], check=True)\n"
            "        break\n"
            "    except SystemExit:\n"
            "        time.sleep(0.2)\n"
            "else:\n"
            "    raise RuntimeError('anvil did not come up')\n"
            "print(f'anvil PID={_anvil_proc.pid}')"
        ),
    ]
