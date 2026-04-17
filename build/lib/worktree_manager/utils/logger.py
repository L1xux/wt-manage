"""Colored logging utility for worktree-manager CLI."""

import sys
from typing import Optional

# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


def _colorize(text: str, *styles: str) -> str:
    """Apply color styles to text."""
    return "".join(styles) + text + Colors.RESET


def info(message: str, prefix: str = "[*]") -> None:
    """Print info message in blue."""
    print(_colorize(f"{prefix} {message}", Colors.BLUE))


def success(message: str, prefix: str = "[+]") -> None:
    """Print success message in green."""
    print(_colorize(f"{prefix} {message}", Colors.GREEN))


def warning(message: str, prefix: str = "[!]") -> None:
    """Print warning message in yellow."""
    print(_colorize(f"{prefix} {message}", Colors.YELLOW))


def error(message: str, prefix: str = "[ERROR]") -> None:
    """Print error message in red."""
    print(_colorize(f"{prefix} {message}", Colors.RED, Colors.BOLD))


def dim(message: str) -> None:
    """Print dimmed/grayed message."""
    print(_colorize(message, Colors.GRAY))


def header(message: str) -> None:
    """Print section header in bold magenta."""
    print(_colorize(f"\n{message}", Colors.MAGENTA, Colors.BOLD))


def value(label: str, value: str) -> None:
    """Print label-value pair with cyan value."""
    print(f"  {label}: {_colorize(value, Colors.CYAN)}")


def section(title: str) -> None:
    """Print a section divider with title."""
    print(_colorize(f"\n{'=' * 60}", Colors.GRAY))
    print(_colorize(f"  {title}", Colors.BOLD, Colors.WHITE))
    print(_colorize(f"{'=' * 60}\n", Colors.GRAY))


def print_table_row(columns: list, widths: Optional[list] = None) -> None:
    """Print a table row with consistent column widths."""
    if widths is None:
        widths = [max(len(str(col)) for col in columns)]
    row = " | ".join(
        str(col).ljust(width) for col, width in zip(columns, widths)
    )
    print(row)


def print_table_header(columns: list, widths: list) -> None:
    """Print table header with separators."""
    separator = "-+-".join("-" * w for w in widths)
    print(separator)
    print_table_row(columns, widths)
    print(separator)