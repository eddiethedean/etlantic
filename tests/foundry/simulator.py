"""A Semblance-backed, loopback Foundry API for connector tests.

JSON file-list responses are generated and validated by Semblance. FastAPI
routes model Foundry's binary file operations and the stateful transaction API.
The simulator never contacts a Foundry deployment.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import unquote

import uvicorn
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, create_model
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

from fastapi import FastAPI, Request

FOUNDRY_TOKEN = "foundry-simulator-token"
FOUNDRY_DATASET = "ri.foundry.main.dataset.test"
PINNED_TRANSACTION = "ri.foundry.main.transaction.pinned"
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_semblance = import_module("semblance")
SemblanceAPI = _semblance.SemblanceAPI
register_link = _semblance.register_link


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class SimulatedFile:
    content: bytes
    branch_name: str
    transaction_rid: str


class _FileListQuery(BaseModel):
    dataset_rid: str = ""
    branchName: str = "main"
    endTransactionRid: str | None = None
    pathPrefix: str | None = None
    pageToken: str | None = None
    pageSize: int = 200


class _CreateTransaction(BaseModel):
    transactionType: Literal["APPEND", "UPDATE", "SNAPSHOT"]


class _TransactionView(BaseModel):
    rid: str
    status: str


class _UploadView(BaseModel):
    path: str
    sizeBytes: str
    transactionRid: str


class _BearerTokenMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, *, token: str) -> None:
        super().__init__(app)
        self.token = token

    async def dispatch(
        self, request: StarletteRequest, call_next: Any
    ) -> StarletteResponse:
        if request.url.path in {"/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)
        if request.headers.get("authorization") != f"Bearer {self.token}":
            unauthorized = _load_fixture("foundry_error_unauthorized.json")
            return JSONResponse(
                unauthorized["body"],
                status_code=int(unauthorized["status_code"]),
            )
        return await call_next(request)


class FromFoundryFileList:
    """Resolve a Semblance response field from the simulator's scoped catalog."""

    def __init__(self, simulator: FoundrySimulator, field: str) -> None:
        self.simulator = simulator
        self.field = field

    def resolve(self, input_data: dict[str, Any], rng: Any) -> object:
        del rng
        if self.field == "data":
            self.simulator.record_file_query(input_data)
        return self.simulator.resolve_file_list(input_data)[self.field]


register_link(FromFoundryFileList)


