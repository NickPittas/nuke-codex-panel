"""Nuke GUI startup entrypoint."""

import nuke

from .panel import register_panel


if nuke.GUI:
    register_panel()
