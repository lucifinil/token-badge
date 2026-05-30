from __future__ import annotations

import json
import os
import uuid
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urlparse


DATABASE_ENV_NAMES = ("TiDB_DSN", "TiDB_DNS")

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS usage_challenges (
        challenge_nonce VARCHAR(128) PRIMARY KEY,
        collector_installation_id VARCHAR(128) NOT NULL,
        github_login VARCHAR(255) NULL,
        github_node_id VARCHAR(255) NULL,
        created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        used_at TIMESTAMP(6) NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usage_snapshots (
        id CHAR(36) PRIMARY KEY,
        provider VARCHAR(64) NOT NULL,
        usage_kind VARCHAR(64) NOT NULL,
        total_tokens BIGINT UNSIGNED NOT NULL,
        trust_level VARCHAR(64) NOT NULL,
        github_login VARCHAR(255) NULL,
        github_node_id VARCHAR(255) NULL,
        collector_installation_id VARCHAR(128) NOT NULL,
        challenge_nonce VARCHAR(128) NOT NULL,
        report_hash VARCHAR(128) NOT NULL,
        source VARCHAR(255) NOT NULL,
        raw_totals_json JSON NOT NULL,
        received_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        UNIQUE KEY uniq_usage_snapshots_report_hash (report_hash),
        KEY idx_usage_snapshots_github_login (github_login),
        KEY idx_usage_snapshots_collector (collector_installation_id)
    )
    """,
)


class StorageConfigurationError(RuntimeError):
    """Raised when TiDB storage is not configured correctly."""


class StorageError(RuntimeError):
    """Raised when a storage operation fails."""


def get_tidb_dsn(env: Mapping[str, str] = os.environ) -> str | None:
    for name in DATABASE_ENV_NAMES:
        value = env.get(name)
        if value:
            return value
    return None


def parse_mysql_dsn(dsn: str) -> dict[str, Any]:
    parsed = urlparse(dsn)
    if parsed.scheme not in {"mysql", "mysql+pymysql", "tidb"}:
        raise StorageConfigurationError("TiDB DSN must use mysql://, mysql+pymysql://, or tidb://")
    if not parsed.hostname or not parsed.username:
        raise StorageConfigurationError("TiDB DSN must include host and username")

    query = parse_qs(parsed.query)
    database = parsed.path.lstrip("/") or None
    config: dict[str, Any] = {
        "host": parsed.hostname,
        "port": parsed.port or 4000,
        "user": unquote(parsed.username),
        "password": unquote(parsed.password or ""),
        "database": database,
        "charset": "utf8mb4",
        "autocommit": True,
    }

    if query.get("ssl") == ["true"] or query.get("ssl_ca"):
        ssl_config: dict[str, str] = {}
        if query.get("ssl_ca"):
            ssl_config["ca"] = query["ssl_ca"][0]
        config["ssl"] = ssl_config

    return config


class TiDBStorage:
    def __init__(self, dsn: str):
        self.dsn = dsn

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "TiDBStorage":
        dsn = get_tidb_dsn(env)
        if not dsn:
            names = " or ".join(DATABASE_ENV_NAMES)
            raise StorageConfigurationError(f"missing {names}")
        return cls(dsn)

    def initialize_schema(self) -> None:
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    for statement in SCHEMA_STATEMENTS:
                        cursor.execute(statement)
        except StorageConfigurationError:
            raise
        except Exception as exc:
            raise StorageError("failed to initialize TiDB schema") from exc

    def create_challenge(self, challenge_nonce: str, request: dict[str, str | None]) -> None:
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO usage_challenges (
                            challenge_nonce,
                            collector_installation_id,
                            github_login,
                            github_node_id
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            challenge_nonce,
                            request["collector_installation_id"],
                            request.get("github_login"),
                            request.get("github_node_id"),
                        ),
                    )
        except StorageConfigurationError:
            raise
        except Exception as exc:
            raise StorageError("failed to create usage challenge") from exc

    def store_usage_snapshot(self, snapshot: dict[str, Any]) -> str:
        snapshot_id = str(uuid.uuid4())
        raw_totals_json = json.dumps(snapshot["raw_totals"], sort_keys=True, separators=(",", ":"))

        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT challenge_nonce FROM usage_challenges WHERE challenge_nonce = %s",
                        (snapshot["challenge_nonce"],),
                    )
                    if cursor.fetchone() is None:
                        raise StorageError("challenge_nonce was not issued by this backend")

                    cursor.execute(
                        """
                        INSERT INTO usage_snapshots (
                            id,
                            provider,
                            usage_kind,
                            total_tokens,
                            trust_level,
                            github_login,
                            github_node_id,
                            collector_installation_id,
                            challenge_nonce,
                            report_hash,
                            source,
                            raw_totals_json
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            snapshot_id,
                            snapshot["provider"],
                            snapshot["usage_kind"],
                            snapshot["total_tokens"],
                            snapshot["trust_level"],
                            snapshot.get("github_login"),
                            snapshot.get("github_node_id"),
                            snapshot["collector_installation_id"],
                            snapshot["challenge_nonce"],
                            snapshot["report_hash"],
                            snapshot["source"],
                            raw_totals_json,
                        ),
                    )
                    cursor.execute(
                        """
                        UPDATE usage_challenges
                        SET used_at = COALESCE(used_at, CURRENT_TIMESTAMP(6))
                        WHERE challenge_nonce = %s
                        """,
                        (snapshot["challenge_nonce"],),
                    )
        except (StorageConfigurationError, StorageError):
            raise
        except Exception as exc:
            raise StorageError("failed to store usage snapshot") from exc
        return snapshot_id

    def _connect(self) -> Any:
        try:
            import pymysql
        except ImportError as exc:
            raise StorageConfigurationError("install PyMySQL to use TiDB storage") from exc

        return pymysql.connect(**parse_mysql_dsn(self.dsn))
