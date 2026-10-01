#!/usr/bin/env python3
"""Consume generated ETLantic definitions through the public managed HTTP API.

The consumer owns business approval and post-acceptance orchestration. It does
not import ETLantic or implement transformations; the generated definition is
registered, validated, planned, reviewed, then submitted at its exact immutable
revision.

The input JSON shape is documented in ``examples/README.md``. The default
principal header is for local demonstrations; production callers should use
the authentication configured by their control-plane deployment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen


class ManagedCommands(Protocol):
    """Small transport contract implemented by the HTTP adapter below."""

    def register(
        self, definition_id: str, document: Mapping[str, Any]
    ) -> dict[str, Any]: ...

    def validate(self, definition_id: str, revision_id: str) -> dict[str, Any]: ...

    def plan(
        self, definition_id: str, revision_id: str, request: Mapping[str, Any]
    ) -> dict[str, Any]: ...

    def submit(
        self,
        definition_id: str,
        revision_id: str,
        idempotency_key: str,
        request: Mapping[str, Any],
    ) -> dict[str, Any]: ...


Review = Callable[[Mapping[str, Any]], bool]
BusinessOrchestrator = Callable[[Mapping[str, Any], Mapping[str, Any]], None]
RevisionCheckpoint = Callable[[str], None]


class HttpManagedCommands:
    """HTTP transport for the public CP1 definition and run commands."""

    def __init__(
        self,
        base_url: str,
        *,
        principal: str,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Principal": principal,
        }

    def register(
        self, definition_id: str, document: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self._json(
            "PUT",
            f"/v1/definitions/{quote(definition_id, safe='')}",
            {"document": dict(document)},
        )

    def validate(self, definition_id: str, revision_id: str) -> dict[str, Any]:
        selector = urlencode({"revision_selector": revision_id})
        return self._json(
            "POST",
            f"/v1/definitions/{quote(definition_id, safe='')}/validate?{selector}",
        )

    def plan(
        self, definition_id: str, revision_id: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self._json(
            "POST",
            f"/v1/definitions/{quote(definition_id, safe='')}/plan",
            {"revision_selector": revision_id, "request": dict(request)},
        )

    def submit(
        self,
        definition_id: str,
        revision_id: str,
        idempotency_key: str,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._json(
            "POST",
            f"/v1/definitions/{quote(definition_id, safe='')}/runs",
            {
                "payload": {
                    "revision_selector": revision_id,
                    "request": dict(request),
                }
            },
            extra_headers={"Idempotency-Key": idempotency_key},
        )

    def _json(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
        *,
        extra_headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        data = (
            json.dumps(dict(body), separators=(",", ":")).encode("utf-8")
            if body is not None
            else None
        )
        request = Request(
            self.base_url + path,
            data=data,
            headers={**self.headers, **(extra_headers or {})},
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ETLantic returned HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"Could not reach the ETLantic service: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("ETLantic returned a non-object JSON response")
        return cast(dict[str, Any], payload)


def consume_generated_spec(
    spec: Mapping[str, Any],
    commands: ManagedCommands,
    *,
    review: Review | None = None,
    orchestrate_business: BusinessOrchestrator | None = None,
    checkpoint_revision: RevisionCheckpoint | None = None,
) -> dict[str, Any]:
    """Register, review and submit a generated definition without ETL logic.

    ``checkpoint_revision`` persists the exact write result before the review
    callback or run submission, making a caller retry reuse the same intent.
    Callers that already have a ``spec.revision_id`` can omit that callback.
    """
    definition_id = _required_text(spec, "definition_id")
    idempotency_key = _required_text(spec, "idempotency_key")
    document = spec.get("document")
    pinned_revision = spec.get("revision_id")
    request = spec.get("request", {})
    business_context = spec.get("business_context", {})
    if not isinstance(request, Mapping):
        raise ValueError("spec.request must be a JSON object")
    if not isinstance(business_context, Mapping):
        raise ValueError("spec.business_context must be a JSON object")
    request = cast(Mapping[str, Any], request)
    business_context = cast(Mapping[str, Any], business_context)

    if pinned_revision is not None:
        if not isinstance(pinned_revision, str) or not pinned_revision.strip():
            raise ValueError("spec.revision_id must be a non-empty string")
        revision_id = pinned_revision
    else:
        if not isinstance(document, Mapping):
            raise ValueError("spec.document must be a JSON object before registration")
        document = cast(Mapping[str, Any], document)
        if checkpoint_revision is None:
            raise ValueError(
                "checkpoint_revision is required so retries reuse the registered revision"
            )
        registration = commands.register(definition_id, document)
        revision_id = registration.get("revision_id")
        if not isinstance(revision_id, str) or not revision_id:
            raise RuntimeError(
                "The managed service did not return the immutable definition revision; "
                "this consumer requires a revision-aware managed backend"
            )
        checkpoint_revision(revision_id)

    validation = commands.validate(definition_id, revision_id)
    if validation.get("revision_id") != revision_id:
        raise RuntimeError("Validation did not use the pinned immutable revision")
    if validation.get("ok") is not True:
        raise ValueError(
            "Generated definition failed validation: "
            + json.dumps(validation.get("diagnostics", []), sort_keys=True)
        )
    plan_result = commands.plan(definition_id, revision_id, request)
    if plan_result.get("revision_id") != revision_id:
        raise RuntimeError("Planning did not use the pinned immutable revision")
    if plan_result.get("ok") is not True or not isinstance(
        plan_result.get("plan"), Mapping
    ):
        raise ValueError("ETLantic did not return a valid execution plan")

    plan = cast(Mapping[str, Any], plan_result["plan"])
    review_context: dict[str, Any] = {
        "definition_id": definition_id,
        "revision_id": revision_id,
        "validation": validation,
        "plan": plan,
        "business_context": dict(business_context),
    }
    if review is not None and not review(review_context):
        raise RuntimeError("External review did not approve this run")

    receipt = commands.submit(
        definition_id,
        revision_id,
        idempotency_key,
        request,
    )
    if orchestrate_business is not None:
        orchestrate_business(receipt, business_context)
    return receipt


def _required_text(spec: Mapping[str, Any], field: str) -> str:
    value = spec.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"spec.{field} must be a non-empty string")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="Generated consumer-spec JSON")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--principal", default="alice")
    parser.add_argument(
        "--require-review",
        action="store_true",
        help="Prompt for a human decision before submitting the pinned plan",
    )
    parser.add_argument(
        "--business-webhook",
        help="Optional HTTPS endpoint for a post-acceptance business event",
    )
    args = parser.parse_args()

    try:
        loaded_spec = json.loads(args.spec.read_text(encoding="utf-8"))
        if not isinstance(loaded_spec, dict):
            raise ValueError("consumer spec must be a JSON object")
        spec = cast(dict[str, Any], loaded_spec)
        definition_file = spec.get("definition_file")
        if (
            "revision_id" not in spec
            and "document" not in spec
            and isinstance(definition_file, str)
        ):
            definition_path = (args.spec.parent / definition_file).resolve()
            document = json.loads(definition_path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise ValueError("definition file must contain a JSON object")
            spec["document"] = cast(dict[str, Any], document)
        commands = HttpManagedCommands(
            args.base_url,
            principal=args.principal,
        )

        def review(context: Mapping[str, Any]) -> bool:
            print(
                "Review plan for "
                f"{context['definition_id']} at {context['revision_id']} "
                "([y]es/[n]o): ",
                end="",
                flush=True,
            )
            return sys.stdin.readline().strip().lower() in {"y", "yes"}

        def orchestrate(
            receipt: Mapping[str, Any], business_context: Mapping[str, Any]
        ) -> None:
            event = {
                "event_id": receipt.get("submission_id")
                or receipt.get("acceptance_id")
                or spec["idempotency_key"],
                "business_event": "etlantic.run.accepted",
                "receipt": dict(receipt),
                "business_context": dict(business_context),
            }
            if args.business_webhook:
                _deliver_business_event(
                    args.business_webhook,
                    event,
                    bearer_token=os.environ.get("ETLANTIC_BUSINESS_WEBHOOK_TOKEN"),
                )
            else:
                print(json.dumps(event, indent=2, sort_keys=True), flush=True)

        def checkpoint_revision(revision_id: str) -> None:
            spec["revision_id"] = revision_id
            args.spec.write_text(
                json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

        receipt = consume_generated_spec(
            spec,
            commands,
            review=review if args.require_review else None,
            orchestrate_business=orchestrate,
            checkpoint_revision=checkpoint_revision,
        )
        if not args.require_review:
            print(json.dumps(receipt, indent=2, sort_keys=True))
    except (OSError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _deliver_business_event(
    endpoint: str,
    event: Mapping[str, Any],
    *,
    bearer_token: str | None,
) -> None:
    """Post one accepted-run event without logging webhook credentials."""
    parsed = urlsplit(endpoint)
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("business webhook must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("business webhook URL must not embed credentials")
    if parsed.scheme != "https" and parsed.hostname not in local_hosts:
        raise ValueError("business webhook must use HTTPS outside loopback")
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("accepted receipt did not provide a stable event id")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": event_id,
    }
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = Request(
        endpoint,
        data=json.dumps(dict(event), separators=(",", ":")).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("Post-acceptance business webhook delivery failed") from exc


if __name__ == "__main__":
    raise SystemExit(main())
