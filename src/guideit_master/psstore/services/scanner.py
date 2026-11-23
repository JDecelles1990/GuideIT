"""File-first .PSSTORE_META scanner and SHA-256 SQLite catalog sync."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guideit_master.paths import get_ps_scripts_dir, get_user_custom_scripts_dir, is_frozen
from guideit_master.psstore.repositories.catalog_repo import CatalogRepo, ScriptRecord

logger = logging.getLogger(__name__)


@dataclass
class ScanSummary:
    total_found: int = 0
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)


class ScriptScanner:
    def __init__(
        self,
        scripts_dir: Path | str | None = None,
        repo: CatalogRepo | None = None,
        user_scripts_dir: Path | str | None = None,
        include_user_scripts: bool | None = None,
    ) -> None:
        if scripts_dir is None:
            self.scripts_dir = get_ps_scripts_dir()
            default_include_user = True
        else:
            self.scripts_dir = Path(scripts_dir)
            default_include_user = False

        if user_scripts_dir is not None:
            resolved_user: Path | None = Path(user_scripts_dir)
        else:
            should_include = (
                include_user_scripts
                if include_user_scripts is not None
                else default_include_user
            )
            resolved_user = get_user_custom_scripts_dir() if should_include else None

        if resolved_user is not None and resolved_user.resolve() == self.scripts_dir.resolve():
            resolved_user = None

        self.user_scripts_dir: Path | None = resolved_user
        self.repo = repo if repo is not None else CatalogRepo()

    def resolve_script_path(self, relative_path: str) -> Path | None:
        """Resolve relative_path with user_scripts_dir taking precedence over scripts_dir."""
        rel_clean = relative_path.replace("\\", "/").lstrip("/")
        if not rel_clean:
            return None
        roots = [r for r in (self.user_scripts_dir, self.scripts_dir) if r is not None]
        for root in roots:
            root_resolved = root.resolve()
            try:
                candidate = (root_resolved / rel_clean).resolve()
            except OSError:
                continue
            if candidate.is_relative_to(root_resolved) and candidate.is_file():
                return candidate
        return None

    @staticmethod
    def derive_category(folder_name: str) -> str:
        """Derives human-readable category name from folder (e.g. 04_Printers_Devices -> Printers_Devices)."""
        clean = re.sub(r"^\d+_", "", folder_name)
        return clean.strip() or folder_name

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def parse_psstore_meta(content: str) -> tuple[dict[str, Any], str]:
        """Parses .PSSTORE_META JSON and .SYNOPSIS from PowerShell comment block (<# ... #>)."""
        synopsis = ""
        meta: dict[str, Any] = {}

        comment_blocks = re.findall(r"<#\s*(.*?)\s*#>", content, re.DOTALL)
        if not comment_blocks:
            return meta, synopsis

        for block in comment_blocks:
            if not synopsis:
                syn_match = re.search(
                    r"\.SYNOPSIS\s*\r?\n(.*?)(?=\r?\n\.[A-Z_]+|\Z)",
                    block,
                    re.IGNORECASE | re.DOTALL,
                )
                if syn_match:
                    synopsis = syn_match.group(1).strip()

            meta_match = re.search(
                r"\.PSSTORE_META\s*\r?\n(.*?)(?=\r?\n\.[A-Z_]+|\Z)",
                block,
                re.IGNORECASE | re.DOTALL,
            )
            if meta_match:
                raw_json = meta_match.group(1).strip()
                first_brace = raw_json.find("{")
                last_brace = raw_json.rfind("}")
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_str = raw_json[first_brace : last_brace + 1]
                    try:
                        meta = json.loads(json_str)
                    except json.JSONDecodeError:
                        cleaned = re.sub(r",\s*([\]}])", r"\1", json_str)
                        cleaned = re.sub(r"'([^']*)'", r'"\1"', cleaned)
                        try:
                            meta = json.loads(cleaned)
                        except Exception as e:
                            logger.warning("Failed to parse .PSSTORE_META JSON: %s", e)

        return meta, synopsis

    def scan_file(
        self,
        file_path: Path,
        *,
        root_dir: Path | None = None,
        source: str = "bundled",
    ) -> ScriptRecord:
        """Parses a single .ps1 file and returns a ScriptRecord."""
        base_dir = Path(root_dir) if root_dir is not None else self.scripts_dir
        relative_path = file_path.relative_to(base_dir).as_posix()
        if file_path.parent.resolve() == base_dir.resolve():
            folder_category = "Custom"
        else:
            folder_category = self.derive_category(file_path.parent.name)

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="utf-8-sig", errors="replace")

        sha256 = self.compute_sha256(file_path)
        meta, synopsis = self.parse_psstore_meta(content)

        category = meta.get("category", folder_category)
        title = meta.get("title", file_path.stem)
        risk_level = meta.get("risk_level", "read_only")
        ps_edition = meta.get("ps_edition", "Desktop")
        requires_admin = bool(meta.get("requires_admin", False))
        timeout_seconds = int(meta.get("timeout_seconds", 30))
        output_mode = meta.get("output_mode", "json")
        params = meta.get("params", [])

        if not isinstance(params, list):
            params = []

        return ScriptRecord(
            relative_path=relative_path,
            category=category,
            filename=file_path.name,
            title=title,
            synopsis=synopsis,
            risk_level=risk_level,
            ps_edition=ps_edition,
            requires_admin=requires_admin,
            timeout_seconds=timeout_seconds,
            output_mode=output_mode,
            params=params,
            sha256=sha256,
            source=source,
            file_path=str(file_path.resolve()),
        )

    def sync_catalog(self) -> ScanSummary:
        """Scans bundled and optional user_scripts directories, compares hashes, and syncs SQLite."""
        summary = ScanSummary()

        if (
            not self.scripts_dir.exists()
            and not is_frozen()
            and self.user_scripts_dir is None
        ):
            self.scripts_dir.mkdir(parents=True, exist_ok=True)
            return summary

        candidates: dict[str, tuple[Path, Path, str]] = {}
        if self.scripts_dir.is_dir():
            for ps1_file in sorted(self.scripts_dir.rglob("*.ps1")):
                rel_path = ps1_file.relative_to(self.scripts_dir).as_posix()
                candidates[rel_path] = (ps1_file, self.scripts_dir, "bundled")

        if self.user_scripts_dir is not None and self.user_scripts_dir.is_dir():
            for ps1_file in sorted(self.user_scripts_dir.rglob("*.ps1")):
                rel_path = ps1_file.relative_to(self.user_scripts_dir).as_posix()
                candidates[rel_path] = (ps1_file, self.user_scripts_dir, "user")

        found_paths = list(candidates.keys())

        for rel_path, (ps1_file, base_root, source) in candidates.items():
            summary.total_found += 1

            try:
                current_sha = self.compute_sha256(ps1_file)
                resolved_file_str = str(ps1_file.resolve())
                existing = self.repo.get_script_by_path(rel_path)

                if (
                    existing
                    and existing.sha256 == current_sha
                    and existing.source == source
                    and existing.file_path == resolved_file_str
                ):
                    summary.unchanged += 1
                    continue

                record = self.scan_file(ps1_file, root_dir=base_root, source=source)
                self.repo.upsert_script(record)

                if existing:
                    summary.updated += 1
                else:
                    summary.added += 1

            except Exception as e:
                logger.exception("Error processing script %s", rel_path)
                summary.errors.append((rel_path, str(e)))

        deleted_count = self.repo.delete_missing_scripts(found_paths)
        summary.deleted = deleted_count

        return summary
