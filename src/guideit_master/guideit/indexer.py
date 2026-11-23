"""Atomic SQLite FTS5 index builder for GuideIT playbooks."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from guideit_master.guideit.models import IndexStats, Playbook
from guideit_master.guideit.validator import load_playbook_file
from guideit_master.paths import get_bundle_dir, get_guideit_db_path, get_playbooks_dir

DEFAULT_DB_RELPATH = Path("data/guideit.db")
SCHEMA_VERSION = "2"


def _discover_playbook_files(root_dir: Path) -> list[Path]:
    """Return sorted playbook Markdown files under playbooks/01..09."""
    playbooks_dir = get_playbooks_dir(root_dir)
    if not playbooks_dir.is_dir():
        return []
    files: list[Path] = []
    for subdir in sorted(playbooks_dir.iterdir()):
        if not subdir.is_dir():
            continue
        for md_file in sorted(subdir.glob("*.md")):
            if md_file.name.lower() == "readme.md":
                continue
            files.append(md_file)
    return files


def _compute_source_hash(root_dir: Path, files: list[Path]) -> str:
    """Compute a deterministic SHA-256 digest of all indexed playbook files."""
    hasher = hashlib.sha256()
    for path in files:
        rel = path.relative_to(root_dir).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def build_index(root_dir: Path | None = None, db_path: Path | None = None) -> IndexStats:
    """Parse all playbooks and atomically rebuild the SQLite FTS5 database."""
    resolved_root = (root_dir if root_dir is not None else get_bundle_dir()).resolve()
    target_db = db_path.resolve() if db_path is not None else get_guideit_db_path()
    target_db.parent.mkdir(parents=True, exist_ok=True)

    files = _discover_playbook_files(resolved_root)
    playbooks: list[Playbook] = [load_playbook_file(resolved_root, f) for f in files]
    source_hash = _compute_source_hash(resolved_root, files)
    built_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    tmp_db = target_db.with_name(f".{target_db.name}.tmp.{os.getpid()}")
    if tmp_db.exists():
        tmp_db.unlink()

    try:
        with closing(sqlite3.connect(str(tmp_db))) as conn:
            conn.execute("PRAGMA journal_mode = DELETE")
            conn.executescript(
                """
                CREATE TABLE index_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE playbooks (
                    id TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    subcategory TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    requires_admin INTEGER NOT NULL,
                    last_verified TEXT NOT NULL,
                    os_json TEXT NOT NULL,
                    environment_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    error_codes_json TEXT NOT NULL,
                    keywords_en_json TEXT NOT NULL,
                    keywords_fr_json TEXT NOT NULL,
                    tools_json TEXT NOT NULL,
                    related_ids_json TEXT NOT NULL,
                    triage_summary TEXT NOT NULL,
                    body_markdown TEXT NOT NULL
                );

                CREATE VIRTUAL TABLE playbooks_fts USING fts5(
                    id,
                    error_codes,
                    tags,
                    keywords_en,
                    keywords_fr,
                    title,
                    tools,
                    body,
                    tokenize = "unicode61 remove_diacritics 2"
                );
                """
            )

            conn.executemany(
                "INSERT INTO index_meta (key, value) VALUES (?, ?)",
                [
                    ("schema_version", SCHEMA_VERSION),
                    ("built_at", built_at),
                    ("playbook_count", str(len(playbooks))),
                    ("source_hash", source_hash),
                ],
            )

            for pb in playbooks:
                conn.execute(
                    """
                    INSERT INTO playbooks (
                        id, path, domain, subject, subcategory, title, tier, risk_level,
                        requires_admin, last_verified, os_json, environment_json,
                        tags_json, error_codes_json, keywords_en_json, keywords_fr_json,
                        tools_json, related_ids_json, triage_summary, body_markdown
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pb.id,
                        pb.path,
                        pb.domain,
                        pb.subject,
                        pb.subcategory,
                        pb.title,
                        pb.tier,
                        pb.risk_level,
                        1 if pb.requires_admin else 0,
                        pb.last_verified,
                        json.dumps(pb.os, ensure_ascii=False),
                        json.dumps(pb.environment, ensure_ascii=False),
                        json.dumps(pb.tags, ensure_ascii=False),
                        json.dumps(pb.error_codes, ensure_ascii=False),
                        json.dumps(pb.keywords_en, ensure_ascii=False),
                        json.dumps(pb.keywords_fr, ensure_ascii=False),
                        json.dumps(pb.tools, ensure_ascii=False),
                        json.dumps(pb.related_ids, ensure_ascii=False),
                        pb.triage_summary,
                        pb.body_markdown,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO playbooks_fts (
                        id, error_codes, tags, keywords_en, keywords_fr, title, tools, body
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pb.id,
                        " ".join(pb.error_codes),
                        " ".join(pb.tags),
                        " | ".join(pb.keywords_en),
                        " | ".join(pb.keywords_fr),
                        pb.title,
                        " | ".join(pb.tools),
                        pb.body_markdown,
                    ),
                )

            conn.commit()

        os.replace(tmp_db, target_db)
    except Exception:
        if tmp_db.exists():
            tmp_db.unlink()
        raise

    return IndexStats(
        db_path=str(target_db),
        indexed_count=len(playbooks),
        built_at=built_at,
        source_hash=source_hash,
    )
