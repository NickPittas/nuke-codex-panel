"""Qt-free installer for the Nuke Codex Panel plugin (driven by the root ``install.py``).

Standard library only; run with a standalone Python 3.11+, never Nuke's interpreter. The panel never
imports this package at runtime: downloads, ``npm``, hashing and process spawns live here, away from
the UI thread. The resolver the panel uses is ``nuke_codex_panel.pi_runtime``.
"""
