"""CSV format controls and fail-closed input validation for local-files."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import anyio
import pytest

from etlantic import Data
from etlantic.connectors.errors import ConnectorConfigError, ConnectorReadError
from etlantic.connectors.local_files import (
    LocalFilesSourceConnector,
    read_csv_identities,
)
from etlantic.connectors.models import SourcePlan
from etlantic.io_policy import SafeIoPolicy


class CsvRecord(Data):
    id: int
    name: str


def _binding(**options: Any) -> dict[str, Any]:
    return {
        "provider": "local-files",
        "location": "landing",
        "kind": "source",
        "config": {
            "format": "csv",
            "mode": "snapshot",
            "root": "landing",
            "root_ref": "orders-landing",
            "glob": "*.csv",
            **options,
        },
    }


def _collect(
    base: Path,
    *,
    connector: LocalFilesSourceConnector | None = None,
    binding: Mapping[str, Any] | None = None,
) -> tuple[SourcePlan, list[Any], dict[str, Any]]:
    context: dict[str, Any] = {
        "run_id": "csv-0-56-test",
        "safe_io": SafeIoPolicy.for_root(base),
        "contract_type": CsvRecord,
    }
    provider = connector or LocalFilesSourceConnector()
    selected_binding = dict(binding or _binding())

    async def run() -> tuple[SourcePlan, list[Any]]:
        plan = await provider.plan_read(binding=selected_binding, context=context)
        records: list[Any] = []
        async for batch in provider.read_batches(
            plan=plan, binding=selected_binding, context=context
        ):
            records.extend(batch.records)
        return plan, records

    plan, records = anyio.run(run)
    return plan, records, context


def test_local_files_csv_encoding_and_delimiter_are_pinned_and_typed(
    tmp_path: Path,
) -> None:
    landing = tmp_path / "landing"
    landing.mkdir()
    (landing / "orders.csv").write_bytes("\ufeffid;name\n42;Zoë\n".encode("utf-8"))

    plan, records, _context = _collect(
        tmp_path,
        binding=_binding(encoding="utf-8-sig", delimiter=";"),
    )

    assert plan.listing_intent["encoding"] == "utf-8-sig"
    assert plan.listing_intent["delimiter"] == ";"
    assert len(records) == 1
    assert records[0].id == 42
    assert records[0].name == "Zoë"

    first_schema = LocalFilesSourceConnector().info().configuration_schema
    first_schema["properties"].clear()
    assert (
        "encoding"
        in LocalFilesSourceConnector().info().configuration_schema["properties"]
    )


@pytest.mark.parametrize(
    ("encoding", "name"),
    [("latin-1", "André"), ("cp1252", "Zoë — café")],
)
def test_local_files_csv_supports_declared_legacy_encodings(
    tmp_path: Path, encoding: str, name: str
) -> None:
    landing = tmp_path / "landing"
    landing.mkdir()
    (landing / "orders.csv").write_bytes(f"id,name\n42,{name}\n".encode(encoding))

    _plan, records, _context = _collect(
        tmp_path,
        binding=_binding(encoding=encoding),
    )

    assert records[0].id == 42
    assert records[0].name == name


@pytest.mark.parametrize(
    ("options", "expected_code"),
    [
        ({"encoding": "utf-16"}, "PMCONN704"),
        ({"encoding": "UTF-8-SIG"}, "PMCONN704"),
        ({"encoding": 4}, "PMCONN704"),
        ({"delimiter": "::"}, "PMCONN705"),
        ({"delimiter": None}, "PMCONN705"),
        ({"delimiter": "\n"}, "PMCONN705"),
        ({"mode": True}, "PMCONN701"),
        ({"required_capabilities": "snapshot"}, "PMCONN706"),
        ({"credential": "do-not-echo"}, "PMCONN706"),
    ],
)
def test_local_files_rejects_unsupported_csv_options_without_echoing_values(
    tmp_path: Path, options: dict[str, Any], expected_code: str
) -> None:
    connector = LocalFilesSourceConnector()
    binding = _binding(**options)

    async def plan() -> None:
        await connector.plan_read(binding=binding, context={})

    with pytest.raises(ConnectorConfigError) as caught:
        anyio.run(plan)
    assert caught.value.code == expected_code
    assert "do-not-echo" not in str(caught.value)


def test_local_files_allows_empty_glob_only_when_requested(tmp_path: Path) -> None:
    (tmp_path / "landing").mkdir()
    binding = _binding(empty_match="allow")

    plan, records, context = _collect(tmp_path, binding=binding)

    assert plan.listing_intent["empty_match"] == "allow"
    assert records == []
    manifest = context["landing_read_manifest"]
    assert manifest.file_count == 0

    with pytest.raises(ConnectorReadError) as caught:
        _collect(tmp_path)
    assert caught.value.code == "PMCONN710"


@pytest.mark.parametrize(
    ("content", "options", "expected_code"),
    [
        (b"", {"delimiter": ";"}, "PMCONN774"),
        (b'id;name\n1;"unfinished\n', {"delimiter": ";"}, "PMCONN777"),
        (b"id;name\n1\n", {"delimiter": ";"}, "PMCONN778"),
        (b"id;name\n1;\xff\n", {"delimiter": ";"}, "PMCONN777"),
        (b"id;id\n1;2\n", {"delimiter": ";"}, "PMCONN778"),
    ],
)
def test_local_files_rejects_empty_malformed_and_undecodable_csv(
    tmp_path: Path,
    content: bytes,
    options: dict[str, Any],
    expected_code: str,
) -> None:
    landing = tmp_path / "landing"
    landing.mkdir()
    (landing / "orders.csv").write_bytes(content)

    with pytest.raises(ConnectorReadError) as caught:
        _collect(tmp_path, binding=_binding(**options))
    assert caught.value.code == expected_code


def test_local_files_enforces_file_and_row_budgets(tmp_path: Path) -> None:
    landing = tmp_path / "landing"
    landing.mkdir()
    path = landing / "orders.csv"
    path.write_text("id,name\n1,one\n2,two\n", encoding="utf-8")

    with pytest.raises(ConnectorReadError) as file_error:
        _collect(tmp_path, connector=LocalFilesSourceConnector(max_file_bytes=8))
    assert file_error.value.code == "PMCONN764"

    with pytest.raises(ConnectorReadError) as row_error:
        _collect(tmp_path, connector=LocalFilesSourceConnector(max_rows=1))
    assert row_error.value.code == "PMCONN776"


def test_local_files_detects_content_change_after_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    landing = tmp_path / "landing"
    landing.mkdir()
    path = landing / "orders.csv"
    path.write_text("id,name\n1,alpha\n", encoding="utf-8")

    def change_after_listing(
        root: Path,
        identities: Any,
        **options: Any,
    ) -> list[Any]:
        path.write_text("id,name\n9,alpha\n", encoding="utf-8")
        return read_csv_identities(root, identities, **options)

    monkeypatch.setattr(
        "etlantic.connectors.local_files.read_csv_identities", change_after_listing
    )
    with pytest.raises(ConnectorReadError) as caught:
        _collect(tmp_path)
    assert caught.value.code == "PMCONN773"
