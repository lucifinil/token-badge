from __future__ import annotations

import base64
import json
import unittest
from typing import Sequence
from unittest.mock import ANY

from token_badge.github_profile import (
    END_MARKER,
    START_MARKER,
    GitHubConnectionError,
    GitHubProfileClient,
    GitHubProfileError,
    ProfileRepositoryNotFound,
    badge_block,
    badge_markdown,
    profile_visibility_for_badge,
    upsert_badge_block,
)


class FakeRunner:
    def __init__(self, responses: dict[tuple[str, ...], str | Exception] | list[tuple[tuple[str, ...], str | Exception]]):
        self.responses = list(responses.items()) if isinstance(responses, dict) else responses
        self.calls: list[tuple[str, ...]] = []

    def run(self, args: Sequence[str]) -> str:
        key = tuple(args)
        self.calls.append(key)
        found = False
        response: str | Exception = ""
        for expected, candidate in self.responses:
            if len(expected) == len(key) and all(left == right or left is ANY for left, right in zip(expected, key, strict=True)):
                response = candidate
                found = True
                break
        if not found:
            raise AssertionError(f"unexpected gh command: {key}")
        if isinstance(response, Exception):
            raise response
        return response


def json_response(payload: dict[str, object]) -> str:
    return json.dumps(payload)


def readme_response(content: str, sha: str = "sha-1") -> str:
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    return json_response({"content": encoded, "encoding": "base64", "sha": sha})


