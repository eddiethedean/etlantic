"""Sparkless shim for differential corpus (default CI path)."""

from __future__ import annotations

import os

os.environ.setdefault("SPARKLESS_TEST_MODE", "sparkless")

try:
    from etlantic_pyspark.sparkless_shim import install

    install()
except Exception:
    pass
