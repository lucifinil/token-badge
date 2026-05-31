from __future__ import annotations

import json
import os
import uuid
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urlparse

from token_badge.badges import badge_grant_from_snapshot, github_identity_key, should_replace_badge_grant

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
    CREATE TABLE IF NOT EXISTS badge_grants (
        identity_key VARCHAR(320) PRIMARY KEY,
        github_login VARCHAR(255) NULL,
        github_node_id VARCHAR(255) NULL,
        tier_name VARCHAR(128) NOT NULL,
        tier_threshold BIGINT UNSIGNED NOT NULL,
        winning_provider VARCHAR(64) NOT NULL,
        winning_snapshot_id CHAR(36) NOT NULL,
        winning_total_tokens BIGINT UNSIGNED NOT NULL,
        trust_level VARCHAR(64) NOT NULL,
        granted_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
        KEY idx_badge_grants_github_login (github_login),
        KEY idx_badge_grants_github_node_id (github_node_id)
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


def challenge_matches_snapshot(challenge: Mapping[str, Any], snapshot: Mapping[str, Any]) -> bool:
    return (
        challenge["collector_installation_id"] == snapshot["collector_installation_id"]
        and challenge.get("github_login") == snapshot.get("github_login")
        and challenge.get("github_node_id") == snapshot.get("github_node_id")
    )


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
                try:
                    connection.begin()
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            SELECT
                                collector_installation_id,
                                github_login,
                                github_node_id,
                                used_at
                            FROM usage_challenges
                            WHERE challenge_nonce = %s
                            FOR UPDATE
                            """,
                            (snapshot["challenge_nonce"],),
                        )
                        row = cursor.fetchone()
                        if row is None:
                            raise StorageError("challenge_nonce was not issued by this backend")

                        challenge = {
                            "collector_installation_id": row[0],
                            "github_login": row[1],
                            "github_node_id": row[2],
                            "used_at": row[3],
                        }
                        if challenge["used_at"] is not None:
                            raise StorageError("challenge_nonce was already used")
                        if not challenge_matches_snapshot(challenge, snapshot):
                            raise StorageError("challenge metadata does not match usage snapshot")

                        cursor.execute(
                            """
                            UPDATE usage_challenges
                            SET used_at = CURRENT_TIMESTAMP(6)
                            WHERE challenge_nonce = %s
                            """,
                            (snapshot["challenge_nonce"],),
                        )
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
                        self._upsert_badge_grant(cursor, snapshot, snapshot_id)
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        except (StorageConfigurationError, StorageError):
            raise
        except Exception as exc:
            raise StorageError("failed to store usage snapshot") from exc
        return snapshot_id

    def get_badge_grant(self, github_login: str) -> dict[str, Any] | None:
        identity_key = github_identity_key(github_login)
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            identity_key,
                            github_login,
                            github_node_id,
                            tier_name,
                            tier_threshold,
                            winning_provider,
                            winning_snapshot_id,
                            winning_total_tokens,
                            trust_level
                        FROM badge_grants
                        WHERE identity_key = %s
                        """,
                        (identity_key,),
                    )
                    row = cursor.fetchone()
        except StorageConfigurationError:
            raise
        except Exception as exc:
            raise StorageError("failed to read badge grant") from exc

        if row is None:
            return None
        keys = (
            "identity_key",
            "github_login",
            "github_node_id",
            "tier_name",
            "tier_threshold",
            "winning_provider",
            "winning_snapshot_id",
            "winning_total_tokens",
            "trust_level",
        )
        return dict(zip(keys, row, strict=True))

    def _upsert_badge_grant(self, cursor: Any, snapshot: dict[str, Any], snapshot_id: str) -> None:
        candidate = badge_grant_from_snapshot(snapshot, snapshot_id)
        if candidate is None:
            return

        cursor.execute(
            "SELECT winning_total_tokens FROM badge_grants WHERE identity_key = %s",
            (candidate.identity_key,),
        )
        row = cursor.fetchone()
        existing_total = None if row is None else int(row[0])
        if not should_replace_badge_grant(existing_total, candidate.winning_total_tokens):
            return

        record = candidate.to_record()
        if row is None:
            cursor.execute(
                """
                INSERT INTO badge_grants (
                    identity_key,
                    github_login,
                    github_node_id,
                    tier_name,
                    tier_threshold,
                    winning_provider,
                    winning_snapshot_id,
                    winning_total_tokens,
                    trust_level
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record["identity_key"],
                    record["github_login"],
                    record["github_node_id"],
                    record["tier_name"],
                    record["tier_threshold"],
                    record["winning_provider"],
                    record["winning_snapshot_id"],
                    record["winning_total_tokens"],
                    record["trust_level"],
                ),
            )
            return

        cursor.execute(
            """
            UPDATE badge_grants
            SET
                github_login = %s,
                github_node_id = %s,
                tier_name = %s,
                tier_threshold = %s,
                winning_provider = %s,
                winning_snapshot_id = %s,
                winning_total_tokens = %s,
                trust_level = %s
            WHERE identity_key = %s
            """,
            (
                record["github_login"],
                record["github_node_id"],
                record["tier_name"],
                record["tier_threshold"],
                record["winning_provider"],
                record["winning_snapshot_id"],
                record["winning_total_tokens"],
                record["trust_level"],
                record["identity_key"],
            ),
        )

    def _connect(self) -> Any:
        try:
            import pymysql
        except ImportError as exc:
            raise StorageConfigurationError("install PyMySQL to use TiDB storage") from exc

        return pymysql.connect(**parse_mysql_dsn(self.dsn))
