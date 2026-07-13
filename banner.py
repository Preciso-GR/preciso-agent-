from __future__ import annotations

import os
import sys

# Red-velvet theme: a deep-maroon-to-crimson gradient down the wordmark, with
# rose-cream accents for labels. ANSI 256-color codes, degrading to plain text
# on non-TTY output or when NO_COLOR is set.

_WORDMARK = (
    "██████╗ ██████╗ ███████╗ ██████╗██╗███████╗ ██████╗ ",
    "██╔══██╗██╔══██╗██╔════╝██╔════╝██║██╔════╝██╔═══██╗",
    "██████╔╝██████╔╝█████╗  ██║     ██║███████╗██║   ██║",
    "██╔═══╝ ██╔══██╗██╔══╝  ██║     ██║╚════██║██║   ██║",
    "██║     ██║  ██║███████╗╚██████╗██║███████║╚██████╔╝",
    "╚═╝     ╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝╚══════╝ ╚═════╝ ",
)

_VELVET_GRADIENT = (52, 88, 124, 160, 196, 197)  # one shade per wordmark row
_ACCENT = 217  # rose cream — info labels
_VALUE = 131   # muted brick — info values
_RULE = 88     # dark velvet — divider rule

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _color_enabled() -> bool:
    return sys.stdout.isatty() and not os.getenv("NO_COLOR")


def _fg(code: int) -> str:
    return f"\033[38;5;{code}m"


def print_banner(info: list[tuple[str, str]], tagline: str = "local-first GraphRAG agent") -> None:
    """Print the PRECISO wordmark and startup info in the red-velvet theme."""
    color = _color_enabled()
    width = max(len(row) for row in _WORDMARK)

    print()
    for row, shade in zip(_WORDMARK, _VELVET_GRADIENT):
        print(f"{_fg(shade)}{_BOLD}{row}{_RESET}" if color else row)

    centered_tagline = f"· {tagline} ·".center(width)
    print(f"{_fg(_ACCENT)}{_DIM}{centered_tagline}{_RESET}" if color else centered_tagline)

    rule = "─" * width
    print(f"{_fg(_RULE)}{rule}{_RESET}" if color else rule)

    label_width = max((len(label) for label, _ in info), default=0)
    for label, value in info:
        if color:
            print(f"  {_fg(_ACCENT)}{label.ljust(label_width)}{_RESET}  {_fg(_VALUE)}{value}{_RESET}")
        else:
            print(f"  {label.ljust(label_width)}  {value}")

    print(f"{_fg(_RULE)}{rule}{_RESET}" if color else rule)
    print()
