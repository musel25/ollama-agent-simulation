"""Assemble 01a0_blockchain_primer.ipynb from sections/*.py modules."""
from __future__ import annotations
import importlib, pathlib, nbformat

HERE = pathlib.Path(__file__).parent
NB_PATH = HERE / "01a0_blockchain_primer.ipynb"

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
    import sys
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
            # Section not yet implemented — skip during incremental build.
            print(f"skip (missing): {mod_name}")
            continue
        cells.extend(mod.cells())
        print(f"  + {mod_name}: {len(mod.cells())} cells")
    nb.cells = cells
    nbformat.write(nb, NB_PATH)
    print(f"wrote {NB_PATH} ({len(cells)} cells)")


if __name__ == "__main__":
    main()
