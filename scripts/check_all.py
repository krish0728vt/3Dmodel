from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


@dataclass(frozen=True)
class Check:
    name: str
    command: list[str]
    cwd: Path = ROOT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SHAH INDUSTRIES local verification checks.")
    parser.add_argument(
        "--only",
        action="append",
        choices=["lint", "workflows", "python", "evaluation", "frontend", "security"],
        help="Run only the selected group. May be repeated.",
    )
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args(argv)

    selected = set(args.only or ["lint", "workflows", "python", "evaluation", "frontend", "security"])
    checks = _checks(selected)
    failures: list[str] = []
    for check in checks:
        print(f"\n==> {check.name}")
        result = subprocess.run(check.command, cwd=check.cwd)
        if result.returncode != 0:
            failures.append(check.name)
            print(f"FAIL: {check.name} exited with {result.returncode}")
            if not args.continue_on_error:
                break
        else:
            print(f"PASS: {check.name}")

    print("\nSummary")
    if failures:
        for failure in failures:
            print(f"- FAIL {failure}")
        return 1
    for check in checks:
        print(f"- PASS {check.name}")
    return 0


def _checks(selected: set[str]) -> list[Check]:
    python = sys.executable
    npm = "npm.cmd" if os.name == "nt" else "npm"
    checks: list[Check] = []
    if "lint" in selected:
        checks.append(Check("Python lint (ruff)", [python, "-m", "ruff", "check", "."]))
    if "workflows" in selected:
        actionlint = _find_actionlint()
        if actionlint is None:
            print("SKIP: Workflow lint (actionlint not installed; pip install -r requirements-dev.txt)")
        else:
            checks.append(Check("Workflow lint (actionlint)", [actionlint, *_workflow_files()]))
    if "python" in selected:
        checks.append(Check("Python tests", [python, "-m", "pytest"]))
    if "evaluation" in selected:
        checks.append(Check("Evaluation smoke", [python, "app.py", "evaluate", "smoke"]))
        checks.append(Check("Evaluation baseline compare", [python, "app.py", "evaluate", "compare"]))
    if "frontend" in selected:
        checks.append(Check("Frontend typecheck", [npm, "run", "typecheck"], WEB))
        checks.append(Check("Frontend tests", [npm, "test"], WEB))
        checks.append(Check("Frontend production build", [npm, "run", "build"], WEB))
    if "security" in selected:
        checks.append(Check("Security scan", [python, "scripts/security_check.py"]))
    return checks


def _find_actionlint() -> str | None:
    """actionlint ships as a binary next to the interpreter or on PATH."""
    scripts_dir = Path(sys.executable).parent
    for candidate in (scripts_dir / "actionlint.exe", scripts_dir / "actionlint"):
        if candidate.exists():
            return str(candidate)
    return shutil.which("actionlint")


def _workflow_files() -> list[str]:
    workflows = ROOT / ".github" / "workflows"
    found = sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml"))
    return [str(path) for path in found]


if __name__ == "__main__":
    raise SystemExit(main())
