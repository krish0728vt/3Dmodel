from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from config import CONFIG
from exports.models import ExportFormat, ExportHistoryRecord, ExportSourceType


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class ExportStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else CONFIG.learning_db_path.parent / "shah_exports.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS exports (
                    export_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    revision_id TEXT,
                    format TEXT NOT NULL,
                    path TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    checksum_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )

    def add_record(
        self,
        *,
        source_type: ExportSourceType,
        source_id: str,
        revision: int,
        revision_id: str | None,
        format: ExportFormat,
        path: str,
        filename: str,
        size_bytes: int,
        checksum_sha256: str,
        metadata: dict[str, object] | None = None,
    ) -> ExportHistoryRecord:
        record = ExportHistoryRecord(
            export_id=f"exp_{uuid.uuid4().hex[:12]}",
            source_type=source_type,
            source_id=source_id,
            revision=revision,
            revision_id=revision_id,
            format=format,
            path=path,
            filename=filename,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            created_at=utc_now(),
            metadata=metadata or {},
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO exports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.export_id,
                    record.source_type.value,
                    record.source_id,
                    record.revision,
                    record.revision_id,
                    record.format.value,
                    record.path,
                    record.filename,
                    record.size_bytes,
                    record.checksum_sha256,
                    record.created_at,
                    json.dumps(record.metadata, sort_keys=True),
                ),
            )
        return record

    def get(self, export_id: str) -> ExportHistoryRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM exports WHERE export_id = ?", (export_id,)).fetchone()
        return _record_from_row(row) if row else None

    def list_for_source(self, source_type: ExportSourceType, source_id: str) -> list[ExportHistoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exports WHERE source_type = ? AND source_id = ? ORDER BY created_at DESC",
                (source_type.value, source_id),
            ).fetchall()
        return [_record_from_row(row) for row in rows]


def _record_from_row(row: sqlite3.Row) -> ExportHistoryRecord:
    return ExportHistoryRecord(
        export_id=row["export_id"],
        source_type=ExportSourceType(row["source_type"]),
        source_id=row["source_id"],
        revision=row["revision"],
        revision_id=row["revision_id"],
        format=ExportFormat(row["format"]),
        path=row["path"],
        filename=row["filename"],
        size_bytes=row["size_bytes"],
        checksum_sha256=row["checksum_sha256"],
        created_at=row["created_at"],
        metadata=json.loads(row["metadata_json"]),
    )
