from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Callable


PYTHON_MIN_VERSION = (3, 11)
CCUSAGE_INSTALL_COMMAND = "npm install -g ccusage"
CCUSAGE_INSTALL_GUIDANCE = (
    "Install Node.js/npm, then run `npm install -g ccusage`, "
    "and verify with `token-badge doctor`."
)

WhichFn = Callable[[str], str | None]


@dataclass(frozen=True)
class DependencyCheck:
    name: str
    status: str
    required: bool
    detail: str
    remediation: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, str | bool | None]:
        return asdict(self)


def _command_output(command: list[str], timeout_seconds: int = 10) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)

    output = completed.stdout.strip() or completed.stderr.strip()
    return True, output


def check_python_version() -> DependencyCheck:
    current = sys.version_info[:3]
    required = ".".join(str(part) for part in PYTHON_MIN_VERSION)
    detail = f"Python {current[0]}.{current[1]}.{current[2]}"
    if current >= PYTHON_MIN_VERSION:
        return DependencyCheck(
            name="python",
            status="ok",
            required=True,
            detail=f"{detail} satisfies >= {required}",
        )

    return DependencyCheck(
        name="python",
        status="error",
        required=True,
        detail=f"{detail} is lower than required >= {required}",
        remediation=f"Install Python {required} or newer.",
    )


def check_npm(which: WhichFn = shutil.which) -> DependencyCheck:
    npm_path = which("npm")
    if not npm_path:
        return DependencyCheck(
            name="npm",
            status="warning",
            required=False,
            detail="npm is not on PATH; runtime may work if ccusage is already installed",
            remediation="Install Node.js/npm before installing or upgrading ccusage.",
        )

    ok, version = _command_output([npm_path, "--version"])
    detail = f"npm found at {npm_path}"
    if version:
        detail = f"{detail}: {version}"
    return DependencyCheck(name="npm", status="ok" if ok else "warning", required=False, detail=detail)


def check_ccusage(which: WhichFn = shutil.which) -> DependencyCheck:
    ccusage_path = which("ccusage")
    if not ccusage_path:
        return DependencyCheck(
            name="ccusage",
            status="error",
            required=True,
            detail="ccusage is not installed or is not on PATH",
            remediation=CCUSAGE_INSTALL_GUIDANCE,
        )

    ok, version = _command_output([ccusage_path, "--version"])
    detail = f"ccusage found at {ccusage_path}"
    if version:
        detail = f"{detail}: {version}"
    return DependencyCheck(name="ccusage", status="ok" if ok else "error", required=True, detail=detail)


def check_ccusage_codex_support(which: WhichFn = shutil.which) -> DependencyCheck:
    ccusage_path = which("ccusage")
    if not ccusage_path:
        return DependencyCheck(
            name="ccusage-codex",
            status="error",
            required=True,
            detail="cannot check Codex support because ccusage is missing",
            remediation=CCUSAGE_INSTALL_GUIDANCE,
        )

    ok, output = _command_output([ccusage_path, "codex", "--help"])
    if ok and "monthly" in output and "session" in output:
        return DependencyCheck(
            name="ccusage-codex",
            status="ok",
            required=True,
            detail="ccusage exposes Codex monthly and session commands",
        )

    return DependencyCheck(
        name="ccusage-codex",
        status="error",
        required=True,
        detail="ccusage is installed but Codex commands were not detected",
        remediation=f"Upgrade ccusage with `{CCUSAGE_INSTALL_COMMAND}`.",
    )


def collect_dependency_checks(which: WhichFn = shutil.which) -> list[DependencyCheck]:
    return [
        check_python_version(),
        check_npm(which),
        check_ccusage(which),
        check_ccusage_codex_support(which),
    ]


def required_checks_pass(checks: list[DependencyCheck]) -> bool:
    return all(check.ok for check in checks if check.required)

