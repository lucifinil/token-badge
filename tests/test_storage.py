from __future__ import annotations

import unittest

from token_badge.storage import get_tidb_dsn, parse_mysql_dsn


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


if __name__ == "__main__":
    unittest.main()

