"""Deployment-specific safety checks, used by scripts/security_check.py.

The launcher and its scripts are the only code with authority to terminate
processes and delete directories, so they get scrutiny the rest of the tree does
not need:

* no killing processes by image name (that can hit unrelated programs)
* no recursive deletion of absolute or environment-derived paths
* the launcher's cleanable list must never include a user-data directory
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

_UNSAFE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"taskkill.*/IM\b", re.IGNORECASE),
        "kills processes by image name, which can hit unrelated programs",
    ),
    (
        re.compile(r"\b(?:pkill|killall)\b"),
        "kills processes by name, which can hit unrelated programs",
    ),
    (
        re.compile(r"Stop-Process.*-Name\b", re.IGNORECASE),
        "stops processes by name, which can hit unrelated programs",
    ),
    (
        re.compile(r"""rmtree\(\s*['"][/\\]"""),
        "recursively removes an absolute filesystem path",
    ),
    (
        re.compile(r"Remove-Item.*-Recurse.*\$env:", re.IGNORECASE),
        "recursively removes a path built from an environment variable",
    ),
)

# Directory constants that must never appear as a whole cleanable target.
_PROTECTED_DIR_ATTRS = ("DATA_DIR", "OUTPUTS_DIR", "BACKUPS_DIR")


def scan() -> list[str]:
    """Return findings for deployment scripts and the launcher package."""
    findings: list[str] = []
    for path in _targets():
        findings.extend(_scan_file(path))
    findings.extend(_check_cleanable_targets())
    return findings


def _targets() -> list[Path]:
    paths: list[Path] = []
    deployment_dir = ROOT / "deployment"
    if deployment_dir.is_dir():
        paths.extend(sorted(deployment_dir.rglob("*.py")))
    scripts_dir = ROOT / "scripts"
    if scripts_dir.is_dir():
        paths.extend(sorted(scripts_dir.glob("*.ps1")))
        paths.extend(sorted(scripts_dir.glob("*.py")))
    paths.extend(sorted(ROOT.glob("*.bat")))
    # This file documents the patterns it looks for, so scanning it would
    # report its own rule table.
    return [path for path in paths if path.resolve() != Path(__file__).resolve()]


def _scan_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    findings: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith(("#", "//", "REM ", "rem ")):
            continue
        for pattern, message in _UNSAFE_PATTERNS:
            if pattern.search(line):
                findings.append(f"{_rel(path)}:{number} {message}")
    return findings


def _check_cleanable_targets() -> list[str]:
    """The `clean` command must not be able to remove user data.

    Reads `_CLEANABLE` from the launcher and rejects any entry that is a bare
    protected directory. A path *underneath* one (outputs/evaluation/work) is
    fine, which is why only whole-entry attributes are flagged.
    """
    launcher = ROOT / "deployment" / "launcher.py"
    if not launcher.is_file():
        return []
    try:
        tree = ast.parse(launcher.read_text(encoding="utf-8"), filename=str(launcher))
    except (OSError, SyntaxError) as exc:
        return [f"deployment/launcher.py could not be parsed: {exc}"]

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "_CLEANABLE" for t in node.targets):
            continue
        return _flag_bare_dirs(node.value)
    return ["deployment/launcher.py does not define _CLEANABLE"]


def _flag_bare_dirs(value: ast.AST) -> list[str]:
    findings: list[str] = []
    for element in ast.walk(value):
        if not isinstance(element, ast.Tuple) or len(element.elts) != 2:
            continue
        target = element.elts[1]
        if isinstance(target, ast.Attribute) and target.attr in _PROTECTED_DIR_ATTRS:
            findings.append(
                f"deployment/launcher.py _CLEANABLE includes {target.attr}, "
                f"which would remove user data"
            )
    return findings


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    results = scan()
    if results:
        print("Deployment safety check failed:")
        for item in results:
            print(f"- {item}")
        raise SystemExit(1)
    print("Deployment safety check passed.")
