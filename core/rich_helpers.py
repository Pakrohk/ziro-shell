"""ziro-shell — Rich UI wrappers with graceful fallback.

Layer: 3 (Python core)
Spec: 008 R6, R7, R8, R9
"""

from __future__ import annotations

import sys
from typing import Any
from core.tty import is_tty


def get_console() -> Any | None:
    """Return a Rich Console instance if in a TTY and rich is installed.

    Returns None otherwise, signaling callers to fall back to plain text.
    """
    if not is_tty():
        return None
    try:
        from rich.console import Console
        return Console()
    except (ImportError, Exception):
        return None


def render_tree(title: str, items: list[tuple[str, bool, str]]) -> bool:
    """Render a Rich tree of health/diagnostic checks.

    items is a list of (name, ok_bool, detail_str).
    Returns True if rendered via Rich, False if fallback is needed.
    """
    console = get_console()
    if console is None:
        return False

    try:
        from rich.tree import Tree
        root = Tree(f"[bold]{title}[/bold]")
        for name, ok, detail in items:
            status_icon = "[green]✅[/green]" if ok else "[red]❌[/red]"
            style = "green" if ok else "bold red"
            msg = f" {detail}" if detail else ""
            root.add(f"{status_icon} [{style}]{name}[/{style}]{msg}")
        console.print(root)
        return True
    except Exception:
        return False


def render_table(title: str, headers: list[str], rows: list[list[str]]) -> bool:
    """Render a Rich table.

    Returns True if rendered via Rich, False if fallback is needed.
    """
    console = get_console()
    if console is None:
        return False

    try:
        from rich.table import Table
        from rich import box
        table = Table(title=title, box=box.ROUNDED, expand=True, header_style="bold cyan")
        styles = ["cyan", "green", "yellow", "magenta", "white"]
        for i, h in enumerate(headers):
            no_wrap = (i < len(headers) - 1)
            col_style = styles[i % len(styles)]
            table.add_column(h, style=col_style, no_wrap=no_wrap)
        for row in rows:
            table.add_row(*row)
        console.print(table)
        return True
    except Exception:
        return False


def render_columns(items: list[str]) -> bool:
    """Render items as Rich columns.

    Returns True if rendered via Rich, False if fallback is needed.
    """
    console = get_console()
    if console is None:
        return False

    try:
        from rich.columns import Columns
        from rich.panel import Panel
        panels = [Panel(f"[bold cyan]{item}[/bold cyan]", expand=True) for item in items]
        console.print(Columns(panels, equal=True))
        return True
    except Exception:
        return False
