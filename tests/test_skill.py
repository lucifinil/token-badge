from __future__ import annotations

import unittest
from pathlib import Path

from token_badge.api import TokenBadgeAPI
from token_badge.skill import SKILL_MARKDOWN

from tests.test_api import FakeStorage

REPO_SKILL = Path(__file__).resolve().parent.parent / "SKILL.md"


class SkillTest(unittest.TestCase):
    def test_repo_skill_matches_served_constant(self) -> None:
        self.assertEqual(
            REPO_SKILL.read_text(encoding="utf-8"),
            SKILL_MARKDOWN,
            "SKILL.md is out of sync; regenerate it from token_badge.skill.SKILL_MARKDOWN",
        )

    def test_skill_endpoint_serves_markdown(self) -> None:
        response = TokenBadgeAPI(FakeStorage()).handle("GET", "/SKILL.md")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith("text/markdown"))
        self.assertIn("Token Badge — Agent Setup Skill", response.body)

    def test_skill_names_exact_install_source_and_fallback(self) -> None:
        self.assertIn(
            "uvx --from git+https://github.com/lucifinil/token-badge token-badge --help",
            SKILL_MARKDOWN,
        )
        self.assertIn("repo-root `SKILL.md` as the canonical", SKILL_MARKDOWN)
        self.assertIn("not a Python package index or wheel URL", SKILL_MARKDOWN)


if __name__ == "__main__":
    unittest.main()
