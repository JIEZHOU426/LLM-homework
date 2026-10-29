"""Entry point for the qAgent Textual UI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tui.app import QAgentApp  # noqa: E402


def main() -> None:
    QAgentApp().run()


if __name__ == "__main__":
    main()
