"""GuideIT core library for playbook validation, SQLite FTS5 indexing, and search."""

from guideit_master.guideit.frontmatter import FrontmatterError, extract_sections, parse_frontmatter
from guideit_master.guideit.indexer import DEFAULT_DB_RELPATH, SCHEMA_VERSION, build_index
from guideit_master.guideit.models import (
    IndexStats,
    Playbook,
    SearchHit,
    SearchResponse,
    ValidationIssue,
    ValidationReport,
)
from guideit_master.guideit.search import (
    ensure_index_current,
    get_domain_and_subcategory_counts,
    get_playbook_by_id,
    get_playbook_titles,
    list_facets,
    search_playbooks,
)
from guideit_master.guideit.taxonomy import expand_query, load_resources, load_taxonomy, normalize_text
from guideit_master.guideit.validator import load_playbook_file, validate_repository

__all__ = [
    "DEFAULT_DB_RELPATH",
    "FrontmatterError",
    "IndexStats",
    "Playbook",
    "SCHEMA_VERSION",
    "SearchHit",
    "SearchResponse",
    "ValidationIssue",
    "ValidationReport",
    "build_index",
    "ensure_index_current",
    "expand_query",
    "extract_sections",
    "get_domain_and_subcategory_counts",
    "get_playbook_by_id",
    "get_playbook_titles",
    "list_facets",
    "load_playbook_file",
    "load_resources",
    "load_taxonomy",
    "normalize_text",
    "parse_frontmatter",
    "search_playbooks",
    "validate_repository",
]
