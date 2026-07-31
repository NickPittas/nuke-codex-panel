"""Dockable Codex client for Foundry Nuke."""

__version__ = "0.1.0.dev0"


def register_panel():
    """Register the panel lazily so importing package metadata works outside Nuke."""
    from .panel import register_panel as _register_panel

    return _register_panel()
