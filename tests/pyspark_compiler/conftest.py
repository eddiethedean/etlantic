"""Route PySpark imports to sparkless for JVM-free portable compiler tests."""

from __future__ import annotations

import os

os.environ.setdefault("SPARKLESS_TEST_MODE", "sparkless")

from etlantic_pyspark.sparkless_shim import install

install()
