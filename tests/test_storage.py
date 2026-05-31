from __future__ import annotations

import unittest

from token_badge.storage import challenge_matches_snapshot, get_tidb_dsn, parse_mysql_dsn


class StorageConfigTest(unittest.TestCase):
    def test_prefers_tidb_dsn(self) -> None:
        env = {"TiDB_DSN": "mysql://primary", "TiDB_DNS": "mysql://alias"}

        self.assertEqual(get_tidb_dsn(env), "mysql://primary")

    def test_accepts_tidb_dns_alias(self) -> None:
        env = {"TiDB_DNS": "mysql://alias"}

        self.assertEqual(get_tidb_dsn(env), "mysql://alias")

    def test_parse_mysql_dsn_defaults_tidb_port(self) -> None:
        config = parse_mysql_dsn("mysql://user:pass@example.com/token_badge")

        self.assertEqual(config["host"], "example.com")
        self.assertEqual(config["port"], 4000)
        self.assertEqual(config["user"], "user")
        self.assertEqual(config["password"], "pass")
        self.assertEqual(config["database"], "token_badge")

    def test_challenge_metadata_must_match_snapshot(self) -> None:
        challenge = {
            "collector_installation_id": "collector-1",
            "github_login": "octocat",
            "github_node_id": "U_123",
        }

        self.assertTrue(challenge_matches_snapshot(challenge, dict(challenge)))
        self.assertFalse(
            challenge_matches_snapshot(
                challenge,
                {
                    "collector_installation_id": "collector-1",
                    "github_login": "someone-else",
                    "github_node_id": "U_123",
                },
            )
        )


if __name__ == "__main__":
    unittest.main()
