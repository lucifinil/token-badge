from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol
from urllib.parse import unquote, urlparse

from token_badge.badges import badge_summary_from_record, render_badge_svg


ALLOWED_CHALLENGE_KEYS = {"collector_installation_id", "github_login", "github_node_id"}
ALLOWED_RAW_TOTAL_KEYS = {
    "cachedInputTokens",
    "cacheCreationTokens",
    "cacheReadTokens",
    "costUSD",
    "inputTokens",
    "outputTokens",
    "reasoningOutputTokens",
    "totalCost",
    "totalTokens",
}
ALLOWED_SNAPSHOT_KEYS = {
    "challenge_nonce",
    "collector_installation_id",
    "github_login",
    "github_node_id",
    "provider",
    "raw_totals",
    "report_hash",
    "source",
    "total_tokens",
    "trust_level",
    "usage_kind",
}
ALLOWED_TRUST_LEVELS = {"local-self-reported", "challenge-signed", "provider-verified"}
ALLOWED_PROVIDERS = {"codex", "claude"}


class Storage(Protocol):
    def create_challenge(self, challenge_nonce: str, request: dict[str, str | None]) -> None:
        ...

    def store_usage_snapshot(self, snapshot: dict[str, Any]) -> str:
        ...

    def get_badge_grant(self, github_login: str) -> dict[str, Any] | None:
        ...


@dataclass(frozen=True)
class APIResponse:
    status_code: int
    body: dict[str, Any] | str
    content_type: str = "application/json"


class APIError(ValueError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _reject_unknown_keys(payload: dict[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise APIError(400, f"unknown fields are not accepted: {', '.join(unknown)}")


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise APIError(400, f"{key} must be a non-empty string when provided")
    return value.strip()


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = _optional_str(payload, key)
    if value is None:
        raise APIError(400, f"{key} is required")
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise APIError(400, f"{key} must be a non-negative integer")
    return value


def validate_challenge_request(payload: dict[str, Any]) -> dict[str, str | None]:
    _reject_unknown_keys(payload, ALLOWED_CHALLENGE_KEYS)
    collector_installation_id = _required_str(payload, "collector_installation_id")
    return {
        "collector_installation_id": collector_installation_id,
        "github_login": _optional_str(payload, "github_login"),
        "github_node_id": _optional_str(payload, "github_node_id"),
    }


def validate_raw_totals(raw_totals: Any) -> dict[str, int | float]:
    if not isinstance(raw_totals, dict):
        raise APIError(400, "raw_totals must be a summary object")
    _reject_unknown_keys(raw_totals, ALLOWED_RAW_TOTAL_KEYS)

    clean: dict[str, int | float] = {}
    for key, value in raw_totals.items():
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise APIError(400, f"raw_totals.{key} must be numeric")
        clean[key] = value
    return clean


def validate_usage_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown_keys(payload, ALLOWED_SNAPSHOT_KEYS)

    provider = _required_str(payload, "provider")
    if provider not in ALLOWED_PROVIDERS:
        raise APIError(400, f"unsupported provider: {provider}")

    usage_kind = _required_str(payload, "usage_kind")
    if usage_kind != "subscription":
        raise APIError(400, "only subscription usage snapshots are accepted")

    trust_level = _required_str(payload, "trust_level")
    if trust_level not in ALLOWED_TRUST_LEVELS:
        raise APIError(400, f"unsupported trust_level: {trust_level}")

    report_hash = _required_str(payload, "report_hash")
    if not report_hash.startswith("sha256:"):
        raise APIError(400, "report_hash must be a sha256 hash")

    return {
        "challenge_nonce": _required_str(payload, "challenge_nonce"),
        "collector_installation_id": _required_str(payload, "collector_installation_id"),
        "github_login": _optional_str(payload, "github_login"),
        "github_node_id": _optional_str(payload, "github_node_id"),
        "provider": provider,
        "raw_totals": validate_raw_totals(payload.get("raw_totals")),
        "report_hash": report_hash,
        "source": _required_str(payload, "source"),
        "total_tokens": _required_int(payload, "total_tokens"),
        "trust_level": trust_level,
        "usage_kind": usage_kind,
    }


class TokenBadgeAPI:
    def __init__(self, storage: Storage):
        self.storage = storage

    def handle(self, method: str, path: str, payload: dict[str, Any] | None = None) -> APIResponse:
        try:
            clean_path = urlparse(path).path
            if method == "GET" and clean_path == "/healthz":
                return APIResponse(200, {"ok": True})
            if method == "GET" and clean_path.startswith("/v1/badges/"):
                return self._get_badge(clean_path)
            if method == "POST" and clean_path == "/v1/challenges":
                return self._create_challenge(payload or {})
            if method == "POST" and clean_path == "/v1/usage-snapshots":
                return self._store_usage_snapshot(payload or {})
            return APIResponse(404, {"error": "not_found"})
        except APIError as exc:
            return APIResponse(exc.status_code, {"error": exc.message})
        except RuntimeError as exc:
            return APIResponse(503, {"error": "storage_unavailable", "detail": str(exc)})

    def _create_challenge(self, payload: dict[str, Any]) -> APIResponse:
        request = validate_challenge_request(payload)
        challenge_nonce = secrets.token_urlsafe(32)
        self.storage.create_challenge(challenge_nonce, request)
        return APIResponse(
            201,
            {
                "challenge_nonce": challenge_nonce,
                "collector_installation_id": request["collector_installation_id"],
            },
        )

    def _store_usage_snapshot(self, payload: dict[str, Any]) -> APIResponse:
        snapshot = validate_usage_snapshot(payload)
        snapshot_id = self.storage.store_usage_snapshot(snapshot)
        return APIResponse(201, {"snapshot_id": snapshot_id, "status": "accepted"})

    def _get_badge(self, path: str) -> APIResponse:
        github_login = unquote(path.removeprefix("/v1/badges/"))
        wants_svg = github_login.endswith(".svg")
        if wants_svg:
            github_login = github_login.removesuffix(".svg")
        if not github_login:
            return APIResponse(400, {"error": "github_login is required"})

        summary = badge_summary_from_record(self.storage.get_badge_grant(github_login))
        if wants_svg:
            return APIResponse(200, render_badge_svg(summary), content_type="image/svg+xml")
        return APIResponse(200, summary)


def run_http_server(api: TokenBadgeAPI, *, host: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._send(api.handle("GET", self.path))

        def do_POST(self) -> None:
            try:
                response = api.handle("POST", self.path, self._read_json())
            except APIError as exc:
                response = APIResponse(exc.status_code, {"error": exc.message})
            self._send(response)

        def _read_json(self) -> dict[str, Any]:
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

    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.serve_forever()
