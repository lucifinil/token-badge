from __future__ import annotations

import unittest

from token_badge.dependencies import (
    CCUSAGE_INSTALL_COMMAND,
    check_ccusage,
    check_ccusage_codex_support,
    collect_dependency_checks,
    required_checks_pass,
)


def missing(_: str) -> None:
    return None


class DependencyCheckTest(unittest.TestCase):
    def test_missing_ccusage_has_install_guidance(self) -> None:
        check = check_ccusage(missing)

        self.assertEqual(check.status, "error")
        self.assertTrue(check.required)
        self.assertIn("npm install -g ccusage", check.remediation)

    def test_missing_ccusage_blocks_codex_support_check(self) -> None:
        check = check_ccusage_codex_support(missing)

        self.assertEqual(check.status, "error")
        self.assertIn("ccusage is missing", check.detail)
        self.assertIn(CCUSAGE_INSTALL_COMMAND, check.remediation)

    def test_required_checks_fail_when_required_tool_is_missing(self) -> None:
        checks = collect_dependency_checks(missing)

        self.assertFalse(required_checks_pass(checks))


if __name__ == "__main__":
    unittest.main()

