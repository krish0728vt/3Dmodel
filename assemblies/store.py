from __future__ import annotations

import json
import sqlite3
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from config import CONFIG
from assemblies.models import AssemblyComponent, AssemblyRecord, AssemblyRevisionRecord, AssemblyStatus


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class AssemblyStore:
    """SQLite-backed immutable assembly revision store."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else CONFIG.learning_db_path.parent / "shah_assemblies.db"
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
                CREATE TABLE IF NOT EXISTS assemblies (
                    assembly_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    current_revision INTEGER NOT NULL DEFAULT 0,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS assembly_revisions (
                    revision_id TEXT PRIMARY KEY,
                    assembly_id TEXT NOT NULL,
                    revision_number INTEGER NOT NULL,
                    parent_revision_id TEXT,
                    timestamp TEXT NOT NULL,
                    user_instruction TEXT NOT NULL,
                    change_summary TEXT NOT NULL,
                    components_json TEXT NOT NULL,
                    manifest_path TEXT,
                    UNIQUE(assembly_id, revision_number)
                );
                """
            )
            _ensure_column(conn, "assemblies", "status", "TEXT DEFAULT 'active'")
            _ensure_column(conn, "assemblies", "archived_at", "TEXT")
            _ensure_column(conn, "assemblies", "last_opened_at", "TEXT")

    def create_assembly(self, *, name: str, notes: str | None = None) -> AssemblyRecord:
        now = utc_now()
        assembly = AssemblyRecord(
            assembly_id=f"asm_{uuid.uuid4().hex[:10]}",
            name=name,
            created_at=now,
            updated_at=now,
            current_revision=0,
            notes=notes,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO assemblies (
                    assembly_id, name, created_at, updated_at, current_revision,
                    notes, status, archived_at, last_opened_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assembly.assembly_id,
                    assembly.name,
                    assembly.created_at,
                    assembly.updated_at,
                    assembly.current_revision,
                    assembly.notes,
                    assembly.status.value,
                    assembly.archived_at,
                    assembly.last_opened_at,
                ),
            )
        return assembly

    def list_assemblies(self, *, search: str | None = None, status: str = "active", sort: str = "recently_updated") -> list[AssemblyRecord]:
        query = "SELECT * FROM assemblies"
        clauses: list[str] = []
        params: list[object] = []
        normalized_status = status.lower()
        if normalized_status == "active":
            clauses.append("status = ?")
            params.append(AssemblyStatus.ACTIVE.value)
        elif normalized_status == "archived":
            clauses.append("status = ?")
            params.append(AssemblyStatus.ARCHIVED.value)
        elif normalized_status != "all":
            raise ValueError(f"Unsupported assembly status filter: {status}")
        if search:
            needle = f"%{search.strip().lower()}%"
            clauses.append("(LOWER(name) LIKE ? OR LOWER(assembly_id) LIKE ?)")
            params.extend([needle, needle])
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        order_by = {
            "recently_updated": "updated_at DESC",
            "recently_opened": "COALESCE(last_opened_at, updated_at) DESC",
            "name": "LOWER(name) ASC",
            "created": "created_at DESC",
        }.get(sort, "updated_at DESC")
        query += f" ORDER BY {order_by}"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_assembly_from_row(row) for row in rows]

    def get_assembly(self, assembly_id: str) -> AssemblyRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM assemblies WHERE assembly_id = ?", (assembly_id,)).fetchone()
        return _assembly_from_row(row) if row else None

    def add_revision(
        self,
        *,
        assembly_id: str,
        components: list[AssemblyComponent],
        user_instruction: str,
        change_summary: str,
        parent_revision_id: str | None = None,
        manifest_path: str | None = None,
        make_current: bool = True,
    ) -> AssemblyRevisionRecord:
        if self.get_assembly(assembly_id) is None:
            raise ValueError(f"Unknown assembly: {assembly_id}")
        revision_number = self.next_revision_number(assembly_id)
        revision = AssemblyRevisionRecord(
            revision_id=f"asmrev_{uuid.uuid4().hex[:12]}",
            assembly_id=assembly_id,
            revision_number=revision_number,
            parent_revision_id=parent_revision_id,
            timestamp=utc_now(),
            user_instruction=_sanitize(user_instruction),
            change_summary=change_summary,
            components=components,
            manifest_path=manifest_path,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO assembly_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    revision.revision_id,
                    revision.assembly_id,
                    revision.revision_number,
                    revision.parent_revision_id,
                    revision.timestamp,
                    revision.user_instruction,
                    revision.change_summary,
                    json.dumps([component.model_dump(mode="json") for component in components], sort_keys=True),
                    revision.manifest_path,
                ),
            )
            if make_current:
                conn.execute(
                    "UPDATE assemblies SET current_revision = ?, updated_at = ? WHERE assembly_id = ?",
                    (revision.revision_number, revision.timestamp, assembly_id),
                )
        return revision

    def next_revision_number(self, assembly_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM assembly_revisions WHERE assembly_id = ?",
                (assembly_id,),
            ).fetchone()
        return int(row[0])

    def history(self, assembly_id: str) -> list[AssemblyRevisionRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM assembly_revisions WHERE assembly_id = ? ORDER BY revision_number",
                (assembly_id,),
            ).fetchall()
        return [_revision_from_row(row) for row in rows]

    def get_revision(self, assembly_id: str, revision_number: int) -> AssemblyRevisionRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM assembly_revisions WHERE assembly_id = ? AND revision_number = ?",
                (assembly_id, revision_number),
            ).fetchone()
        return _revision_from_row(row) if row else None

    def current_revision(self, assembly_id: str) -> AssemblyRevisionRecord | None:
        assembly = self.get_assembly(assembly_id)
        if assembly is None or assembly.current_revision == 0:
            return None
        return self.get_revision(assembly_id, assembly.current_revision)

    def set_current_revision(self, assembly_id: str, revision_number: int) -> AssemblyRevisionRecord:
        revision = self.get_revision(assembly_id, revision_number)
        if revision is None:
            raise ValueError(f"Revision {revision_number} does not exist for {assembly_id}.")
        with self._connect() as conn:
            conn.execute(
                "UPDATE assemblies SET current_revision = ?, updated_at = ? WHERE assembly_id = ?",
                (revision_number, utc_now(), assembly_id),
            )
        return revision

    def rename_assembly(self, assembly_id: str, name: str) -> AssemblyRecord:
        if self.get_assembly(assembly_id) is None:
            raise ValueError(f"Unknown assembly: {assembly_id}")
        with self._connect() as conn:
            conn.execute("UPDATE assemblies SET name = ?, updated_at = ? WHERE assembly_id = ?", (name, utc_now(), assembly_id))
        return self.get_assembly(assembly_id)  # type: ignore[return-value]

    def mark_opened(self, assembly_id: str) -> AssemblyRecord:
        if self.get_assembly(assembly_id) is None:
            raise ValueError(f"Unknown assembly: {assembly_id}")
        with self._connect() as conn:
            conn.execute("UPDATE assemblies SET last_opened_at = ? WHERE assembly_id = ?", (utc_now(), assembly_id))
        return self.get_assembly(assembly_id)  # type: ignore[return-value]

    def archive_assembly(self, assembly_id: str) -> AssemblyRecord:
        return self._set_assembly_status(assembly_id, AssemblyStatus.ARCHIVED)

    def unarchive_assembly(self, assembly_id: str) -> AssemblyRecord:
        return self._set_assembly_status(assembly_id, AssemblyStatus.ACTIVE)

    def duplicate_assembly(self, assembly_id: str, *, revision_number: int | None = None, name: str | None = None) -> tuple[AssemblyRecord, AssemblyRevisionRecord]:
        source = self.get_assembly(assembly_id)
        if source is None:
            raise ValueError(f"Unknown assembly: {assembly_id}")
        revision = self.current_revision(assembly_id) if revision_number is None else self.get_revision(assembly_id, revision_number)
        if revision is None:
            raise ValueError("Source assembly revision not found.")
        duplicate = self.create_assembly(name=name or f"{source.name} Copy", notes=source.notes)
        new_revision = self.add_revision(
            assembly_id=duplicate.assembly_id,
            components=revision.components,
            user_instruction=f"Duplicated from {assembly_id} revision {revision.revision_number}",
            change_summary=f"Duplicated from {source.name}",
        )
        return duplicate, new_revision

    def delete_assembly(self, assembly_id: str, *, delete_outputs: bool = True) -> dict[str, int]:
        if self.get_assembly(assembly_id) is None:
            raise ValueError(f"Unknown assembly: {assembly_id}")
        revision_count = len(self.history(assembly_id))
        with self._connect() as conn:
            conn.execute("DELETE FROM assembly_revisions WHERE assembly_id = ?", (assembly_id,))
            conn.execute("DELETE FROM assemblies WHERE assembly_id = ?", (assembly_id,))
        file_count = 0
        if delete_outputs:
            target = Path("outputs") / "assemblies" / assembly_id
            root = Path("outputs") / "assemblies"
            try:
                target.resolve().relative_to(root.resolve())
            except ValueError as exc:
                raise ValueError(f"Refusing to delete unsafe assembly output path: {target}") from exc
            if target.exists():
                file_count = sum(1 for item in target.rglob("*") if item.is_file())
                shutil.rmtree(target)
        return {"revision_count": revision_count, "file_count": file_count}

    def _set_assembly_status(self, assembly_id: str, status: AssemblyStatus) -> AssemblyRecord:
        if self.get_assembly(assembly_id) is None:
            raise ValueError(f"Unknown assembly: {assembly_id}")
        now = utc_now()
        archived_at = now if status == AssemblyStatus.ARCHIVED else None
        with self._connect() as conn:
            conn.execute(
                "UPDATE assemblies SET status = ?, archived_at = ?, updated_at = ? WHERE assembly_id = ?",
                (status.value, archived_at, now, assembly_id),
            )
        return self.get_assembly(assembly_id)  # type: ignore[return-value]


