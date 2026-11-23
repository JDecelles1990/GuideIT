"""Bidirectional Playbook <-> PowerShell Script cross-linking service."""

from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote

from guideit_master.guideit.search import get_playbook_by_id, get_playbook_script_links
from guideit_master.paths import get_guideit_db_path
from guideit_master.psstore.repositories.catalog_repo import CatalogRepo, ScriptRecord

_CANONICAL_SCRIPT_RELPATH_RE = re.compile(
    r"^[0-9]{2}_[A-Za-z0-9_]+/[A-Za-z0-9][A-Za-z0-9_-]*\.ps1$"
)


@dataclass(frozen=True, slots=True)
class LinkedScriptSummary:
    """UI-agnostic summary of a PowerShellStore script linked to a playbook."""

    relative_path: str
    title: str
    category: str
    risk_level: str
    requires_admin: bool
    synopsis: str
    ps_edition: str = "Desktop"
    timeout_seconds: int = 30
    exists: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LinkedPlaybookSummary:
    """UI-agnostic summary of a GuideIT playbook referencing a script."""

    id: str
    title: str
    domain: str
    subject: str
    tier: str
    risk_level: str
    path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def is_canonical_script_path(relative_path: str) -> bool:
    """Return True if relative_path strictly matches NN_Category/Verb-Noun.ps1."""
    return bool(_CANONICAL_SCRIPT_RELPATH_RE.match(relative_path.strip()))


def parse_psstore_uri(uri: str) -> tuple[str, dict[str, str]] | None:
    """Parse a psstore://NN_Category/Script.ps1?Param=Value URI safely.

    Returns (canonical_relative_path, query_params) or None if invalid.
    """
    cleaned = html.unescape(uri or "").strip()
    if not cleaned.lower().startswith("psstore://"):
        return None
    rest = cleaned[len("psstore://") :]
    rest = rest.split("#", 1)[0]
    if "?" in rest:
        raw_path, raw_query = rest.split("?", 1)
    else:
        raw_path, raw_query = rest, ""

    rel_path = unquote(raw_path).lstrip("/")
    if not is_canonical_script_path(rel_path):
        return None

    params: dict[str, str] = {}
    if raw_query:
        for key, val in parse_qsl(raw_query, keep_blank_values=True):
            if key:
                params[key] = val
    return rel_path, params


def _parse_bool_value(val: Any) -> bool | None:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        if val == 1:
            return True
        if val == 0:
            return False
        return None
    text = str(val).strip().lower()
    if text in ("true", "$true", "1", "yes", "on"):
        return True
    if text in ("false", "$false", "0", "no", "off"):
        return False
    return None


