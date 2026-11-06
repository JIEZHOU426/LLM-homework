"""Entry point for the qAgent Textual UI.

At startup, if the current workspace has no ``config.ini``, one is created
pre-filled with mock (placeholder) values; the TUI then shows a dialog asking
the user to fill in real configuration and restart.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tui.app import QAgentApp  # noqa: E402
from tui.bootstrap import ensure_workspace_config  # noqa: E402


def main() -> None:
    config_created = ensure_workspace_config(Path.cwd())
    QAgentApp(config_created=config_created).run()


if __name__ == "__main__":
    main()
