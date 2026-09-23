# pyright: reportMissingImports=false, reportUnknownVariableType=false
"""Route PySpark imports to sparkless for JVM-free Spark tests.

By default, Spark suite tests run against sparkless. Set
``SPARKLESS_TEST_MODE=pyspark`` to exercise real PySpark instead.
"""

from __future__ import annotations

import os

# Prefer sparkless unless the suite explicitly requests real PySpark.
os.environ.setdefault("SPARKLESS_TEST_MODE", "sparkless")

from etlantic_pyspark.sparkless_shim import install

install()
