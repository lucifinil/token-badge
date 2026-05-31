"""Vercel serverless entrypoint for the Token Badge API.

Vercel runs functions, not a persistent server, so this adapter wraps the existing
``TokenBadgeAPI`` dispatcher in a per-request ``BaseHTTPRequestHandler``. ``vercel.json``
rewrites every path to this function, and ``self.path`` preserves the original request
path so routing stays identical to the local ``serve`` command.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# The token_badge package ships under src/ (declared via vercel.json includeFiles).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from token_badge.api import APIError, APIResponse, TokenBadgeAPI  # noqa: E402
from token_badge.storage import TiDBStorage  # noqa: E402


class _LazyStorage:
    """Resolve TiDB config only when a DB-backed route runs, so /healthz and /SKILL.md
    stay reachable even if TiDB_DSN is not configured (handle() maps the resulting
    RuntimeError to a 503)."""

    def __init__(self) -> None:
        self._storage: TiDBStorage | None = None

    def _resolve(self) -> TiDBStorage:
        if self._storage is None:
            self._storage = TiDBStorage.from_env()
        return self._storage

    def create_challenge(self, *args: object, **kwargs: object):
        return self._resolve().create_challenge(*args, **kwargs)

    def store_usage_snapshot(self, *args: object, **kwargs: object):
        return self._resolve().store_usage_snapshot(*args, **kwargs)

    def get_badge_grant(self, *args: object, **kwargs: object):
        return self._resolve().get_badge_grant(*args, **kwargs)

    def get_consumption_ranking(self, *args: object, **kwargs: object):
        return self._resolve().get_consumption_ranking(*args, **kwargs)


_api = TokenBadgeAPI(_LazyStorage())


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        try:
            payload = self._read_json() if method == "POST" else None
            response = _api.handle(method, self.path, payload)
        except APIError as exc:
            response = APIResponse(exc.status_code, {"error": exc.message})
        self._send(response)

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length == 0:
            return {}
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise APIError(400, "request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise APIError(400, "request body must be a JSON object")
        return payload

    def _send(self, response: APIResponse) -> None:
        if response.content_type == "application/json":
            encoded = json.dumps(response.body, sort_keys=True).encode("utf-8")
        else:
            encoded = str(response.body).encode("utf-8")
        self.send_response(response.status_code)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args: object) -> None:  # keep Vercel logs quiet
        return
