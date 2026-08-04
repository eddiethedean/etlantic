"""Console entry for etlantic-lsp."""

from __future__ import annotations


def main() -> None:
    from etlantic_lsp.server import run_stdio

    run_stdio()


if __name__ == "__main__":
    main()
