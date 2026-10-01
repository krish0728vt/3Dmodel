"""Full release-candidate verification.

Everything `check_all.py` runs, plus the complete deterministic benchmark and
the deployment safety scan. Nothing here needs an API key, the internet, an MCP
server, or a browser: the whole gate is deterministic and offline.

    python scripts/release_check.py
    python scripts/release_check.py --skip-full-benchmark   # faster iteration
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


@dataclass
class Stage:
    name: str
    command: list[str]
    cwd: Path = ROOT
    # Pulls a count ("320 passed") out of the output for the summary line.
    detail_pattern: str | None = None


@dataclass
class Result:
    name: str
    passed: bool
    detail: str = ""
    seconds: float = 0.0
    output: str = field(default="", repr=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SHAH INDUSTRIES release candidate check.")
    parser.add_argument(
        "--skip-full-benchmark",
        action="store_true",
        help="Run only the smoke benchmark instead of the full corpus.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Run every stage even after one fails.",
    )
    args = parser.parse_args(argv)

    print("SHAH INDUSTRIES RELEASE CHECK")
    print()
    print(_version_line())
    print()

    results: list[Result] = []
    for stage in _stages(skip_full=args.skip_full_benchmark):
        result = _run(stage)
        results.append(result)
        _print_result(result)
        if not result.passed and not args.continue_on_error:
            break

    print()
    _print_summary(results)

    failed = [result for result in results if not result.passed]
    if failed or len(results) < len(_stages(skip_full=args.skip_full_benchmark)):
        print()
        print("NOT READY FOR RELEASE CANDIDATE")
        for result in failed:
            print(f"  {result.name} failed. Last lines:")
            for line in _tail(result.output):
                print(f"    {line}")
        return 1

    print()
    print("READY FOR RELEASE CANDIDATE")
    return 0


def _stages(*, skip_full: bool) -> list[Stage]:
    python = sys.executable
    npm = "npm.cmd" if os.name == "nt" else "npm"
    stages = [
        Stage("Ruff", [python, "-m", "ruff", "check", "."]),
        Stage("GitHub Actions lint", [python, "scripts/check_all.py", "--only", "workflows"]),
        Stage("Deployment CLI", [python, "app.py", "doctor", "--skip-frontend"]),
        Stage(
            "Python tests",
            [python, "-m", "pytest", "-q"],
            detail_pattern=r"(\d+) passed",
        ),
        Stage("Evaluation smoke", [python, "app.py", "evaluate", "smoke"], detail_pattern=r"Cases: (\d+)"),
    ]
    if not skip_full:
        stages.append(
            Stage("Full benchmark", [python, "app.py", "evaluate", "run"], detail_pattern=r"Cases: (\d+)")
        )
    stages += [
        Stage("Regression compare", [python, "app.py", "evaluate", "compare"]),
        Stage("Frontend typecheck", [npm, "run", "typecheck"], WEB),
        Stage("Frontend tests", [npm, "test"], WEB, detail_pattern=r"Tests\s+(\d+) passed"),
        Stage("Frontend build", [npm, "run", "build"], WEB),
        Stage("Security scan", [python, "scripts/security_check.py"]),
        Stage("Deployment safety", [python, "scripts/deployment_safety.py"]),
        Stage("Documentation links", [python, "scripts/check_docs.py"]),
    ]
    return stages


def _run(stage: Stage) -> Result:
    executable = shutil.which(stage.command[0]) or stage.command[0]
    started = time.monotonic()
    try:
        completed = subprocess.run(  # noqa: S603 - explicit arg list, shell never used
            [executable, *stage.command[1:]],
            cwd=str(stage.cwd),
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
    except OSError as exc:
        return Result(stage.name, False, detail=f"could not run: {exc}", seconds=time.monotonic() - started)

    elapsed = time.monotonic() - started
    output = (completed.stdout or "") + (completed.stderr or "")
    detail = ""
    if stage.detail_pattern:
        match = re.search(stage.detail_pattern, output)
        if match:
            detail = match.group(1)
    return Result(stage.name, completed.returncode == 0, detail, elapsed, output)


def _print_result(result: Result) -> None:
    tag = "[PASS]" if result.passed else "[FAIL]"
    suffix = ""
    if result.detail:
        if result.name.endswith("tests"):
            suffix = f" - {result.detail} passed"
        elif "benchmark" in result.name.lower() or "smoke" in result.name.lower():
            suffix = f" - {result.detail} cases"
        else:
            suffix = f" - {result.detail}"
    print(f"{tag} {result.name}{suffix}  ({result.seconds:.1f}s)")


def _print_summary(results: list[Result]) -> None:
    total = sum(result.seconds for result in results)
    passed = sum(1 for result in results if result.passed)
    print(f"{passed}/{len(results)} stages passed in {total:.0f}s")

    report = ROOT / "outputs" / "evaluation" / "latest.json"
    if report.is_file():
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        metrics = data.get("metrics", {})
        regressions = len(data.get("regressions", []))
        print(
            f"Benchmark: {data.get('case_count', '?')} cases, "
            f"{metrics.get('pass_count', '?')} pass, "
            f"{metrics.get('fail_count', '?')} fail, "
            f"{metrics.get('unsupported_count', '?')} unsupported, "
            f"{regressions} regressions"
        )


def _version_line() -> str:
    sys.path.insert(0, str(ROOT))
    from shah_version import version_line

    return version_line()


def _tail(output: str, lines: int = 12) -> list[str]:
    rows = [line.rstrip() for line in output.splitlines() if line.strip()]
    return rows[-lines:]


if __name__ == "__main__":
    raise SystemExit(main())
