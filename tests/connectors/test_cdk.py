"""CDK helper unit tests."""

from __future__ import annotations

import anyio
import pytest

from etlantic.connectors.cdk import (
    BatchBudget,
    BatchCeilings,
    RedactedRuntimeContext,
    RetryPolicy,
    compute_backoff,
    couple_proposal_to_receipt,
    emit_connector_event,
    is_retryable_error,
    is_secret_like_key,
    may_advance_cursor,
    reject_secret_like_keys,
    require_committed,
    retry_async,
    run_sync_in_worker,
    validate_config,
)
from etlantic.connectors.errors import (
    ConnectorConfigError,
    ConnectorError,
    ConnectorWriteError,
)
from etlantic.connectors.models import CommitReceipt, CursorProposal
from etlantic.secrets import SecretRef


def test_validate_config_accepts_and_rejects() -> None:
    schema = {
        "type": "object",
        "required": ["root", "mode"],
        "additionalProperties": False,
        "properties": {
            "root": {"type": "string", "minLength": 1},
            "mode": {"type": "string", "enum": ["snapshot", "incremental"]},
            "max_files": {"type": "integer", "minimum": 1},
        },
    }
    out = validate_config(
        {"root": "inbox", "mode": "snapshot", "max_files": 10},
        schema,
        provider="local-files",
    )
    assert out["root"] == "inbox"
    with pytest.raises(ConnectorConfigError, match="secret-like"):
        validate_config({"root": "x", "mode": "snapshot", "password": "x"}, schema)
    with pytest.raises(ConnectorConfigError, match="unexpected key"):
        validate_config({"root": "x", "mode": "snapshot", "extra": 1}, schema)
    with pytest.raises(ConnectorConfigError, match="missing required"):
        validate_config({"root": "x"}, schema)


def test_is_secret_like_key_and_reject_nested() -> None:
    assert is_secret_like_key("api_token")
    assert not is_secret_like_key("root_ref")
    with pytest.raises(ConnectorConfigError, match="userinfo"):
        reject_secret_like_keys({"url": "postgres://user:pass@host/db"})


def test_redacted_runtime_context_safe_repr() -> None:
    ref = SecretRef(provider="env", name="DB", key="password")
    ctx = RedactedRuntimeContext(
        values={"safe_io": "policy"},
        secret_refs={"db": ref},
        run_id="r1",
    )
    text = repr(ctx)
    assert "secret_ref_names" in text
    assert "password" not in text or "DB" in text
    assert "SecretRef" not in text or "db" in text
    assert "r1" in text
    public = ctx.to_public_dict()
    assert public["secret_refs"]["db"]["name"] == "DB"
    with pytest.raises(ConnectorConfigError):
        RedactedRuntimeContext(values={"password": "leak"})


def test_retry_async_bounded() -> None:
    attempts = {"n": 0}

    async def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectorError(
                "throttle",
                code="PMCONN_THROTTLE",
                details={"retry_after": 0.0},
            )
        return "ok"

    async def _run() -> str:
        return await retry_async(
            flaky,
            policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.0, jitter=0.0),
        )

    result = anyio.run(_run)
    assert result == "ok"
    assert attempts["n"] == 3
    assert is_retryable_error(ConnectorError("x", code="PMCONN_THROTTLE"))
    assert compute_backoff(0, RetryPolicy(jitter=0.0)) == 0.05


def test_run_sync_in_worker() -> None:
    def add(a: int, b: int) -> int:
        return a + b

    async def _run() -> int:
        return await run_sync_in_worker(add, 2, 3)

    assert anyio.run(_run) == 5


def test_batch_ceilings() -> None:
    budget = BatchBudget(BatchCeilings(max_pages=2, max_items=5, max_bytes=100))
    budget.consume_page(item_count=2, byte_count=10)
    with pytest.raises(Exception, match=r"item ceiling|page ceiling"):
        budget.consume_page(item_count=4, byte_count=1)


def test_publication_coupling() -> None:
    proposal = CursorProposal(subject_id="landing", candidate="abc")
    committed = CommitReceipt(status="committed", publication_id="pub-1")
    decision = couple_proposal_to_receipt(proposal, committed)
    assert decision.may_advance
    assert may_advance_cursor(committed, proposal=proposal).may_advance
    with pytest.raises(ConnectorWriteError):
        require_committed(CommitReceipt(status="rolled_back"))
    unknown = may_advance_cursor(CommitReceipt(status="unknown"))
    assert not unknown.may_advance


def test_emit_connector_event_bounds_and_redacts() -> None:
    event = emit_connector_event(
        "read.completed",
        provider="local-files",
        run_id="r1",
        metadata={"file_count": 2, "password": "nope", "rows": ["a" * 1000]},
        max_bytes=2048,
    )
    assert event["schema"] == "etlantic.connector_event/1"
    assert event["metadata"]["password"] == "***"
    assert "nope" not in str(event)
