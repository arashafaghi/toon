"""Application footer (host-owned; no plugin required).

Wraps Textual's :class:`~textual.widgets.Footer`, so it automatically lists
every *visible* key binding (``Binding(..., show=True)``) in
``ToonApp.BINDINGS`` and appends the command-palette hint.

Adding a shortcut to the footer therefore means only one thing: add a binding to
``ToonApp.BINDINGS``. To add non-binding hints (text labels), extend
:attr:`AppFooter.EXTRA_HINTS`.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Footer, Static

__all__ = ["AppFooter"]


class AppFooter(Footer):
    """Footer bar listing the active key bindings."""

    #: Extra static hints appended after the bindings (empty by default).
    #: Example: ``EXTRA_HINTS = ("esc back", "? help")``.
    EXTRA_HINTS: tuple[str, ...] = ()

    def compose(self) -> ComposeResult:
        """Yield the binding keys (from Textual), then any extra hints."""
        yield from super().compose()
        for hint in self.EXTRA_HINTS:
            yield Static(hint, classes="footer-hint")
