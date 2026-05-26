"""Cell factories. One source of truth for nbformat cell construction."""
from __future__ import annotations
import nbformat


def md(source: str) -> dict:
    return nbformat.v4.new_markdown_cell(source)


def code(source: str) -> dict:
    return nbformat.v4.new_code_cell(source)