def coerce_param_overrides(
    script_params: list[dict[str, Any]] | None,
    raw_overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate and coerce parameter overrides against .PSSTORE_META parameter specs.

    Unknown parameter names are dropped, case is normalized to the declared
    parameter name, booleans parse strings safely, and integers are bounds-clamped.
    """
    if not script_params or not raw_overrides:
        return {}

    specs_by_lower: dict[str, dict[str, Any]] = {}
    for spec in script_params:
        name = str(spec.get("name", "")).strip()
        if name:
            specs_by_lower[name.lower()] = spec

    coerced: dict[str, Any] = {}
    for raw_key, raw_val in raw_overrides.items():
        if raw_val is None:
            continue
        spec = specs_by_lower.get(str(raw_key).strip().lower())
        if spec is None:
            continue
        canonical_name = str(spec["name"])
        param_type = str(spec.get("type", "string")).strip().lower()

        if param_type == "bool":
            parsed_bool = _parse_bool_value(raw_val)
            if parsed_bool is not None:
                coerced[canonical_name] = parsed_bool
        elif param_type in ("int", "integer"):
            if isinstance(raw_val, bool):
                continue
            try:
                parsed_int = int(str(raw_val).strip())
            except (TypeError, ValueError):
                continue
            if spec.get("min") is not None:
                parsed_int = max(int(spec["min"]), parsed_int)
            if spec.get("max") is not None:
                parsed_int = min(int(spec["max"]), parsed_int)
            coerced[canonical_name] = parsed_int
        else:
            coerced[canonical_name] = str(raw_val)

    return coerced


def _derive_category_from_path(relative_path: str) -> str:
    parts = relative_path.split("/", 1)
    if len(parts) < 2:
        return "Custom"
    return re.sub(r"^\d+_", "", parts[0]).strip() or parts[0]


def script_record_to_summary(record: ScriptRecord) -> LinkedScriptSummary:
    return LinkedScriptSummary(
        relative_path=record.relative_path,
        title=record.title,
        category=record.category,
        risk_level=record.risk_level,
        requires_admin=record.requires_admin,
        synopsis=record.synopsis or "",
        ps_edition=record.ps_edition,
        timeout_seconds=record.timeout_seconds,
        exists=True,
    )


class CrossLinkService:
    """Resolves bidirectional Playbook <-> Script metadata without cross-module UI imports."""

    def __init__(
        self,
        *,
        guideit_db_path: Path | None = None,
        catalog_repo: CatalogRepo | None = None,
    ) -> None:
        self.guideit_db_path = (
            guideit_db_path.resolve()
            if guideit_db_path is not None
            else get_guideit_db_path()
        )
        self.catalog_repo = catalog_repo
        self._reverse_cache: dict[str, list[LinkedPlaybookSummary]] | None = None

    def invalidate_cache(self) -> None:
        """Clear cached reverse Script -> Playbook mappings."""
        self._reverse_cache = None

    def get_scripts_for_paths(
        self,
        relative_paths: list[str],
    ) -> list[LinkedScriptSummary]:
        """Resolve exact canonical NN_Category/Script.ps1 paths to LinkedScriptSummary items."""
        ordered_unique: list[str] = []
        seen: set[str] = set()
        for raw in relative_paths:
            norm = str(raw).strip().replace("\\", "/")
            if not norm or norm in seen:
                continue
            seen.add(norm)
            ordered_unique.append(norm)

        if not ordered_unique:
            return []

        records_by_path: dict[str, ScriptRecord] = (
            self.catalog_repo.get_scripts_by_paths(ordered_unique)
            if self.catalog_repo is not None
            else {}
        )

        summaries: list[LinkedScriptSummary] = []
        for rel_path in ordered_unique:
            record = records_by_path.get(rel_path)
            if record is not None:
                summaries.append(script_record_to_summary(record))
            else:
                summaries.append(
                    LinkedScriptSummary(
                        relative_path=rel_path,
                        title=Path(rel_path).stem,
                        category=_derive_category_from_path(rel_path),
                        risk_level="read_only",
                        requires_admin=False,
                        synopsis="Script not found in local PowerShellStore catalog.",
                        exists=False,
                    )
                )
        return summaries

    def get_scripts_for_playbook(self, playbook_id: str) -> list[LinkedScriptSummary]:
        """Return ordered LinkedScriptSummary items for a playbook ID."""
        if not playbook_id or not self.guideit_db_path.is_file():
            return []
        record = get_playbook_by_id(self.guideit_db_path, playbook_id)
        if record is None:
            return []
        linked = [str(item) for item in record.get("linked_scripts", [])]
        return self.get_scripts_for_paths(linked)

    def _build_reverse_map(self) -> dict[str, list[LinkedPlaybookSummary]]:
        reverse: dict[str, list[LinkedPlaybookSummary]] = {}
        seen_per_script: dict[str, set[str]] = {}
        for row in get_playbook_script_links(self.guideit_db_path):
            summary = LinkedPlaybookSummary(
                id=str(row["id"]),
                title=str(row["title"]),
                domain=str(row["domain"]),
                subject=str(row["subject"]),
                tier=str(row["tier"]),
                risk_level=str(row["risk_level"]),
                path=str(row["path"]),
            )
            for script_rel in row.get("linked_scripts", []):
                norm_rel = str(script_rel).strip().replace("\\", "/")
                if not norm_rel:
                    continue
                bucket_ids = seen_per_script.setdefault(norm_rel, set())
                if summary.id not in bucket_ids:
                    bucket_ids.add(summary.id)
                    reverse.setdefault(norm_rel, []).append(summary)
        return reverse

    def get_all_reverse_links(self) -> dict[str, list[LinkedPlaybookSummary]]:
        """Return a mapping of script relative_path -> referencing LinkedPlaybookSummary list."""
        if self._reverse_cache is None:
            self._reverse_cache = self._build_reverse_map()
        return {k: list(v) for k, v in self._reverse_cache.items()}

    def get_playbooks_for_script(
        self,
        relative_path: str,
    ) -> list[LinkedPlaybookSummary]:
        """Return all GuideIT playbooks referencing the given script relative path."""
        norm = str(relative_path).strip().replace("\\", "/")
        if not norm:
            return []
        if self._reverse_cache is None:
            self._reverse_cache = self._build_reverse_map()
        return list(self._reverse_cache.get(norm, []))
