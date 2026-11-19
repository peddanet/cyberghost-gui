"""Prints tables in the layout of the official program."""
from typing import Any


def table(header: list[str], rows: list[list[Any]]) -> str:
    """Format a table.

    Args:
        header: Column titles.
        rows: Data rows.

    Returns:
        Table text.
    """
    cells = [header, *rows]
    widths = [max(len(str(row[i])) for row in cells) for i in range(len(header))]
    rule = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    lines = [rule]
    for index, row in enumerate(cells):
        lines.append("| " + " | ".join(str(c).ljust(w) for c, w in zip(row, widths)) + " |")
        if index == 0:
            lines.append(rule)
    return "\n".join([*lines, rule]) + "\n"
