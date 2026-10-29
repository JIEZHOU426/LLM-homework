"""Allow ``py -m tui`` from the qAgent root."""

from .app import QAgentApp


def main() -> None:
    QAgentApp().run()


if __name__ == "__main__":
    main()
