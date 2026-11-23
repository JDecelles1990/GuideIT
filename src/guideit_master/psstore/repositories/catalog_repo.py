"""SQLite catalog and run history persistence for PowerShellStore."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guideit_master.paths import get_psstore_db_path


def _build_params_text(params: list[dict[str, Any]]) -> str:
    """Build FTS-searchable token text from .PSSTORE_META parameter names."""
    tokens: list[str] = []
    for param in params or []:
        name = str(param.get("name", "")).strip()
        if not name:
            continue
        if name not in tokens:
            tokens.append(name)
        for word in re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).split():
            if word and word not in tokens:
                tokens.append(word)
    return " ".join(tokens)


@dataclass
class ScriptRecord:
    relative_path: str
    category: str
    filename: str
    title: str
    synopsis: str = ""
    risk_level: str = "read_only"  # 'read_only' | 'remediation'
    ps_edition: str = "Desktop"  # 'Desktop' | 'Core'
    requires_admin: bool = False
    timeout_seconds: int = 30
    output_mode: str = "json"
    params: list[dict[str, Any]] = field(default_factory=list)
    sha256: str = ""
    id: int | None = None
    updated_at: str = ""
    source: str = "bundled"
    file_path: str = ""

    @property
    def params_json(self) -> str:
        return json.dumps(self.params)


@dataclass
class RunHistoryRecord:
    script_id: int
    duration_ms: int
    exit_code: int
    status: str  # 'pass', 'warning', 'fail', 'error', 'timeout'
    summary: str = ""
    parameters_json: str = "{}"
    raw_output: str = ""
    json_payload: str = ""
    executed_at: str = ""
    id: int | None = None


class CatalogRepo:
    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            self.db_path: Path | str = get_psstore_db_path()
        elif str(db_path) == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(db_path)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS scripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    relative_path TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    title TEXT NOT NULL,
                    synopsis TEXT,
                    risk_level TEXT NOT NULL DEFAULT 'read_only',
                    ps_edition TEXT NOT NULL DEFAULT 'Desktop',
                    requires_admin INTEGER NOT NULL DEFAULT 0,
                    timeout_seconds INTEGER NOT NULL DEFAULT 30,
                    output_mode TEXT NOT NULL DEFAULT 'json',
                    params_json TEXT,
                    sha256 TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source TEXT NOT NULL DEFAULT 'bundled',
                    file_path TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_scripts_category ON scripts(category);
                CREATE INDEX IF NOT EXISTS idx_scripts_risk ON scripts(risk_level);

                CREATE TABLE IF NOT EXISTS run_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    script_id INTEGER NOT NULL,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration_ms INTEGER NOT NULL,
                    exit_code INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT,
                    parameters_json TEXT,
                    raw_output TEXT,
                    json_payload TEXT,
                    FOREIGN KEY(script_id) REFERENCES scripts(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_run_history_script ON run_history(script_id);

                CREATE VIRTUAL TABLE IF NOT EXISTS scripts_fts USING fts5(
                    relative_path,
                    title,
                    category,
                    synopsis,
                    filename,
                    params_text,
                    tokenize = "unicode61 remove_diacritics 2"
                );
                """
            )
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(scripts)").fetchall()}
            if "source" not in cols:
                conn.execute("ALTER TABLE scripts ADD COLUMN source TEXT NOT NULL DEFAULT 'bundled'")
            if "file_path" not in cols:
                conn.execute("ALTER TABLE scripts ADD COLUMN file_path TEXT NOT NULL DEFAULT ''")
            scripts_count = int(conn.execute("SELECT COUNT(*) FROM scripts").fetchone()[0])
            fts_count = int(conn.execute("SELECT COUNT(*) FROM scripts_fts").fetchone()[0])
            if scripts_count != fts_count:
                conn.execute("DELETE FROM scripts_fts")
                if scripts_count > 0:
                    existing_rows = conn.execute("SELECT * FROM scripts").fetchall()
                    for row in existing_rows:
                        self._upsert_fts_row(conn, self._row_to_script(row))

    def _row_to_script(self, row: sqlite3.Row) -> ScriptRecord:
        params: list[dict[str, Any]] = []
        if row["params_json"]:
            try:
                params = json.loads(row["params_json"])
            except json.JSONDecodeError:
                params = []

        row_keys = set(row.keys())
        return ScriptRecord(
            id=row["id"],
            relative_path=row["relative_path"],
            category=row["category"],
            filename=row["filename"],
            title=row["title"],
            synopsis=row["synopsis"] or "",
            risk_level=row["risk_level"],
            ps_edition=row["ps_edition"],
            requires_admin=bool(row["requires_admin"]),
            timeout_seconds=row["timeout_seconds"],
            output_mode=row["output_mode"],
            params=params,
            sha256=row["sha256"],
            updated_at=str(row["updated_at"]),
            source=row["source"] if "source" in row_keys else "bundled",
            file_path=row["file_path"] if "file_path" in row_keys else "",
        )

    def _upsert_fts_row(self, conn: sqlite3.Connection, script: ScriptRecord) -> None:
        norm_rel = script.relative_path.replace("\\", "/")
        conn.execute("DELETE FROM scripts_fts WHERE relative_path = ?", (norm_rel,))
        conn.execute(
            """
            INSERT INTO scripts_fts (
                relative_path, title, category, synopsis, filename, params_text
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                norm_rel,
                script.title,
                script.category,
                script.synopsis or "",
                script.filename,
                _build_params_text(script.params),
            ),
        )

    def upsert_script(self, script: ScriptRecord) -> int:
        norm_rel = script.relative_path.replace("\\", "/")
        query = """
        INSERT INTO scripts (
            relative_path, category, filename, title, synopsis,
            risk_level, ps_edition, requires_admin, timeout_seconds,
            output_mode, params_json, sha256, source, file_path, updated_at
        ) VALUES (
            :relative_path, :category, :filename, :title, :synopsis,
            :risk_level, :ps_edition, :requires_admin, :timeout_seconds,
            :output_mode, :params_json, :sha256, :source, :file_path, CURRENT_TIMESTAMP
        )
        ON CONFLICT(relative_path) DO UPDATE SET
            category = excluded.category,
            filename = excluded.filename,
            title = excluded.title,
            synopsis = excluded.synopsis,
            risk_level = excluded.risk_level,
            ps_edition = excluded.ps_edition,
            requires_admin = excluded.requires_admin,
            timeout_seconds = excluded.timeout_seconds,
            output_mode = excluded.output_mode,
            params_json = excluded.params_json,
            sha256 = excluded.sha256,
            source = excluded.source,
            file_path = excluded.file_path,
            updated_at = CURRENT_TIMESTAMP;
        """
        params = {
            "relative_path": norm_rel,
            "category": script.category,
            "filename": script.filename,
            "title": script.title,
            "synopsis": script.synopsis,
            "risk_level": script.risk_level,
            "ps_edition": script.ps_edition,
            "requires_admin": 1 if script.requires_admin else 0,
            "timeout_seconds": script.timeout_seconds,
            "output_mode": script.output_mode,
            "params_json": json.dumps(script.params),
            "sha256": script.sha256,
            "source": script.source or "bundled",
            "file_path": script.file_path or "",
        }

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            self._upsert_fts_row(conn, script)
            if script.id:
                return script.id
            row = conn.execute(
                "SELECT id FROM scripts WHERE relative_path = ?",
                (norm_rel,),
            ).fetchone()
            return row["id"] if row else cursor.lastrowid

    def get_script_by_id(self, script_id: int) -> ScriptRecord | None:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM scripts WHERE id = ?", (script_id,)).fetchone()
            if row:
                return self._row_to_script(row)
        return None

    def get_script_by_path(self, relative_path: str) -> ScriptRecord | None:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM scripts WHERE relative_path = ?",
                (relative_path.replace("\\", "/"),),
            ).fetchone()
            if row:
                return self._row_to_script(row)
        return None

    def get_scripts_by_paths(self, relative_paths: list[str]) -> dict[str, ScriptRecord]:
        normalized = [p.replace("\\", "/") for p in relative_paths if p]
        if not normalized:
            return {}
        unique_paths = list(dict.fromkeys(normalized))
        placeholders = ",".join("?" for _ in unique_paths)
        with self._get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM scripts WHERE relative_path IN ({placeholders})",
                unique_paths,
            ).fetchall()
        return {rec.relative_path: rec for rec in (self._row_to_script(r) for r in rows)}

    def search_scripts_fts(
        self,
        fts_query: str,
        *,
        limit: int = 20,
    ) -> list[tuple[ScriptRecord, float]]:
        cleaned = fts_query.strip()
        if not cleaned:
            return []
        sql = """
        SELECT
            s.*,
            -bm25(scripts_fts, 2.0, 10.0, 4.0, 6.0, 8.0, 3.0) AS fts_score
        FROM scripts_fts
        JOIN scripts s ON s.relative_path = scripts_fts.relative_path
        WHERE scripts_fts MATCH ?
        ORDER BY fts_score DESC, s.title ASC
        """
        args: list[Any] = [cleaned]
        if limit > 0:
            sql += " LIMIT ?"
            args.append(limit)
        try:
            with self._get_connection() as conn:
                rows = conn.execute(sql, args).fetchall()
        except sqlite3.OperationalError:
            return []
        return [(self._row_to_script(row), max(0.0, float(row["fts_score"]))) for row in rows]

    def get_all_scripts(
        self,
        category: str | None = None,
        search: str | None = None,
        risk_level: str | None = None,
        ps_edition: str | None = None,
        source: str | None = None,
    ) -> list[ScriptRecord]:
        query = "SELECT * FROM scripts WHERE 1=1"
        args: list[Any] = []

        if category and category != "All":
            query += " AND category = ?"
            args.append(category)

        if risk_level and risk_level != "All":
            query += " AND risk_level = ?"
            args.append(risk_level)

        if ps_edition and ps_edition != "All":
            query += " AND ps_edition = ?"
            args.append(ps_edition)

        if source and source != "All":
            query += " AND source = ?"
            args.append(source)

        if search:
            like_term = f"%{search.strip()}%"
            query += " AND (title LIKE ? OR synopsis LIKE ? OR filename LIKE ?)"
            args.extend([like_term, like_term, like_term])

        query += " ORDER BY category ASC, title ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, args).fetchall()
            return [self._row_to_script(r) for r in rows]

    def get_categories_with_counts(self) -> list[dict[str, Any]]:
        query = """
        SELECT category, COUNT(*) as count
        FROM scripts
        GROUP BY category
        ORDER BY category ASC
        """
        with self._get_connection() as conn:
            rows = conn.execute(query).fetchall()
            return [{"category": r["category"], "count": r["count"]} for r in rows]

    def delete_missing_scripts(self, current_relative_paths: list[str]) -> int:
        normalized_paths = [p.replace("\\", "/") for p in current_relative_paths]
        with self._get_connection() as conn:
            if not normalized_paths:
                conn.execute("DELETE FROM scripts_fts")
                cursor = conn.execute("DELETE FROM scripts")
                return cursor.rowcount

            placeholders = ",".join("?" for _ in normalized_paths)
            conn.execute(
                f"DELETE FROM scripts_fts WHERE relative_path NOT IN ({placeholders})",
                normalized_paths,
            )
            query = f"DELETE FROM scripts WHERE relative_path NOT IN ({placeholders})"
            cursor = conn.execute(query, normalized_paths)
            return cursor.rowcount

    def log_run(self, record: RunHistoryRecord) -> int:
        query = """
        INSERT INTO run_history (
            script_id, duration_ms, exit_code, status,
            summary, parameters_json, raw_output, json_payload, executed_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
        )
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                query,
                (
                    record.script_id,
                    record.duration_ms,
                    record.exit_code,
                    record.status,
                    record.summary,
                    record.parameters_json,
                    record.raw_output,
                    record.json_payload,
                ),
            )
            return cursor.lastrowid

    def get_history_for_script(self, script_id: int, limit: int = 50) -> list[RunHistoryRecord]:
        query = """
        SELECT * FROM run_history
        WHERE script_id = ?
        ORDER BY executed_at DESC
        LIMIT ?
        """
        with self._get_connection() as conn:
            rows = conn.execute(query, (script_id, limit)).fetchall()
            return [
                RunHistoryRecord(
                    id=r["id"],
                    script_id=r["script_id"],
                    duration_ms=r["duration_ms"],
                    exit_code=r["exit_code"],
                    status=r["status"],
                    summary=r["summary"] or "",
                    parameters_json=r["parameters_json"] or "{}",
                    raw_output=r["raw_output"] or "",
                    json_payload=r["json_payload"] or "",
                    executed_at=str(r["executed_at"]),
                )
                for r in rows
            ]