class GitHubProfileTest(unittest.TestCase):
    def test_badge_markdown_uses_dynamic_svg_endpoint(self) -> None:
        markdown = badge_markdown("octocat", "https://token.example.com/")

        self.assertEqual(
            markdown,
            "[![Token Badge](https://token.example.com/v1/badges/octocat.svg)]"
            "(https://token.example.com/u/octocat)",
        )

    def test_profile_visibility_detects_rendered_badge_url(self) -> None:
        visibility = profile_visibility_for_badge(
            "octocat",
            "https://token.example.com",
            fetch_url=lambda _url: '<img data-canonical-src="https://token.example.com/v1/badges/octocat.svg">',
        )

        self.assertTrue(visibility.visible)
        self.assertEqual(visibility.profile_url, "https://github.com/octocat")
        self.assertEqual(visibility.share_url, "https://github.com/octocat/octocat")

    def test_profile_visibility_reports_missing_badge(self) -> None:
        visibility = profile_visibility_for_badge(
            "octocat",
            "https://token.example.com",
            fetch_url=lambda _url: "<html></html>",
        )

        self.assertFalse(visibility.visible)

    def test_upsert_appends_block_when_missing(self) -> None:
        updated, changed = upsert_badge_block("# Octocat\n", badge_block("octocat", "https://token.example.com"))

        self.assertTrue(changed)
        self.assertIn(START_MARKER, updated)
        self.assertIn(END_MARKER, updated)
        self.assertTrue(updated.startswith("# Octocat\n\n"))

    def test_upsert_replaces_existing_block(self) -> None:
        old = "\n".join(
            [
                "# Octocat",
                "",
                START_MARKER,
                "old badge",
                END_MARKER,
                "",
                "More profile content",
            ]
        )
        block = badge_block("octocat", "https://token.example.com")

        updated, changed = upsert_badge_block(old, block)

        self.assertTrue(changed)
        self.assertIn(block, updated)
        self.assertIn("More profile content", updated)
        self.assertNotIn("old badge", updated)

    def test_upsert_rejects_partial_marker_block(self) -> None:
        with self.assertRaisesRegex(GitHubProfileError, "partial"):
            upsert_badge_block(f"# Octocat\n{START_MARKER}\n", "badge")

    def test_client_dry_run_uses_authenticated_login_and_does_not_commit(self) -> None:
        runner = FakeRunner(
            {
                ("api", "/user"): json_response({"login": "octocat"}),
                ("api", "/repos/octocat/octocat"): json_response({"default_branch": "main"}),
                ("api", "/repos/octocat/octocat/contents/README.md"): readme_response("# Octocat\n"),
            }
        )

        update = GitHubProfileClient(runner).install_badge(
            github_login=None,
            badge_base_url="https://token.example.com",
            dry_run=True,
            message="Add badge",
        )

        self.assertTrue(update.changed)
        self.assertTrue(update.dry_run)
        self.assertIn("/v1/badges/octocat.svg", update.content)
        self.assertIn("/u/octocat", update.content)
        self.assertIn("what this badge means", update.content)
        self.assertFalse(any("--method" in call for call in runner.calls))

    def test_client_commits_marker_update_to_profile_readme(self) -> None:
        runner = FakeRunner(
            [
                (("api", "/user"), json_response({"login": "octocat"})),
                (("api", "/repos/octocat/octocat"), json_response({"default_branch": "main"})),
                (("api", "/repos/octocat/octocat/contents/README.md"), readme_response("# Octocat\n", sha="sha-1")),
                (
                    (
                        "api",
                        "--method",
                        "PUT",
                        "/repos/octocat/octocat/contents/README.md",
                        "--raw-field",
                        "message=Add badge",
                        "--raw-field",
                        ANY,
                        "--raw-field",
                        "sha=sha-1",
                    ),
                    json_response({"commit": {"sha": "commit-1"}}),
                ),
            ]
        )

        update = GitHubProfileClient(runner).install_badge(
            github_login="octocat",
            badge_base_url="https://token.example.com",
            dry_run=False,
            message="Add badge",
        )

        self.assertEqual(update.commit_sha, "commit-1")
        put_calls = [call for call in runner.calls if "--method" in call]
        self.assertEqual(len(put_calls), 1)
        content_field = next(field for field in put_calls[0] if field.startswith("content="))
        decoded = base64.b64decode(content_field.removeprefix("content=")).decode("utf-8")
        self.assertIn("/v1/badges/octocat.svg", decoded)
        self.assertIn("/u/octocat", decoded)

    def test_client_creates_missing_profile_readme(self) -> None:
        runner = FakeRunner(
            [
                (("api", "/user"), json_response({"login": "octocat"})),
                (("api", "/repos/octocat/octocat"), json_response({"default_branch": "main"})),
                (
                    ("api", "/repos/octocat/octocat/contents/README.md"),
                    GitHubProfileError("HTTP 404 Not Found"),
                ),
                (
                    (
                        "api",
                        "--method",
                        "PUT",
                        "/repos/octocat/octocat/contents/README.md",
                        "--raw-field",
                        "message=Add badge",
                        "--raw-field",
                        ANY,
                    ),
                    json_response({"commit": {"sha": "commit-1"}}),
                ),
            ]
        )

        update = GitHubProfileClient(runner).install_badge(
            github_login="octocat",
            badge_base_url="https://token.example.com",
            dry_run=False,
            message="Add badge",
        )

        self.assertEqual(update.commit_sha, "commit-1")
        put_call = next(call for call in runner.calls if "--method" in call)
        self.assertFalse(any(field.startswith("sha=") for field in put_call))

    def test_client_creates_missing_profile_repository_when_allowed(self) -> None:
        runner = FakeRunner(
            [
                (("api", "/user"), json_response({"login": "octocat"})),
                (("api", "/repos/octocat/octocat"), GitHubProfileError("HTTP 404 Not Found")),
                (
                    ("api", "--method", "POST", "/user/repos", "--raw-field", ANY, "--field", ANY, "--field", ANY),
                    json_response({"default_branch": "main"}),
                ),
                (("api", "/repos/octocat/octocat/contents/README.md"), readme_response("# octocat\n", sha="sha-1")),
                (
                    (
                        "api",
                        "--method",
                        "PUT",
                        "/repos/octocat/octocat/contents/README.md",
                        "--raw-field",
                        "message=Add badge",
                        "--raw-field",
                        ANY,
                        "--raw-field",
                        "sha=sha-1",
                    ),
                    json_response({"commit": {"sha": "commit-1"}}),
                ),
            ]
        )

        update = GitHubProfileClient(runner).install_badge(
            github_login="octocat",
            badge_base_url="https://token.example.com",
            dry_run=False,
            message="Add badge",
            create_repo=True,
        )

        self.assertTrue(update.repo_created)
        self.assertEqual(update.commit_sha, "commit-1")
        self.assertTrue(any(call[:4] == ("api", "--method", "POST", "/user/repos") for call in runner.calls))
        create_call = next(call for call in runner.calls if call[:4] == ("api", "--method", "POST", "/user/repos"))
        self.assertFalse(any(str(field).startswith("description=") for field in create_call))

    def test_client_does_not_create_repository_without_opt_in(self) -> None:
        runner = FakeRunner(
            [
                (("api", "/user"), json_response({"login": "octocat"})),
                (("api", "/repos/octocat/octocat"), GitHubProfileError("HTTP 404 Not Found")),
            ]
        )

        with self.assertRaises(ProfileRepositoryNotFound):
            GitHubProfileClient(runner).install_badge(
                github_login="octocat",
                badge_base_url="https://token.example.com",
                dry_run=False,
                message="Add badge",
            )

    def test_client_refuses_to_update_a_different_github_login(self) -> None:
        runner = FakeRunner({("api", "/user"): json_response({"login": "octocat"})})

        with self.assertRaisesRegex(GitHubProfileError, "not someone-else"):
            GitHubProfileClient(runner).install_badge(
                github_login="someone-else",
                badge_base_url="https://token.example.com",
                dry_run=True,
                message="Add badge",
            )

    def test_client_reports_missing_local_connection(self) -> None:
        runner = FakeRunner({("api", "/user"): GitHubProfileError("authentication required")})

        with self.assertRaises(GitHubConnectionError):
            GitHubProfileClient(runner).authenticated_login()


if __name__ == "__main__":
    unittest.main()
