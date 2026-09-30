from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from config import CONFIG
from learning.adaptive import calculate_confidence, json_dumps, normalize_pattern_signature, promote_status, utc_now
from learning.models import (
    EvidenceStatus,
    FailureCategory,
    FailureRecord,
    LessonRecord,
    RepairAttemptRecord,
    RepairStrategyRecord,
    SuccessfulPatternRecord,
)


class LearningStore:
    """SQLite-backed learning store with evidence-driven adaptive lifecycle data."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else CONFIG.learning_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    component TEXT PRIMARY KEY,
                    version INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS failures (
                    failure_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    prompt TEXT,
                    parsed_spec_json TEXT,
                    operation_plan_json TEXT,
                    failing_operation_id TEXT,
                    error_category TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    relevant_parameters_json TEXT,
                    repair_attempt_count INTEGER NOT NULL DEFAULT 0,
                    resolved INTEGER NOT NULL DEFAULT 0,
                    successful_repair_id TEXT,
                    normalized_signature TEXT
                );

                CREATE TABLE IF NOT EXISTS lessons (
                    lesson_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    problem_signature TEXT NOT NULL,
                    applicable_part_types TEXT NOT NULL,
                    applicable_operation_types TEXT NOT NULL,
                    known_bad_pattern TEXT,
                    recommended_pattern TEXT,
                    evidence_count INTEGER NOT NULL,
                    success_count INTEGER NOT NULL,
                    failure_count INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    last_verified_at TEXT,
                    status TEXT NOT NULL DEFAULT 'OBSERVED',
                    confidence_score REAL NOT NULL DEFAULT 0.1,
                    last_used_at TEXT,
                    source_capability_versions TEXT NOT NULL DEFAULT '{}',
                    source_engine_version TEXT,
                    contradiction_count INTEGER NOT NULL DEFAULT 0,
                    superseded_by_lesson_id TEXT,
                    source_type TEXT NOT NULL DEFAULT 'manual_entry',
                    source_ids TEXT NOT NULL DEFAULT '[]',
                    regression_ids TEXT NOT NULL DEFAULT '[]',
                    manually_overridden INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS successful_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    applicable_operation_types TEXT NOT NULL,
                    input_signature TEXT NOT NULL,
                    plan_fragment_json TEXT NOT NULL,
                    validation_notes TEXT,
                    success_count INTEGER NOT NULL,
                    last_success_at TEXT NOT NULL,
                    operation_signature TEXT,
                    part_type TEXT,
                    usage_count INTEGER NOT NULL DEFAULT 1,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    confidence_score REAL NOT NULL DEFAULT 0.1,
                    status TEXT NOT NULL DEFAULT 'OBSERVED',
                    created_at TEXT,
                    last_used_at TEXT,
                    last_verified_at TEXT,
                    source_capabilities TEXT NOT NULL DEFAULT '{}',
                    regression_ids TEXT NOT NULL DEFAULT '[]',
                    manually_overridden INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS repair_attempts (
                    repair_id TEXT PRIMARY KEY,
                    failure_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    repaired_plan_json TEXT,
                    strategy TEXT NOT NULL,
                    result TEXT NOT NULL,
                    error_message TEXT,
                    timestamp TEXT NOT NULL,
                    strategy_signature TEXT
                );

                CREATE TABLE IF NOT EXISTS evidence_events (
                    event_id TEXT PRIMARY KEY,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    contradiction INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS repair_strategies (
                    strategy_signature TEXT PRIMARY KEY,
                    problem_signature TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    successes INTEGER NOT NULL DEFAULT 0,
                    failures INTEGER NOT NULL DEFAULT 0,
                    confidence_score REAL NOT NULL DEFAULT 0.1,
                    status TEXT NOT NULL DEFAULT 'OBSERVED',
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    last_success_at TEXT,
                    last_failure_at TEXT
                );
                """
            )
            self._migrate_columns(conn)
            conn.execute("INSERT OR REPLACE INTO schema_version(component, version) VALUES ('learning', 3)")

    def _migrate_columns(self, conn: sqlite3.Connection) -> None:
        self._ensure_columns(conn, "failures", {"normalized_signature": "TEXT"})
        self._ensure_columns(
            conn,
            "lessons",
            {
                "status": "TEXT NOT NULL DEFAULT 'OBSERVED'",
                "confidence_score": "REAL NOT NULL DEFAULT 0.1",
                "last_used_at": "TEXT",
                "source_capability_versions": "TEXT NOT NULL DEFAULT '{}'",
                "source_engine_version": "TEXT",
                "contradiction_count": "INTEGER NOT NULL DEFAULT 0",
                "superseded_by_lesson_id": "TEXT",
                "source_type": "TEXT NOT NULL DEFAULT 'manual_entry'",
                "source_ids": "TEXT NOT NULL DEFAULT '[]'",
                "regression_ids": "TEXT NOT NULL DEFAULT '[]'",
                "manually_overridden": "INTEGER NOT NULL DEFAULT 0",
            },
        )
        self._ensure_columns(
            conn,
            "successful_patterns",
            {
                "operation_signature": "TEXT",
                "part_type": "TEXT",
                "usage_count": "INTEGER NOT NULL DEFAULT 1",
                "failure_count": "INTEGER NOT NULL DEFAULT 0",
                "confidence_score": "REAL NOT NULL DEFAULT 0.1",
                "status": "TEXT NOT NULL DEFAULT 'OBSERVED'",
                "created_at": "TEXT",
                "last_used_at": "TEXT",
                "last_verified_at": "TEXT",
                "source_capabilities": "TEXT NOT NULL DEFAULT '{}'",
                "regression_ids": "TEXT NOT NULL DEFAULT '[]'",
                "manually_overridden": "INTEGER NOT NULL DEFAULT 0",
            },
        )
        self._ensure_columns(conn, "repair_attempts", {"strategy_signature": "TEXT"})
        conn.execute("UPDATE lessons SET confidence_score = confidence WHERE confidence_score = 0.1 AND confidence != 0.1")
        conn.execute("UPDATE successful_patterns SET created_at = last_success_at WHERE created_at IS NULL")
        conn.execute("UPDATE successful_patterns SET last_verified_at = last_success_at WHERE last_verified_at IS NULL")

    def _ensure_columns(self, conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for column, definition in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def record_failure(
        self,
        *,
        error_category: FailureCategory,
        error_message: str,
        prompt: str | None = None,
        parsed_spec_json: str | None = None,
        operation_plan_json: str | None = None,
        failing_operation_id: str | None = None,
        relevant_parameters: dict[str, Any] | None = None,
        normalized_signature: str | None = None,
    ) -> str:
        failure_id = f"fail_{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO failures (
                    failure_id, timestamp, prompt, parsed_spec_json, operation_plan_json,
                    failing_operation_id, error_category, error_message, relevant_parameters_json,
                    repair_attempt_count, resolved, successful_repair_id, normalized_signature
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, NULL, ?)
                """,
                (
                    failure_id,
                    utc_now(),
                    _sanitize(prompt),
                    parsed_spec_json,
                    operation_plan_json,
                    failing_operation_id,
                    error_category.value,
                    _sanitize(error_message) or "",
                    json.dumps(relevant_parameters) if relevant_parameters else None,
                    normalized_signature or error_category.value,
                ),
            )
        return failure_id

    def get_failure(self, failure_id: str) -> FailureRecord | None:
        row = self._fetch_one("SELECT * FROM failures WHERE failure_id = ?", (failure_id,))
        return _failure_from_row(row) if row else None

    def list_failures(self, limit: int = 20) -> list[FailureRecord]:
        rows = self._fetch_all("SELECT * FROM failures ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [_failure_from_row(row) for row in rows]

    def insert_lesson(
        self,
        *,
        title: str,
        description: str,
        problem_signature: str,
        applicable_part_types: list[str] | None = None,
        applicable_operation_types: list[str] | None = None,
        known_bad_pattern: str | None = None,
        recommended_pattern: str | None = None,
        evidence_count: int = 1,
        success_count: int = 1,
        failure_count: int = 0,
        confidence: float | None = None,
        source_type: str = "manual_entry",
        source_ids: list[str] | None = None,
        source_capability_versions: dict[str, str] | None = None,
        source_engine_version: str | None = None,
        regression_ids: list[str] | None = None,
    ) -> str:
        lesson_id = f"lesson_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        confidence_score = confidence if confidence is not None else calculate_confidence(success_count=success_count, failure_count=failure_count)
        status = promote_status(success_count=success_count, failure_count=failure_count)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO lessons (
                    lesson_id, title, description, problem_signature, applicable_part_types,
                    applicable_operation_types, known_bad_pattern, recommended_pattern,
                    evidence_count, success_count, failure_count, confidence, created_at,
                    last_verified_at, status, confidence_score, source_capability_versions,
                    source_engine_version, contradiction_count, source_type, source_ids,
                    regression_ids, manually_overridden
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 0)
                """,
                (
                    lesson_id,
                    title,
                    description,
                    problem_signature,
                    json.dumps(applicable_part_types or []),
                    json.dumps(applicable_operation_types or []),
                    known_bad_pattern,
                    recommended_pattern,
                    evidence_count,
                    success_count,
                    failure_count,
                    confidence_score,
                    now,
                    now,
                    status.value,
                    confidence_score,
                    json_dumps(source_capability_versions or {}),
                    source_engine_version,
                    source_type,
                    json.dumps(source_ids or []),
                    json.dumps(regression_ids or []),
                ),
            )
        return lesson_id

    def list_lessons(self, limit: int = 50, include_deprecated: bool = True) -> list[LessonRecord]:
        if include_deprecated:
            rows = self._fetch_all("SELECT * FROM lessons ORDER BY created_at DESC LIMIT ?", (limit,))
        else:
            rows = self._fetch_all(
                "SELECT * FROM lessons WHERE status != ? ORDER BY confidence_score DESC, created_at DESC LIMIT ?",
                (EvidenceStatus.DEPRECATED.value, limit),
            )
        return [_lesson_from_row(row) for row in rows]

    def get_lesson(self, lesson_id: str) -> LessonRecord | None:
        row = self._fetch_one("SELECT * FROM lessons WHERE lesson_id = ?", (lesson_id,))
        return _lesson_from_row(row) if row else None

    def record_lesson_evidence(
        self,
        lesson_id: str,
        *,
        success: bool = True,
        contradiction: bool = False,
        event_id: str | None = None,
    ) -> LessonRecord:
        lesson = self.get_lesson(lesson_id)
        if lesson is None:
            raise ValueError(f"Unknown lesson: {lesson_id}")
        event_id = event_id or f"event_{uuid.uuid4().hex[:16]}"
        success_count = lesson.success_count + (1 if success else 0)
        failure_count = lesson.failure_count + (0 if success else 1)
        contradiction_count = lesson.contradiction_count + (1 if contradiction else 0)
        confidence_score = calculate_confidence(success_count=success_count, failure_count=failure_count, contradiction_count=contradiction_count)
        status = promote_status(
            success_count=success_count,
            failure_count=failure_count,
            contradiction_count=contradiction_count,
            manually_overridden=lesson.manually_overridden,
            current_status=lesson.status,
        )
        with self._connect() as conn:
            if not self._insert_evidence_event(
                conn,
                event_id=event_id,
                target_type="lesson",
                target_id=lesson_id,
                outcome="success" if success else "failure",
                contradiction=contradiction,
            ):
                return lesson
            conn.execute(
                """
                UPDATE lessons
                SET evidence_count = ?, success_count = ?, failure_count = ?, contradiction_count = ?,
                    confidence = ?, confidence_score = ?, status = ?, last_verified_at = ?
                WHERE lesson_id = ?
                """,
                (
                    lesson.evidence_count + 1,
                    success_count,
                    failure_count,
                    contradiction_count,
                    confidence_score,
                    confidence_score,
                    status.value,
                    utc_now(),
                    lesson_id,
                ),
            )
        return self.get_lesson(lesson_id)  # type: ignore[return-value]

    def set_lesson_status(self, lesson_id: str, status: EvidenceStatus, *, manual: bool = True) -> LessonRecord:
        if self.get_lesson(lesson_id) is None:
            raise ValueError(f"Unknown lesson: {lesson_id}")
        with self._connect() as conn:
            conn.execute(
                "UPDATE lessons SET status = ?, manually_overridden = ?, last_verified_at = ? WHERE lesson_id = ?",
                (status.value, 1 if manual else 0, utc_now(), lesson_id),
            )
        return self.get_lesson(lesson_id)  # type: ignore[return-value]

    def record_successful_pattern(
        self,
        *,
        name: str,
        description: str,
        applicable_operation_types: list[str],
        input_signature: str,
        plan_fragment_json: str,
        validation_notes: str | None = None,
        part_type: str | None = None,
        source_capabilities: dict[str, str] | None = None,
    ) -> str:
        pattern_id = f"pattern_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        operation_signature = _signature_from_fragment(plan_fragment_json, fallback=input_signature)
        confidence_score = calculate_confidence(success_count=1)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO successful_patterns (
                    pattern_id, name, description, applicable_operation_types, input_signature,
                    plan_fragment_json, validation_notes, success_count, last_success_at,
                    operation_signature, part_type, usage_count, failure_count, confidence_score,
                    status, created_at, last_used_at, last_verified_at, source_capabilities,
                    regression_ids, manually_overridden
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 1, 0, ?, ?, ?, ?, ?, ?, '[]', 0)
                """,
                (
                    pattern_id,
                    name,
                    description,
                    json.dumps(applicable_operation_types),
                    input_signature,
                    plan_fragment_json,
                    validation_notes,
                    now,
                    operation_signature,
                    part_type,
                    confidence_score,
                    EvidenceStatus.OBSERVED.value,
                    now,
                    now,
                    now,
                    json_dumps(source_capabilities or {}),
                ),
            )
        return pattern_id

    def list_patterns(self, limit: int = 50, include_deprecated: bool = True) -> list[SuccessfulPatternRecord]:
        if include_deprecated:
            rows = self._fetch_all("SELECT * FROM successful_patterns ORDER BY last_success_at DESC LIMIT ?", (limit,))
        else:
            rows = self._fetch_all(
                "SELECT * FROM successful_patterns WHERE status != ? ORDER BY confidence_score DESC, last_success_at DESC LIMIT ?",
                (EvidenceStatus.DEPRECATED.value, limit),
            )
        return [_pattern_from_row(row) for row in rows]

    def get_pattern(self, pattern_id: str) -> SuccessfulPatternRecord | None:
        row = self._fetch_one("SELECT * FROM successful_patterns WHERE pattern_id = ?", (pattern_id,))
        return _pattern_from_row(row) if row else None

    def record_pattern_evidence(
        self,
        pattern_id: str,
        *,
        success: bool = True,
        event_id: str | None = None,
    ) -> SuccessfulPatternRecord:
        pattern = self.get_pattern(pattern_id)
        if pattern is None:
            raise ValueError(f"Unknown pattern: {pattern_id}")
        event_id = event_id or f"event_{uuid.uuid4().hex[:16]}"
        success_count = pattern.success_count + (1 if success else 0)
        failure_count = pattern.failure_count + (0 if success else 1)
        confidence_score = calculate_confidence(success_count=success_count, failure_count=failure_count)
        status = promote_status(
            success_count=success_count,
            failure_count=failure_count,
            manually_overridden=pattern.manually_overridden,
            current_status=pattern.status,
        )
        now = utc_now()
        with self._connect() as conn:
            if not self._insert_evidence_event(
                conn,
                event_id=event_id,
                target_type="pattern",
                target_id=pattern_id,
                outcome="success" if success else "failure",
                contradiction=False,
            ):
                return pattern
            conn.execute(
                """
                UPDATE successful_patterns
                SET usage_count = ?, success_count = ?, failure_count = ?, confidence_score = ?,
                    status = ?, last_used_at = ?, last_verified_at = ?,
                    last_success_at = CASE WHEN ? THEN ? ELSE last_success_at END
                WHERE pattern_id = ?
                """,
                (pattern.usage_count + 1, success_count, failure_count, confidence_score, status.value, now, now, 1 if success else 0, now, pattern_id),
            )
        return self.get_pattern(pattern_id)  # type: ignore[return-value]

    def set_pattern_status(self, pattern_id: str, status: EvidenceStatus, *, manual: bool = True) -> SuccessfulPatternRecord:
        if self.get_pattern(pattern_id) is None:
            raise ValueError(f"Unknown pattern: {pattern_id}")
        with self._connect() as conn:
            conn.execute(
                "UPDATE successful_patterns SET status = ?, manually_overridden = ?, last_verified_at = ? WHERE pattern_id = ?",
                (status.value, 1 if manual else 0, utc_now(), pattern_id),
            )
        return self.get_pattern(pattern_id)  # type: ignore[return-value]

    def record_repair_attempt(
        self,
        *,
        failure_id: str,
        attempt_number: int,
        strategy: str,
        result: str,
        repaired_plan_json: str | None = None,
        error_message: str | None = None,
        strategy_signature: str | None = None,
    ) -> str:
        repair_id = f"repair_{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO repair_attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (repair_id, failure_id, attempt_number, repaired_plan_json, strategy, result, _sanitize(error_message), utc_now(), strategy_signature),
            )
            conn.execute("UPDATE failures SET repair_attempt_count = repair_attempt_count + 1 WHERE failure_id = ?", (failure_id,))
            if result == "success":
                conn.execute("UPDATE failures SET resolved = 1, successful_repair_id = ? WHERE failure_id = ?", (repair_id, failure_id))
            if strategy_signature:
                self._record_repair_strategy_event(conn, failure_id=failure_id, strategy=strategy, result=result, strategy_signature=strategy_signature)
        return repair_id

    def list_repair_attempts(self, failure_id: str) -> list[RepairAttemptRecord]:
        rows = self._fetch_all("SELECT * FROM repair_attempts WHERE failure_id = ? ORDER BY attempt_number", (failure_id,))
        return [_repair_from_row(row) for row in rows]

    def list_repair_strategies(self, *, problem_signature: str | None = None, limit: int = 20) -> list[RepairStrategyRecord]:
        if problem_signature:
            rows = self._fetch_all(
                """
                SELECT * FROM repair_strategies
                WHERE problem_signature = ? AND status != ?
                ORDER BY confidence_score DESC, successes DESC, last_used_at DESC
                LIMIT ?
                """,
                (problem_signature, EvidenceStatus.DEPRECATED.value, limit),
            )
        else:
            rows = self._fetch_all(
                """
                SELECT * FROM repair_strategies
                WHERE status != ?
                ORDER BY confidence_score DESC, successes DESC, last_used_at DESC
                LIMIT ?
                """,
                (EvidenceStatus.DEPRECATED.value, limit),
            )
        return [_repair_strategy_from_row(row) for row in rows]

    def mark_records_needing_revalidation(
        self,
        *,
        engine_version: str | None = None,
        capability_versions: dict[str, str] | None = None,
    ) -> dict[str, int]:
        capability_versions = capability_versions or {}
        lesson_count = 0
        pattern_count = 0
        with self._connect() as conn:
            lesson_rows = conn.execute("SELECT * FROM lessons WHERE status != ?", (EvidenceStatus.DEPRECATED.value,)).fetchall()
            for row in lesson_rows:
                if row["manually_overridden"] or row["status"] == EvidenceStatus.NEEDS_REVALIDATION.value:
                    continue
                source_versions = _json_dict(row["source_capability_versions"])
                engine_changed = bool(engine_version and row["source_engine_version"] and row["source_engine_version"] != engine_version)
                capability_changed = any(capability_versions.get(key) not in {None, value} for key, value in source_versions.items())
                if engine_changed or capability_changed:
                    confidence = calculate_confidence(
                        success_count=row["success_count"],
                        failure_count=row["failure_count"],
                        contradiction_count=row["contradiction_count"],
                        compatible_version=False,
                    )
                    conn.execute(
                        "UPDATE lessons SET status = ?, confidence = ?, confidence_score = ? WHERE lesson_id = ?",
                        (EvidenceStatus.NEEDS_REVALIDATION.value, confidence, confidence, row["lesson_id"]),
                    )
                    lesson_count += 1

            pattern_rows = conn.execute("SELECT * FROM successful_patterns WHERE status != ?", (EvidenceStatus.DEPRECATED.value,)).fetchall()
            for row in pattern_rows:
                if row["manually_overridden"] or row["status"] == EvidenceStatus.NEEDS_REVALIDATION.value:
                    continue
                source_versions = _json_dict(row["source_capabilities"])
                capability_changed = any(capability_versions.get(key) not in {None, value} for key, value in source_versions.items())
                if capability_changed:
                    confidence = calculate_confidence(success_count=row["success_count"], failure_count=row["failure_count"], compatible_version=False)
                    conn.execute(
                        "UPDATE successful_patterns SET status = ?, confidence_score = ? WHERE pattern_id = ?",
                        (EvidenceStatus.NEEDS_REVALIDATION.value, confidence, row["pattern_id"]),
                    )
                    pattern_count += 1
        return {"lessons": lesson_count, "patterns": pattern_count}

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            failures = conn.execute("SELECT COUNT(*) FROM failures").fetchone()[0]
            resolved = conn.execute("SELECT COUNT(*) FROM failures WHERE resolved = 1").fetchone()[0]
            lessons = conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
            patterns = conn.execute("SELECT COUNT(*) FROM successful_patterns").fetchone()[0]
            repairs = conn.execute("SELECT COUNT(*) FROM repair_attempts").fetchone()[0]
            repair_strategies = conn.execute("SELECT COUNT(*) FROM repair_strategies").fetchone()[0]
            lesson_rows = conn.execute("SELECT status, COUNT(*) count FROM lessons GROUP BY status").fetchall()
            pattern_rows = conn.execute("SELECT status, COUNT(*) count FROM successful_patterns GROUP BY status").fetchall()
            avg_conf = conn.execute("SELECT AVG(confidence_score) FROM lessons").fetchone()[0] or 0.0
        success_rate = round((resolved / failures) * 100, 1) if failures else 0.0
        return {
            "failures": failures,
            "resolved": resolved,
            "unresolved": failures - resolved,
            "lessons": lessons,
            "patterns": patterns,
            "repairs": repairs,
            "repair_strategies": repair_strategies,
            "repair_success_rate": success_rate,
            "lessons_by_status": {row["status"]: row["count"] for row in lesson_rows},
            "patterns_by_status": {row["status"]: row["count"] for row in pattern_rows},
            "average_lesson_confidence": round(float(avg_conf), 3),
        }

    def failure_analytics(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            """
            SELECT COALESCE(normalized_signature, error_category) signature, error_category, COUNT(*) count
            FROM failures
            GROUP BY signature, error_category
            ORDER BY count DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in rows]

    def _fetch_one(self, query: str, params: tuple[Any, ...]) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(query, params).fetchone()

    def _fetch_all(self, query: str, params: tuple[Any, ...]) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(conn.execute(query, params).fetchall())

    def _insert_evidence_event(
        self,
        conn: sqlite3.Connection,
        *,
        event_id: str,
        target_type: str,
        target_id: str,
        outcome: str,
        contradiction: bool,
    ) -> bool:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO evidence_events(event_id, target_type, target_id, outcome, contradiction, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, target_type, target_id, outcome, 1 if contradiction else 0, utc_now()),
        )
        return cursor.rowcount == 1

    def _record_repair_strategy_event(
        self,
        conn: sqlite3.Connection,
        *,
        failure_id: str,
        strategy: str,
        result: str,
        strategy_signature: str,
    ) -> None:
        failure = conn.execute("SELECT normalized_signature, error_category FROM failures WHERE failure_id = ?", (failure_id,)).fetchone()
        problem_signature = (failure["normalized_signature"] if failure else None) or (failure["error_category"] if failure else "unknown_failure")
        existing = conn.execute("SELECT * FROM repair_strategies WHERE strategy_signature = ?", (strategy_signature,)).fetchone()
        now = utc_now()
        success_increment = 1 if result == "success" else 0
        failure_increment = 1 if result in {"invalid", "exhausted", "failure"} else 0
        if existing is None:
            attempts = 1
            successes = success_increment
            failures = failure_increment
            confidence = calculate_confidence(success_count=successes, failure_count=failures)
            status = promote_status(success_count=successes, failure_count=failures).value
            conn.execute(
                """
                INSERT INTO repair_strategies (
                    strategy_signature, problem_signature, strategy, attempts, successes,
                    failures, confidence_score, status, created_at, last_used_at,
                    last_success_at, last_failure_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    strategy_signature,
                    problem_signature,
                    strategy,
                    attempts,
                    successes,
                    failures,
                    confidence,
                    status,
                    now,
                    now,
                    now if success_increment else None,
                    now if failure_increment else None,
                ),
            )
            return
        attempts = existing["attempts"] + 1
        successes = existing["successes"] + success_increment
        failures = existing["failures"] + failure_increment
        confidence = calculate_confidence(success_count=successes, failure_count=failures)
        status = promote_status(success_count=successes, failure_count=failures, current_status=existing["status"]).value
        conn.execute(
            """
            UPDATE repair_strategies
            SET attempts = ?, successes = ?, failures = ?, confidence_score = ?, status = ?,
                last_used_at = ?, last_success_at = CASE WHEN ? THEN ? ELSE last_success_at END,
                last_failure_at = CASE WHEN ? THEN ? ELSE last_failure_at END
            WHERE strategy_signature = ?
            """,
            (
                attempts,
                successes,
                failures,
                confidence,
                status,
                now,
                success_increment,
                now,
                failure_increment,
                now,
                strategy_signature,
            ),
        )


def _sanitize(value: str | None) -> str | None:
    if value is None:
        return None
    sanitized = value
    for marker in ["OPENAI_API_KEY", "Authorization:", "Bearer "]:
        sanitized = sanitized.replace(marker, "[redacted]")
    return sanitized


def _json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    value = json.loads(raw)
    return value if isinstance(value, list) else []


def _json_dict(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    value = json.loads(raw)
    return value if isinstance(value, dict) else {}


def _signature_from_fragment(plan_fragment_json: str, *, fallback: str) -> str:
    try:
        return normalize_pattern_signature(json.loads(plan_fragment_json))
    except Exception:
        return fallback


def _failure_from_row(row: sqlite3.Row) -> FailureRecord:
    return FailureRecord(
        failure_id=row["failure_id"],
        timestamp=row["timestamp"],
        prompt=row["prompt"],
        parsed_spec_json=row["parsed_spec_json"],
        operation_plan_json=row["operation_plan_json"],
        failing_operation_id=row["failing_operation_id"],
        error_category=FailureCategory(row["error_category"]),
        error_message=row["error_message"],
        relevant_parameters_json=row["relevant_parameters_json"],
        repair_attempt_count=row["repair_attempt_count"],
        resolved=bool(row["resolved"]),
        successful_repair_id=row["successful_repair_id"],
        normalized_signature=row["normalized_signature"],
    )


def _lesson_from_row(row: sqlite3.Row) -> LessonRecord:
    return LessonRecord(
        lesson_id=row["lesson_id"],
        title=row["title"],
        description=row["description"],
        problem_signature=row["problem_signature"],
        applicable_part_types=_json_list(row["applicable_part_types"]),
        applicable_operation_types=_json_list(row["applicable_operation_types"]),
        known_bad_pattern=row["known_bad_pattern"],
        recommended_pattern=row["recommended_pattern"],
        evidence_count=row["evidence_count"],
        success_count=row["success_count"],
        failure_count=row["failure_count"],
        confidence=row["confidence"],
        created_at=row["created_at"],
        status=EvidenceStatus(row["status"]),
        confidence_score=row["confidence_score"],
        last_used_at=row["last_used_at"],
        last_verified_at=row["last_verified_at"],
        source_capability_versions=_json_dict(row["source_capability_versions"]),
        source_engine_version=row["source_engine_version"],
        contradiction_count=row["contradiction_count"],
        superseded_by_lesson_id=row["superseded_by_lesson_id"],
        source_type=row["source_type"],
        source_ids=_json_list(row["source_ids"]),
        regression_ids=_json_list(row["regression_ids"]),
        manually_overridden=bool(row["manually_overridden"]),
    )


def _pattern_from_row(row: sqlite3.Row) -> SuccessfulPatternRecord:
    return SuccessfulPatternRecord(
        pattern_id=row["pattern_id"],
        name=row["name"],
        description=row["description"],
        applicable_operation_types=_json_list(row["applicable_operation_types"]),
        operation_signature=row["operation_signature"],
        part_type=row["part_type"],
        input_signature=row["input_signature"],
        plan_fragment_json=row["plan_fragment_json"],
        validation_notes=row["validation_notes"],
        usage_count=row["usage_count"],
        success_count=row["success_count"],
        failure_count=row["failure_count"],
        confidence_score=row["confidence_score"],
        status=EvidenceStatus(row["status"]),
        created_at=row["created_at"],
        last_used_at=row["last_used_at"],
        last_verified_at=row["last_verified_at"],
        source_capabilities=_json_dict(row["source_capabilities"]),
        regression_ids=_json_list(row["regression_ids"]),
        manually_overridden=bool(row["manually_overridden"]),
        last_success_at=row["last_success_at"],
    )


def _repair_from_row(row: sqlite3.Row) -> RepairAttemptRecord:
    return RepairAttemptRecord(
        repair_id=row["repair_id"],
        failure_id=row["failure_id"],
        attempt_number=row["attempt_number"],
        repaired_plan_json=row["repaired_plan_json"],
        strategy=row["strategy"],
        result=row["result"],
        error_message=row["error_message"],
        timestamp=row["timestamp"],
        strategy_signature=row["strategy_signature"],
    )


def _repair_strategy_from_row(row: sqlite3.Row) -> RepairStrategyRecord:
    return RepairStrategyRecord(
        strategy_signature=row["strategy_signature"],
        problem_signature=row["problem_signature"],
        strategy=row["strategy"],
        attempts=row["attempts"],
        successes=row["successes"],
        failures=row["failures"],
        confidence_score=row["confidence_score"],
        status=EvidenceStatus(row["status"]),
        created_at=row["created_at"],
        last_used_at=row["last_used_at"],
        last_success_at=row["last_success_at"],
        last_failure_at=row["last_failure_at"],
    )
