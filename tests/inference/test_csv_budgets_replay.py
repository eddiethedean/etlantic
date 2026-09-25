"""Regression coverage for bounded CSV reads and independent replay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import etlantic as etl


def test_inference_limits_round_trip_separate_byte_budgets() -> None:
    limits = etl.InferenceLimits(
        max_bytes=512,
        max_materialized_bytes=256,
        max_field_size=128,
    )

    assert etl.InferenceLimits.from_dict(limits.to_dict()) == limits


def test_csv_raw_byte_budget_counts_physical_reads(tmp_path: Path) -> None:
    path = tmp_path / "many-rows.csv"
    path.write_text("id,payload\n" + "".join(f"{i},small\n" for i in range(100)))
    limit = 32

    result = etl.infer_csv(
        path,
        limits=etl.InferenceLimits(max_rows=500, max_bytes=limit),
    )

    assert path.stat().st_size > limit
    assert 0 < result.provenance["raw_bytes_observed"] <= limit
    assert result.provenance["raw_byte_limit_applies"] is True
    assert result.provenance["sampled"] is True
    assert "raw_bytes" in result.provenance["limit_reasons"]
    assert "INFER_CSV_BYTE_LIMIT" in {item.code for item in result.diagnostics}
    assert (
        result.provenance["materialized_bytes_observed"]
        == result.provenance["bytes_observed"]
    )


def test_csv_exact_raw_byte_boundary_is_not_reported_as_limited(tmp_path: Path) -> None:
    path = tmp_path / "exact.csv"
    content = "id\n1\n2\n"
    path.write_bytes(content.encode())

    result = etl.infer_csv(
        path,
        limits=etl.InferenceLimits(max_rows=10, max_bytes=len(content.encode())),
    )

    assert result.provenance["raw_bytes_observed"] == len(content.encode())
    assert result.provenance["raw_byte_limit_applies"] is True
    assert result.provenance["sampled"] is False
    assert "INFER_CSV_BYTE_LIMIT" not in {item.code for item in result.diagnostics}


def test_csv_raw_byte_limit_flag_is_false_when_unbounded(tmp_path: Path) -> None:
    path = tmp_path / "unbounded.csv"
    path.write_text("id\n1\n")

    result = etl.infer_csv(
        path,
        limits=etl.InferenceLimits(max_bytes=None),
    )

    assert result.provenance["raw_bytes_observed"] == path.stat().st_size
    assert result.provenance["raw_byte_limit_applies"] is False


def test_csv_field_size_has_a_distinct_diagnostic(tmp_path: Path) -> None:
    path = tmp_path / "large-field.csv"
    path.write_text("value\n" + "x" * 40 + "\n")

    result = etl.infer_csv(
        path,
        limits=etl.InferenceLimits(max_bytes=1024, max_field_size=8),
    )

    assert "INFER_CSV_FIELD_LIMIT" in {item.code for item in result.diagnostics}
    assert result.provenance["limit_reason"] == "field_size"


def test_csv_materialized_budget_is_separate_from_raw_budget(tmp_path: Path) -> None:
    path = tmp_path / "materialized.csv"
    path.write_text("id,payload\n1,small\n2,small\n")

    result = etl.infer_csv(
        path,
        limits=etl.InferenceLimits(
            max_rows=10,
            max_bytes=1024,
            max_materialized_bytes=1,
        ),
    )

    assert result.provenance["raw_bytes_observed"] == path.stat().st_size
    assert result.provenance["sampled"] is True
    assert "materialized_bytes" in result.provenance["limit_reasons"]
    assert "raw_bytes" not in result.provenance["limit_reasons"]


def test_csv_row_and_raw_byte_limits_can_both_be_reported(tmp_path: Path) -> None:
    path = tmp_path / "row-and-byte-limits.csv"
    path.write_text("id\n" + "".join(f"{i}\n" for i in range(100)))

    result = etl.infer_csv(
        path,
        limits=etl.InferenceLimits(max_rows=1, max_bytes=24),
    )

    assert result.provenance["rows_observed"] == 1
    assert result.provenance["raw_bytes_observed"] <= 24
    assert set(result.provenance["limit_reasons"]) == {"rows", "raw_bytes"}


def test_csv_replay_preserves_parser_options_and_finishes_after_return(
    tmp_path: Path,
) -> None:
    path = tmp_path / "multiline.csv"
    path.write_bytes('id;note\r\n1;"hello\r\nworld"\r\n2;next\r\n'.encode("utf-16"))
    options = {
        "encoding": "utf-16",
        "delimiter": ";",
        "strict": True,
    }

    result = etl.infer_csv(
        path,
        options=options,
        limits=etl.InferenceLimits(max_rows=1),
        retain_rows=True,
    )

    assert result.replay is not None
    assert result.provenance["parser_options"]["encoding"] == "utf-16"
    assert result.provenance["source_identity"] == result.schema.identity
    assert list(result.replay.take()) == [
        {"id": 1, "note": "hello\r\nworld"},
        {"id": 2, "note": "next"},
    ]
    assert result.provenance["replay_status"]["state"] == "complete"
    assert result.provenance["replay_status"]["rows_observed"] == 2


def test_csv_timeout_retains_a_safe_replay(tmp_path: Path) -> None:
    path = tmp_path / "timeout.csv"
    path.write_text("id\n1\n2\n")

    result = etl.infer_csv(
        path,
        limits=etl.InferenceLimits(timeout_seconds=1e-12),
    )

    assert result.provenance["limit_reason"] == "time"
    assert result.replay is not None
    assert list(result.replay.take()) == [{"id": 1}, {"id": 2}]


def test_csv_replay_keeps_relative_source_when_working_directory_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "relative.csv"
    path.write_text("id\n1\n2\n")
    other_directory = tmp_path / "other"
    other_directory.mkdir()

    monkeypatch.chdir(tmp_path)
    result = etl.infer_csv(
        Path("relative.csv"),
        limits=etl.InferenceLimits(max_rows=1),
    )
    assert result.replay is not None

    monkeypatch.chdir(other_directory)
    assert list(result.replay.take()) == [{"id": 1}, {"id": 2}]
    assert result.provenance["replay_status"]["state"] == "complete"


@pytest.mark.parametrize("change", ["delete", "modify"])
def test_csv_replay_reports_deleted_or_changed_source(
    tmp_path: Path, change: str
) -> None:
    path = tmp_path / "changing.csv"
    path.write_text("id\n1\n2\n")
    result = etl.infer_csv(path, limits=etl.InferenceLimits(max_rows=1))
    assert result.replay is not None

    if change == "delete":
        path.unlink()
    else:
        # A size change is observable even on filesystems with coarse timestamps.
        path.write_text("id\n1\n9\nextra\n")

    with pytest.raises(etl.InferenceReplayError) as error:
        list(result.replay.take())

    assert error.value.diagnostic.code == "INFER_CSV_REPLAY_SOURCE"
    assert result.provenance["replay_status"]["state"] == "failed"
    assert result.provenance["replay_status"]["diagnostic"]["code"] == (
        "INFER_CSV_REPLAY_SOURCE"
    )


def test_csv_replay_is_single_use_and_serialization_stays_row_free(
    tmp_path: Path,
) -> None:
    path = tmp_path / "single-use.csv"
    path.write_text("id,secret\n1,private\n2,hidden\n")
    result = etl.infer_csv(
        path,
        limits=etl.InferenceLimits(max_rows=1),
        retain_rows=True,
    )
    assert result.replay is not None

    assert list(result.replay.take()) == [
        {"id": 1, "secret": "private"},
        {"id": 2, "secret": "hidden"},
    ]
    with pytest.raises(RuntimeError, match="already been consumed"):
        result.replay.take()
    serialized = json.dumps(result.to_dict())
    assert "private" not in serialized
    assert "hidden" not in serialized


def test_invalid_csv_encoding_and_parser_options_are_diagnosed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid-options.csv"
    path.write_text("id\n1\n")

    bad_encoding = etl.infer_csv(path, options={"encoding": "not-a-real-codec"})
    bad_delimiter = etl.infer_csv(path, options={"delimiter": "||"})

    assert "INFER_CSV_OPTIONS" in {item.code for item in bad_encoding.diagnostics}
    assert "INFER_CSV_OPTIONS" in {item.code for item in bad_delimiter.diagnostics}
