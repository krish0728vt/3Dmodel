# Evaluation And Benchmarks

Milestone 17 adds a deterministic robustness suite for measuring prompt-to-CAD behavior without live AI calls.

Normal benchmark runs use checked-in fixture specs, known operation plans, structural expectations, and tolerant geometry checks. They do not require `OPENAI_API_KEY`, internet access, a browser, MCP servers, or external services.

## Commands

Smoke suite:

```powershell
.\.venv311\Scripts\python app.py evaluate smoke
```

Full deterministic suite:

```powershell
.\.venv311\Scripts\python app.py evaluate run
```

Filters:

```powershell
.\.venv311\Scripts\python app.py evaluate run --category parametrics
.\.venv311\Scripts\python app.py evaluate run --difficulty complex
.\.venv311\Scripts\python app.py evaluate run --case basic_cube_050
```

Baseline comparison:

```powershell
.\.venv311\Scripts\python app.py evaluate compare
```

Update the baseline explicitly:

```powershell
.\.venv311\Scripts\python app.py evaluate update-baseline
```

Show the latest report summary:

```powershell
.\.venv311\Scripts\python app.py evaluate report
```

Optional live AI evaluation:

```powershell
.\.venv311\Scripts\python app.py evaluate live --limit 1
```

Live evaluation requires `OPENAI_API_KEY` and is labeled non-deterministic. It is not used by normal tests or CI-friendly benchmark commands.

## Case Schema

Benchmark cases live in `benchmarks/cases/*.json`.

Important fields:

- `benchmark_schema_version`
- `case_id`
- `name`
- `category`
- `difficulty`
- `prompt`
- `mode`
- `fixture_spec`
- `assembly_fixture`
- `capability_fixture`
- `expected_part_type`
- `expected_operation_types`
- `expected_parameters`
- `expected_export_formats`
- `structural_expectation`
- `geometric_expectation`
- `engineering_expectation`
- `expected_status`
- `expected_failure_category`
- `smoke`

Cases should prefer structural and geometric expectations over exact serialized JSON. For example, assert that an operation plan contains `create_box` and `through_hole`, or that a bounding box is approximately `100 x 60 x 5 mm`.

## Difficulty

- `simple`: primitives and simple template parts
- `medium`: common engineering features such as holes, bosses, enclosures, and assemblies
- `complex`: multi-stage operation plans such as sketches, patterns, shells, lofts, and sweeps
- `advanced`: parametrics, capabilities, repairs, and unsupported/ambiguous classifications

## Categories

The initial corpus covers:

- `basic_primitives`
- `mounting_parts`
- `enclosures`
- `brackets`
- `holes`
- `patterns`
- `boolean_operations`
- `sketches`
- `lofts`
- `sweeps`
- `shells`
- `parametrics`
- `engineering_analysis`
- `assemblies`
- `capabilities`
- `exports`
- `invalid_inputs`
- `ambiguous_inputs`

## Stages

Each result records independent stage outcomes:

1. prompt interpretation
2. schema validation
3. design intent resolution
4. operation or CAD validation
5. CAD execution
6. solid validation
7. structural expectations
8. STEP export
9. STL export
10. engineering analysis
11. assembly or capability analysis where applicable
12. repair where applicable

Failures are not collapsed into a single generic result. The report preserves the failing stage, normalized category, and concise error message.

## Reports

Generated reports are runtime artifacts:

- `outputs/evaluation/latest.json`
- `outputs/evaluation/latest.md`

The JSON report is machine-readable for CI and dashboard use. The Markdown report is a concise human-readable summary with pass counts, stage rates, category breakdown, difficulty breakdown, failure distribution, regressions, and failed cases.

## Baselines

The current stored deterministic baseline is:

```text
benchmarks/baselines/current.json
```

Baseline updates are explicit. The runner never overwrites the baseline automatically after an ordinary run.

Regression comparison flags:

- previous `PASS` to current `FAIL`
- previous `PASS` to current `UNSUPPORTED`
- STEP export regression
- parametric preservation regression

Timing is reported but not treated as a strict regression signal.

## Isolation

Benchmark work files are kept under:

```text
outputs/evaluation/work/
```

The runner uses temporary project, assembly, export, learning, and capability registry data for benchmark execution. It does not write benchmark records into the normal user databases.

## Adding Cases

1. Add a case to `benchmarks/cases/*.json`.
2. Use a deterministic fixture spec or local operation plan.
3. Add structural expectations for part type, operation types, parameters, or relationships.
4. Add tolerant geometry ranges where useful.
5. Mark unsupported and ambiguity cases explicitly instead of treating clean rejection as failure.
6. Run `python app.py evaluate smoke` or a filtered run for the new case.
7. Update the baseline only when the new result is intentional.

## Known Limits

- The initial full deterministic corpus is representative, not exhaustive.
- Some OpenCascade operations have numerical sensitivity; use tolerances.
- Live AI mode is intentionally separate and non-deterministic.
- Evaluation reports are read-only in the web app; benchmark execution is CLI-first.
