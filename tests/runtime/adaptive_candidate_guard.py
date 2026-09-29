"""Helpers for tests whose adaptive execution needs a current candidate pin."""

from __future__ import annotations

from etlantic import __version__ as etlantic_version
from etlantic.runtime.adaptive_support import candidate_bundle

_bundle, _ = candidate_bundle()
_local_etlantic_pin = _bundle["rows"]["chain/1:local"]["versions"]["etlantic"]

ADAPTIVE_CANDIDATE_MATCHES_PACKAGE = etlantic_version == _local_etlantic_pin
ADAPTIVE_CANDIDATE_MISMATCH_REASON = (
    "the packaged adaptive candidate is not qualified for this ETLantic version"
)
