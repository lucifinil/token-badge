from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


class UploadError(RuntimeError):
    """Raised when the collector cannot upload usage metadata."""


def post_json(base_url: str, path: str, payload: dict[str, Any], timeout_seconds: int = 30) -> dict[str, Any]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise UploadError(f"upload failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise UploadError(f"upload failed: {exc.reason}") from exc

    try:
        decoded = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise UploadError("upload endpoint returned non-JSON output") from exc
    if not isinstance(decoded, dict):
        raise UploadError("upload endpoint returned an unexpected JSON shape")
    return decoded


def request_challenge(
    base_url: str,
    *,
    collector_installation_id: str,
    github_login: str | None,
    github_node_id: str | None,
) -> dict[str, Any]:
    return post_json(
        base_url,
        "/v1/challenges",
        {
            "collector_installation_id": collector_installation_id,
            "github_login": github_login,
            "github_node_id": github_node_id,
        },
    )


def upload_usage_snapshot(base_url: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    return post_json(base_url, "/v1/usage-snapshots", snapshot)

