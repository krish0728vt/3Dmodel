"""Documentation sanity checks.

Catches the documentation rot that is easy to miss in review: links to files
that no longer exist, references to commands the CLI does not have, and a
README that has quietly grown past its budget.

    python scripts/check_docs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DOCS = ROOT / "docs"

# README is the product front door, not a release-notes dump.
README_MAX_LINES = 500

LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
APP_COMMAND_PATTERN = re.compile(r"python app\.py ([a-z-]+)")


def main() -> int:
    findings: list[str] = []
    findings.extend(_check_links())
    findings.extend(_check_readme_length())
    findings.extend(_check_app_commands())

    if findings:
        print("Documentation check failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Documentation check passed.")
    return 0


def _markdown_files() -> list[Path]:
    files = [README] if README.is_file() else []
    if DOCS.is_dir():
        files.extend(sorted(DOCS.glob("*.md")))
    changelog = ROOT / "CHANGELOG.md"
    if changelog.is_file():
        files.append(changelog)
    return files


def _check_links() -> list[str]:
    """Every relative link must resolve to a file that exists."""
    findings: list[str] = []
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8")
        for target in LINK_PATTERN.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            # Strip any anchor before resolving.
            bare = target.split("#", 1)[0]
            if not bare:
                continue
            resolved = (path.parent / bare).resolve()
            if not resolved.exists():
                findings.append(f"{_rel(path)} links to missing path: {target}")
    return findings


def _check_readme_length() -> list[str]:
    if not README.is_file():
        return ["README.md is missing"]
    lines = len(README.read_text(encoding="utf-8").splitlines())
    if lines > README_MAX_LINES:
        return [
            f"README.md is {lines} lines, over the {README_MAX_LINES}-line budget; "
            f"move detail into docs/"
        ]
    return []


def _check_app_commands() -> list[str]:
    """Documented `python app.py <command>` invocations must be real commands."""
    sys.path.insert(0, str(ROOT))
    try:
        import app as app_module
    except Exception as exc:  # noqa: BLE001 - report rather than crash the scan
        return [f"could not import app.py to verify documented commands: {exc}"]

    known = set(getattr(app_module, "_DEPLOYMENT_COMMANDS", set()))
    # Subcommand groups dispatched before the deployment commands.
    known.update({"project", "learning", "capabilities", "export", "assembly", "evaluate"})

    findings: list[str] = []
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8")
        for command in sorted(set(APP_COMMAND_PATTERN.findall(text))):
            if command not in known:
                findings.append(f"{_rel(path)} documents unknown command: python app.py {command}")
    return findings


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
