"""ETLantic language server package."""

from __future__ import annotations

from etlantic_lsp._version import __version__
from etlantic_lsp.server import create_server

__all__ = ["__version__", "create_server"]
