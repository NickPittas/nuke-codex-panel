"""Location of the running Nuke's installed documentation.

Documentation and the runtime evidence carried by ``api_errors`` are on-demand references: nothing
is gated on reading them, and no run is refused because of an earlier API error.
"""

from __future__ import annotations

from pathlib import Path


def installed_documentation() -> dict:
    """Fast, filesystem-light metadata about the running Nuke's installed documentation."""
    import nuke

    root = Path(str(nuke.env["ExecutablePath"])).parent / "Documentation"
    return {
        "documentation_root": str(root),
        "documentation_available": root.is_dir(),
        "nuke_version": str(nuke.NUKE_VERSION_STRING),
    }
