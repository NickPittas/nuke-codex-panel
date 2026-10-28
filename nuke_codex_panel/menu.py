"""Nuke GUI startup entrypoint."""

import nuke

from .bridge import ensure_bridge
from .panel import register_panel


if nuke.GUI:
    register_panel()
    try:
        ensure_bridge()
    except Exception as exc:
        print("Nuke Codex Panel: bridge unavailable: %s" % exc)