class FoundrySimulator:
    """A local Foundry-shaped API with seeded files and transaction state."""

    def __init__(self, *, token: str = FOUNDRY_TOKEN, page_size: int = 1) -> None:
        self.token = token
        self.page_size = page_size
        self.base_url = ""
        self.files = self._load_seed_files()
        self.transactions: dict[str, str] = {
            item["rid"]: item["status"]
            for item in _load_fixture("foundry_transactions.json")["transactions"]
        }
        self.pending_files: dict[str, dict[str, tuple[str, bytes]]] = {}
        self.list_queries: list[dict[str, Any]] = []
        self.downloaded_paths: list[str] = []
        self.uploaded_files: list[tuple[str, bytes]] = []
        self.created_transaction_types: list[str] = []
        self.last_upload_branch = ""
        self.last_download_branch = ""
        self.drop_create_ack = False
        self.drop_commit_ack = False
        self._transaction_sequence = 0
        self.api = self._build_api()
        self.app = self._add_foundry_routes(self.api.as_fastapi())

    @staticmethod
    def _load_seed_files() -> dict[str, SimulatedFile]:
        catalog = _load_fixture("foundry_file_catalog.json")
        return {
            item["path"]: SimulatedFile(
                (_FIXTURES / item["content_fixture"]).read_bytes(),
                item["branch_name"],
                item["transaction_rid"],
            )
            for item in catalog["files"]
        }

    def _build_api(self) -> SemblanceAPI:
        api = SemblanceAPI(seed=42, validate_responses=True)
        api.add_middleware(_BearerTokenMiddleware, token=self.token)

        file_list_response = create_model(
            "FileListResponse",
            data=(
                Annotated[list[dict[str, Any]], FromFoundryFileList(self, "data")],
                ...,
            ),
            nextPageToken=(
                Annotated[str, FromFoundryFileList(self, "nextPageToken")],
                "",
            ),
        )

        api.get(
            "/api/v2/datasets/{dataset_rid}/files",
            input=_FileListQuery,
            output=file_list_response,
            summary="List dataset files",
            tags=["foundry"],
        )(lambda: None)

        return api

    def resolve_file_list(self, query: dict[str, Any]) -> dict[str, Any]:
        """Build one schema-validated page from the visible branch snapshot."""
        return self._file_list_response(query)

    def record_file_query(self, query: dict[str, Any]) -> None:
        self.list_queries.append(
            {
                "branchName": query.get("branchName"),
                "endTransactionRid": query.get("endTransactionRid"),
                "pathPrefix": query.get("pathPrefix"),
                "pageToken": query.get("pageToken"),
            }
        )

    def _file_list_response(self, query: dict[str, Any]) -> dict[str, Any]:
        transaction = query.get("endTransactionRid")
        branch = str(query.get("branchName") or "main")
        prefix = query.get("pathPrefix")
        candidates = [
            {
                "path": path,
                "sizeBytes": str(len(file.content)),
                "transactionRid": file.transaction_rid,
            }
            for path, file in sorted(self.files.items())
            if (
                file.transaction_rid == transaction
                if transaction
                else file.branch_name == branch
            )
            and (not prefix or path.startswith(str(prefix)))
        ]
        requested_page_size = query.get("pageSize", self.page_size)
        if isinstance(requested_page_size, bool) or not isinstance(
            requested_page_size, int
        ):
            requested_page_size = self.page_size
        page_size = max(1, min(self.page_size, requested_page_size))
        offset = page_size if query.get("pageToken") else 0
        page = candidates[offset : offset + page_size]
        return {
            "data": page,
            "nextPageToken": "page-2" if offset + page_size < len(candidates) else "",
        }

    def _add_foundry_routes(self, app: FastAPI) -> FastAPI:
        async def download_content(
            dataset_rid: str,
            file_path: str,
            endTransactionRid: str | None = None,
            branchName: str | None = None,
        ) -> Response:
            del dataset_rid
            path = unquote(file_path)
            self.downloaded_paths.append(path)
            self.last_download_branch = branchName or ""
            file = self.files.get(path)
            if file is None:
                return Response(status_code=404)
            if endTransactionRid and file.transaction_rid != endTransactionRid:
                return Response(status_code=404)
            if branchName and file.branch_name != branchName:
                return Response(status_code=404)
            return Response(content=file.content, media_type="application/octet-stream")

        app.add_api_route(
            "/api/v2/datasets/{dataset_rid}/files/{file_path:path}/content",
            download_content,
            methods=["GET"],
        )

        async def create_transaction(
            dataset_rid: str,
            body: _CreateTransaction,
            branchName: str = "main",
        ) -> _TransactionView | JSONResponse:
            del dataset_rid, branchName
            self._transaction_sequence += 1
            rid = f"ri.foundry.main.transaction.sim-{self._transaction_sequence}"
            self.transactions[rid] = "OPEN"
            self.pending_files[rid] = {}
            self.created_transaction_types.append(body.transactionType)
            if self.drop_create_ack:
                self.drop_create_ack = False
                await asyncio.sleep(1.2)
            return _TransactionView(rid=rid, status="OPEN")

        app.add_api_route(
            "/api/v2/datasets/{dataset_rid}/transactions",
            create_transaction,
            methods=["POST"],
            response_model=_TransactionView,
            status_code=201,
        )

        async def upload_file(
            request: Request,
            dataset_rid: str,
            file_path: str,
            transactionRid: str,
            branchName: str = "main",
        ) -> _UploadView | JSONResponse:
            del dataset_rid
            if self.transactions.get(transactionRid) != "OPEN":
                return JSONResponse({"errorCode": "CONFLICT"}, status_code=409)
            path = unquote(file_path)
            content = await request.body()
            self.last_upload_branch = branchName
            self.uploaded_files.append((path, content))
            self.pending_files[transactionRid][path] = (branchName, content)
            return _UploadView(
                path=path,
                sizeBytes=str(len(content)),
                transactionRid=transactionRid,
            )

        app.add_api_route(
            "/api/v2/datasets/{dataset_rid}/files/{file_path:path}/upload",
            upload_file,
            methods=["POST"],
            response_model=_UploadView,
        )

        async def commit_transaction(
            dataset_rid: str, transaction_rid: str
        ) -> _TransactionView | JSONResponse:
            del dataset_rid
            if self.transactions.get(transaction_rid) != "OPEN":
                return JSONResponse({"errorCode": "CONFLICT"}, status_code=409)
            self.transactions[transaction_rid] = "COMMITTED"
            for path, (branch, content) in self.pending_files.pop(
                transaction_rid, {}
            ).items():
                self.files[path] = SimulatedFile(content, branch, transaction_rid)
            if self.drop_commit_ack:
                self.drop_commit_ack = False
                return JSONResponse(
                    {"errorCode": "ACKNOWLEDGEMENT_LOST"}, status_code=503
                )
            return _TransactionView(rid=transaction_rid, status="COMMITTED")

        app.add_api_route(
            "/api/v2/datasets/{dataset_rid}/transactions/{transaction_rid}/commit",
            commit_transaction,
            methods=["POST"],
            response_model=_TransactionView,
        )

        async def abort_transaction(
            dataset_rid: str, transaction_rid: str
        ) -> _TransactionView | JSONResponse:
            del dataset_rid
            if self.transactions.get(transaction_rid) != "OPEN":
                return JSONResponse({"errorCode": "CONFLICT"}, status_code=409)
            self.transactions[transaction_rid] = "ABORTED"
            self.pending_files.pop(transaction_rid, None)
            return _TransactionView(rid=transaction_rid, status="ABORTED")

        app.add_api_route(
            "/api/v2/datasets/{dataset_rid}/transactions/{transaction_rid}/abort",
            abort_transaction,
            methods=["POST"],
            response_model=_TransactionView,
        )

        async def get_transaction(
            dataset_rid: str, transaction_rid: str
        ) -> _TransactionView | JSONResponse:
            del dataset_rid
            status = self.transactions.get(transaction_rid)
            if status is None:
                return JSONResponse({"errorCode": "NOT_FOUND"}, status_code=404)
            return _TransactionView(rid=transaction_rid, status=status)

        app.add_api_route(
            "/api/v2/datasets/{dataset_rid}/transactions/{transaction_rid}",
            get_transaction,
            methods=["GET"],
            response_model=_TransactionView,
        )

        return app

    @contextmanager
    def serve(self) -> Generator[str, None, None]:
        """Serve the API on an ephemeral loopback port until the context exits."""
        server = uvicorn.Server(
            uvicorn.Config(self.app, host="127.0.0.1", port=0, log_level="error")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.monotonic() + 8
        while not server.started:
            if not thread.is_alive():
                raise RuntimeError("Foundry simulator exited before binding.")
            if time.monotonic() > deadline:
                raise RuntimeError("Foundry simulator failed to start.")
            time.sleep(0.01)
        try:
            _host, port = server.servers[0].sockets[0].getsockname()[:2]
            self.base_url = f"http://127.0.0.1:{port}"
            yield self.base_url
        finally:
            server.should_exit = True
            thread.join(timeout=5)
