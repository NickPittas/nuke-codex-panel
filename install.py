#!/usr/bin/env python3
"""Install, verify or repair the Nuke Codex Panel plugin and its private Pi runtime.

    python3 install.py [--target PATH] [--nuke-dir PATH] [--no-register] [--check]
    py -3 install.py ...                                                   (Windows)

Run it with a standalone Python 3.11+ (not Nuke's). See docs/INSTALLATION.md.
"""

import sys

if sys.version_info < (3, 11):
    sys.exit("install.py needs Python 3.11 or newer (found {}).".format(sys.version.split()[0]))

from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from nuke_codex_panel.installer.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(source_root=ROOT))
