from __future__ import annotations

import json
from pathlib import Path

from evaluation.categories import BenchmarkCategory
from evaluation.models import BenchmarkCase, BenchmarkDifficulty


DEFAULT_CASE_DIR = Path("benchmarks") / "cases"


def load_cases(
    *,
    case_dir: Path = DEFAULT_CASE_DIR,
    category: BenchmarkCategory | str | None = None,
    difficulty: BenchmarkDifficulty | str | None = None,
    case_id: str | None = None,
    smoke: bool = False,
) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    if not case_dir.exists():
        return cases
    for path in sorted(case_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        raw_cases = data.get("cases", data if isinstance(data, list) else [])
        cases.extend(BenchmarkCase.model_validate(item) for item in raw_cases)

    if category is not None:
        wanted = BenchmarkCategory(category)
        cases = [case for case in cases if case.category == wanted]
    if difficulty is not None:
        wanted_difficulty = BenchmarkDifficulty(difficulty)
        cases = [case for case in cases if case.difficulty == wanted_difficulty]
    if case_id is not None:
        cases = [case for case in cases if case.case_id == case_id]
    if smoke:
        cases = [case for case in cases if case.smoke]
    return sorted(cases, key=lambda case: case.case_id)
