from __future__ import annotations

import base64
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Protocol, Sequence


START_MARKER = "<!-- token-badge:start -->"
END_MARKER = "<!-- token-badge:end -->"


class GitHubProfileError(RuntimeError):
    """Raised when a GitHub profile README cannot be updated."""


class GitHubConnectionError(GitHubProfileError):
    """Raised when no usable local GitHub connection is available."""


class CommandRunner(Protocol):
    def run(self, args: Sequence[str]) -> str:
        ...


@dataclass(frozen=True)
class ProfileRepository:
    owner: str
    name: str
    default_branch: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True)
class ReadmeFile:
    content: str
    sha: str | None


@dataclass(frozen=True)
class ProfileBadgeUpdate:
    github_login: str
    repository: str
    changed: bool
    dry_run: bool
    content: str
    commit_sha: str | None = None


class GhCliRunner:
    def run(self, args: Sequence[str]) -> str:
        command = ["gh", *args]
        try:
            completed = subprocess.run(command, capture_output=True, check=True, text=True)
        except FileNotFoundError as exc:
            raise GitHubConnectionError(
                "GitHub CLI is not installed. Install `gh` or connect GitHub through SSO/OAuth."
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise GitHubProfileError(f"`gh {' '.join(args)}` failed: {detail}") from exc
        return completed.stdout


def badge_markdown(github_login: str, badge_base_url: str) -> str:
    base_url = badge_base_url.rstrip("/")
    badge_url = f"{base_url}/v1/badges/{github_login}.svg"
    target_url = f"{base_url}/v1/badges/{github_login}"
    return f"[![Token Badge]({badge_url})]({target_url})"


def badge_block(github_login: str, badge_base_url: str) -> str:
    return "\n".join(
        [
            START_MARKER,
            badge_markdown(github_login, badge_base_url),
            END_MARKER,
        ]
    )


def upsert_badge_block(readme: str, block: str) -> tuple[str, bool]:
    has_start = START_MARKER in readme
    has_end = END_MARKER in readme
    if has_start != has_end:
        raise GitHubProfileError("README has a partial Token Badge marker block")

    if has_start:
        start = readme.index(START_MARKER)
        try:
            end = readme.index(END_MARKER, start) + len(END_MARKER)
        except ValueError as exc:
            raise GitHubProfileError("README has a malformed Token Badge marker block") from exc
        updated = f"{readme[:start]}{block}{readme[end:]}"
        return updated, updated != readme

    separator = "\n\n" if readme and not readme.endswith("\n\n") else ""
    updated = f"{readme}{separator}{block}\n"
    return updated, True


def _decode_readme_content(payload: dict[str, object]) -> ReadmeFile:
    content = payload.get("content")
    encoding = payload.get("encoding")
    sha = payload.get("sha")
    if not isinstance(content, str) or encoding != "base64":
        raise GitHubProfileError("GitHub README response did not contain base64 content")
    if not isinstance(sha, str):
        raise GitHubProfileError("GitHub README response did not contain a file sha")
    normalized = "".join(content.splitlines())
    return ReadmeFile(base64.b64decode(normalized).decode("utf-8"), sha)


def _is_not_found_error(exc: GitHubProfileError) -> bool:
    return "HTTP 404" in str(exc) or "Not Found" in str(exc)


class GitHubProfileClient:
    def __init__(self, runner: CommandRunner | None = None):
        self.runner = runner or GhCliRunner()

    def authenticated_login(self) -> str:
        try:
            payload = json.loads(self.runner.run(["api", "/user"]))
        except GitHubConnectionError:
            raise
        except GitHubProfileError as exc:
            raise GitHubConnectionError(
                "No usable local GitHub connection found. Run `gh auth login` or proceed with GitHub SSO/OAuth."
            ) from exc
        except json.JSONDecodeError as exc:
            raise GitHubProfileError("GitHub user response was not valid JSON") from exc

        login = payload.get("login")
        if not isinstance(login, str) or not login:
            raise GitHubProfileError("GitHub user response did not include a login")
        return login

    def profile_repository(self, github_login: str) -> ProfileRepository:
        endpoint = f"/repos/{github_login}/{github_login}"
        try:
            payload = json.loads(self.runner.run(["api", endpoint]))
        except GitHubProfileError as exc:
            if _is_not_found_error(exc):
                raise GitHubProfileError(
                    f"Profile repository {github_login}/{github_login} was not found. "
                    "Create the special GitHub profile repository first."
                ) from exc
            raise
        except json.JSONDecodeError as exc:
            raise GitHubProfileError("GitHub repository response was not valid JSON") from exc

        default_branch = payload.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            default_branch = "main"
        return ProfileRepository(owner=github_login, name=github_login, default_branch=default_branch)

    def get_readme(self, repository: ProfileRepository) -> ReadmeFile:
        endpoint = f"/repos/{repository.owner}/{repository.name}/contents/README.md"
        try:
            payload = json.loads(self.runner.run(["api", endpoint]))
        except GitHubProfileError as exc:
            if _is_not_found_error(exc):
                return ReadmeFile("", None)
            raise
        except json.JSONDecodeError as exc:
            raise GitHubProfileError("GitHub README response was not valid JSON") from exc
        if not isinstance(payload, dict):
            raise GitHubProfileError("GitHub README response was not an object")
        return _decode_readme_content(payload)

    def update_readme(
        self,
        repository: ProfileRepository,
        readme: ReadmeFile,
        content: str,
        *,
        message: str,
        branch: str | None = None,
    ) -> str | None:
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        args = [
            "api",
            "--method",
            "PUT",
            f"/repos/{repository.owner}/{repository.name}/contents/README.md",
            "--raw-field",
            f"message={message}",
            "--raw-field",
            f"content={encoded}",
        ]
        if readme.sha:
            args.extend(["--raw-field", f"sha={readme.sha}"])
        if branch:
            args.extend(["--raw-field", f"branch={branch}"])

        try:
            payload = json.loads(self.runner.run(args))
        except json.JSONDecodeError as exc:
            raise GitHubProfileError("GitHub update response was not valid JSON") from exc
        commit = payload.get("commit")
        if isinstance(commit, dict):
            commit_sha = commit.get("sha")
            if isinstance(commit_sha, str):
                return commit_sha
        return None

    def install_badge(
        self,
        *,
        github_login: str | None,
        badge_base_url: str,
        dry_run: bool,
        message: str,
        branch: str | None = None,
    ) -> ProfileBadgeUpdate:
        authenticated_login = self.authenticated_login()
        target_login = github_login or authenticated_login
        if target_login.lower() != authenticated_login.lower():
            raise GitHubProfileError(
                f"authenticated GitHub user is {authenticated_login}, not {target_login}"
            )

        repository = self.profile_repository(authenticated_login)
        readme = self.get_readme(repository)
        updated_content, changed = upsert_badge_block(
            readme.content,
            badge_block(authenticated_login, badge_base_url),
        )
        commit_sha = None
        if changed and not dry_run:
            commit_sha = self.update_readme(
                repository,
                readme,
                updated_content,
                message=message,
                branch=branch,
            )

        return ProfileBadgeUpdate(
            github_login=authenticated_login,
            repository=repository.full_name,
            changed=changed,
            dry_run=dry_run,
            content=updated_content,
            commit_sha=commit_sha,
        )


def badge_base_url_from_env(env: dict[str, str] | None = None) -> str | None:
    source = env if env is not None else os.environ
    return source.get("TOKEN_BADGE_PUBLIC_URL")
