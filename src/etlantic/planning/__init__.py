"""Plan builder stages (internal refactor surface)."""

from etlantic.planning.builder import PlanBuilder, build_plan
from etlantic.planning.capabilities import (
    assert_capabilities_supported,
    assert_dataframe_engines_available,
    assert_quality_rule_capabilities,
    assert_spark_capabilities,
    assert_spark_engines_available,
    assert_sql_engines_available,
    assert_sql_write_capabilities,
    assert_storage_delta_capabilities,
    is_dataframe_engine,
)

__all__ = [
    "PlanBuilder",
    "assert_capabilities_supported",
    "assert_dataframe_engines_available",
    "assert_quality_rule_capabilities",
    "assert_spark_capabilities",
    "assert_spark_engines_available",
    "assert_sql_engines_available",
    "assert_sql_write_capabilities",
    "assert_storage_delta_capabilities",
    "build_plan",
    "is_dataframe_engine",
]
