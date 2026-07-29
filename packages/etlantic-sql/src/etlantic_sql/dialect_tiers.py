"""SQL dialect support tiers for the reference ``etlantic-sql`` plugin.

Tier A dialects are exercised in CI (SQLite + PostgreSQL). Tier B dialects
are detected and capability-gated — planning must fail closed for features
the plugin does not truthfully implement.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

# Live CI / reference semantics.
TIER_A = frozenset({"sqlite", "postgresql"})

# Detected but not claimed as fully supported by the reference plugin.
TIER_B = frozenset(
    {
        "mysql",
        "mariadb",
        "mssql",
        "oracle",
        "cockroachdb",
        "duckdb",
        "redshift",
        "snowflake",
        "bigquery",
    }
)


@dataclass(frozen=True, slots=True)
class DialectInfo:
    """Normalized dialect identity and support tier."""

    name: str
    tier: str  # "A" | "B" | "unknown"
    scheme: str

    @property
    def is_tier_a(self) -> bool:
        return self.tier == "A"

    @property
    def supports_merge(self) -> bool:
        return self.name == "postgresql"

    @property
    def supports_returning(self) -> bool:
        return self.name == "postgresql"

    @property
    def supports_transactional_ddl(self) -> bool:
        return self.name == "postgresql"

    @property
    def supports_compound_select(self) -> bool:
        return self.is_tier_a

    @property
    def supports_cte(self) -> bool:
        return self.is_tier_a


def detect_dialect_info(url: str) -> DialectInfo:
    """Classify a SQLAlchemy URL into a dialect name and support tier."""
    raw = (url or "").strip()
    if "://" in raw:
        scheme = raw.split("://", 1)[0].lower()
    else:
        parsed = urlparse(raw)
        scheme = (parsed.scheme or raw.split("+", 1)[0] or "sqlite").lower()

    # Strip driver suffixes: postgresql+psycopg2 → postgresql
    base = scheme.split("+", 1)[0]
    if base in {"postgres", "postgresql"}:
        name = "postgresql"
    elif base in {"sqlite", "sqlite3"}:
        name = "sqlite"
    elif base in TIER_B:
        name = base
    elif base.startswith("mysql"):
        name = "mysql"
    elif base.startswith("mssql"):
        name = "mssql"
    else:
        name = base or "unknown"

    if name in TIER_A:
        tier = "A"
    elif name in TIER_B:
        tier = "B"
    else:
        tier = "unknown"
    return DialectInfo(name=name, tier=tier, scheme=scheme)


def assert_tier_a_or_raise(info: DialectInfo, *, feature: str) -> None:
    """Fail closed when a Tier A-only feature is requested on another dialect."""
    if info.is_tier_a:
        return
    raise ValueError(
        f"SQL feature {feature!r} requires a Tier A dialect "
        f"(sqlite|postgresql); got {info.name!r} (tier {info.tier})."
    )