def _assembly_from_row(row: sqlite3.Row) -> AssemblyRecord:
    return AssemblyRecord(
        assembly_id=row["assembly_id"],
        name=row["name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        current_revision=row["current_revision"],
        notes=row["notes"],
        status=AssemblyStatus(_row_value(row, "status") or AssemblyStatus.ACTIVE.value),
        archived_at=_row_value(row, "archived_at"),
        last_opened_at=_row_value(row, "last_opened_at"),
    )


def _revision_from_row(row: sqlite3.Row) -> AssemblyRevisionRecord:
    return AssemblyRevisionRecord(
        revision_id=row["revision_id"],
        assembly_id=row["assembly_id"],
        revision_number=row["revision_number"],
        parent_revision_id=row["parent_revision_id"],
        timestamp=row["timestamp"],
        user_instruction=row["user_instruction"],
        change_summary=row["change_summary"],
        components=[AssemblyComponent.model_validate(item) for item in json.loads(row["components_json"])],
        manifest_path=row["manifest_path"],
    )


def _sanitize(value: str | None) -> str:
    if value is None:
        return ""
    sanitized = value
    for marker in ["OPENAI_API_KEY", "Authorization:", "Bearer "]:
        sanitized = sanitized.replace(marker, "[redacted]")
    return sanitized


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _row_value(row: sqlite3.Row, column: str) -> str | None:
    return row[column] if column in row.keys() else None
