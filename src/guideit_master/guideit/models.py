"""Typed data models for the GuideIT playbook library."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class Playbook:
    """Represents a parsed GuideIT troubleshooting playbook."""

    id: str
    path: str
    domain: str
    subject: str
    title: str
    tier: str
    keywords_en: list[str]
    keywords_fr: list[str]
    error_codes: list[str]
    tags: list[str]
    os: list[str]
    environment: list[str]
    tools: list[str]
    risk_level: str
    requires_admin: bool
    last_verified: str
    subcategory: str = ""
    related_ids: list[str] = field(default_factory=list)
    linked_scripts: list[str] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)
    section_order: list[str] = field(default_factory=list)
    body_markdown: str = ""
    triage_summary: str = ""


@dataclass(slots=True)
class ValidationIssue:
    """Single validation error or warning found during repository auditing."""

    severity: str  # "error" | "warning"
    code: str
    path: str
    message: str
    line: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ValidationReport:
    """Aggregated validation results across the playbook repository."""

    checked_files: int
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    @property
    def strict_ok(self) -> bool:
        return len(self.errors) == 0 and len(self.warnings) == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "checked_files": self.checked_files,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "ok": self.ok,
            "strict_ok": self.strict_ok,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(slots=True)
class IndexStats:
    """Summary metadata produced after rebuilding the SQLite FTS5 index."""

    db_path: str
    indexed_count: int
    built_at: str
    source_hash: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class SearchHit:
    """Ranked search match returned by the FTS5 + taxonomy query engine."""

    id: str
    path: str
    domain: str
    subject: str
    title: str
    tier: str
    risk_level: str
    requires_admin: bool
    os: list[str]
    environment: list[str]
    tags: list[str]
    error_codes: list[str]
    tools: list[str]
    last_verified: str
    triage_summary: str
    score: float
    subcategory: str = ""
    matched_reasons: list[str] = field(default_factory=list)
    linked_scripts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class SearchResponse:
    """Complete search output including query expansion metadata and hits."""

    query: str
    expanded_tags: list[str]
    suggested_domains: list[str]
    total_hits: int
    hits: list[SearchHit]

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "expanded_tags": self.expanded_tags,
            "suggested_domains": self.suggested_domains,
            "total_hits": self.total_hits,
            "hits": [hit.to_dict() for hit in self.hits],
        }
