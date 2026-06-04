"""Assemble 01a0_blockchain_primer.py (marimo) from sections/*.py modules.

Each section module exposes a ``cells()`` function returning notebook cells in
Jupyter's nbformat dict shape. We assemble an ``nbformat`` notebook in memory,
write it to a temp file, then run ``marimo convert`` to produce the final
marimo notebook that lives next to this script.
"""
from __future__ import annotations
import importlib, pathlib, subprocess, sys, tempfile
import nbformat

HERE = pathlib.Path(__file__).parent
NB_PATH = HERE / "01a0_blockchain_primer.py"

SECTION_MODULES = [
    "sections.s00_setup",
    "sections.s01_chain",
    "sections.s02_accounts",
    "sections.s03_transactions",
    "sections.s04_state_history",
    "sections.s05_deploy",
    "sections.s06_evm",
    "sections.s07_solidity",
    "sections.s08_events",
    "sections.s09_foundry",
    "sections.s10_escrow",
    "sections.s99_teardown",
]


def main() -> None:
    sys.path.insert(0, str(HERE))
    nb = nbformat.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    }
    cells: list = []
    for mod_name in SECTION_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError:
            print(f"skip (missing): {mod_name}")
            continue
        cells.extend(mod.cells())
        print(f"  + {mod_name}: {len(mod.cells())} cells")
    nb.cells = cells

    with tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False) as tmp:
        tmp_path = pathlib.Path(tmp.name)
    try:
        nbformat.write(nb, tmp_path)
        subprocess.run(
            ["marimo", "-q", "-y", "convert", str(tmp_path), "-o", str(NB_PATH)],
            check=True,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    print(f"wrote {NB_PATH} ({len(cells)} cells)")


if __name__ == "__main__":
    main()
