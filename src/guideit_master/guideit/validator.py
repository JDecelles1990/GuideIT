"""Playbook parser, schema validator, and multi-tenant PII/redaction linter."""

from __future__ import annotations

import ipaddress
import json
import re
from datetime import date
from pathlib import Path

from guideit_master.guideit.frontmatter import FrontmatterError, extract_sections, parse_frontmatter
from guideit_master.guideit.models import Playbook, ValidationIssue, ValidationReport
from guideit_master.guideit.taxonomy import TaxonomyConfig, load_taxonomy
from guideit_master.paths import get_bundle_dir, get_playbooks_dir, get_ps_scripts_dir, get_taxonomy_dir

_SNAKE_CASE_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
_KEBAB_FILENAME_RE = re.compile(r"^[a-z0-9]+-[a-z0-9-]+\.md$")
_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![A-Za-z0-9._%+-])"
)
_IPV4_RE = re.compile(r"(?<![\d.])((?:\d{1,3}\.){3}\d{1,3})(?![\d.])")
_GUID_RE = re.compile(
    r"\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b"
)
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key header", re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
)
_MD_REL_LINK_RE = re.compile(
    r"\[[^\]\n]+\]\((?!https?://|mailto:|#)([^)\s#]+\.md)(?:#[^)\s]*)?\)"
)
_PSSTORE_LINK_RE = re.compile(r"\[[^\]\n]+\]\(psstore://([^)\s#]*)(?:#[^)\s]*)?\)")
_CANONICAL_SCRIPT_RELPATH_RE = re.compile(
    r"^[0-9]{2}_[A-Za-z0-9_]+/[A-Za-z0-9][A-Za-z0-9_-]*\.ps1$"
)
_FENCE_LINE_RE = re.compile(r"^\s*```")
_FENCE_MARKER_RE = re.compile(r"^\s*(```|~~~)")

_SAFE_IPV4_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
)


def _normalize_heading(heading: str) -> str:
    """Normalize en/em dashes and whitespace when comparing section headings."""
    return " ".join(heading.replace("–", "-").replace("—", "-").split()).lower()


def _is_subnet_mask(ip: ipaddress.IPv4Address) -> bool:
    """Return True if an IPv4 address represents a contiguous CIDR subnet mask."""
    val = int(ip)
    if val == 0:
        return True
    inverted = (~val) & 0xFFFFFFFF
    return (inverted & (inverted + 1)) == 0


def _is_allowed_ipv4(ip_str: str, allowed_public_dns: set[str]) -> bool:
    """Return True if IPv4 is RFC1918/APIPA/loopback/RFC5737 doc/mask/known DNS."""
    if ip_str in allowed_public_dns:
        return True
    try:
        ip = ipaddress.IPv4Address(ip_str)
    except ValueError:
        return True  # Not an IPv4 address (e.g., Windows build numbers like 10.0.19045.5011)
    if _is_subnet_mask(ip):
        return True
    return any(ip in net for net in _SAFE_IPV4_NETWORKS)


def _is_allowed_email(email: str, allowed_domains: set[str]) -> bool:
    """Allow synthetic placeholder domains defined in taxonomy/schema.json."""
    domain = email.rsplit("@", 1)[1].lower()
    return any(domain == allowed or domain.endswith("." + allowed) for allowed in allowed_domains)


def _is_placeholder_guid(guid: str) -> bool:
    """Allow obvious synthetic placeholders such as 00000000-0000-0000-0000-000000000000."""
    hex_chars = guid.replace("-", "").lower()
    return len(set(hex_chars)) == 1


def _lint_pii_lines(
    text: str,
    rel_path: str,
    taxonomy: TaxonomyConfig,
) -> list[ValidationIssue]:
    """Scan text line-by-line for unredacted emails, public IPs, GUIDs, and secret tokens."""
    issues: list[ValidationIssue] = []
    allowed_domains = taxonomy.schema.allowed_placeholder_email_domains
    allowed_dns = taxonomy.schema.allowed_public_dns_ips

    for lineno, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        for match in _EMAIL_RE.finditer(line):
            email = match.group(1)
            if not _is_allowed_email(email, allowed_domains):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="PII_EMAIL",
                        path=rel_path,
                        line=lineno,
                        message=(
                            f"Potential non-placeholder email '{email}'. "
                            "Use synthetic domains such as example.com or contoso.com."
                        ),
                    )
                )

        for match in _IPV4_RE.finditer(line):
            ip_str = match.group(1)
            prefix_char = line[match.start(1) - 1] if match.start(1) > 0 else ""
            if prefix_char.lower() == "v":
                continue  # Version string like v6.12.0.1
            if not _is_allowed_ipv4(ip_str, allowed_dns):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="PII_PUBLIC_IP",
                        path=rel_path,
                        line=lineno,
                        message=(
                            f"Potential real public IPv4 '{ip_str}'. "
                            "Use RFC 5737 documentation IPs (e.g., 198.51.100.10) or RFC 1918 ranges."
                        ),
                    )
                )

        for match in _GUID_RE.finditer(line):
            guid = match.group(1)
            if not _is_placeholder_guid(guid):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="PII_GUID",
                        path=rel_path,
                        line=lineno,
                        message=(
                            f"Potential raw tenant/object GUID '{guid}'. "
                            "Use 00000000-0000-0000-0000-000000000000 or <tenant-id>."
                        ),
                    )
                )

        for label, pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="PII_SECRET",
                        path=rel_path,
                        line=lineno,
                        message=f"Potential secret detected ({label}). Remove credentials immediately.",
                    )
                )

    return issues


def _extract_relative_md_links(body_markdown: str) -> list[tuple[int, str]]:
    """Extract (body_line, rel_md_target) pairs outside fenced code blocks and inline code."""
    links: list[tuple[int, str]] = []
    in_fence = False
    for lineno, line in enumerate(body_markdown.replace("\r\n", "\n").split("\n"), start=1):
        if _FENCE_LINE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        stripped_code = re.sub(r"`[^`\n]*`", "", line)
        for match in _MD_REL_LINK_RE.finditer(stripped_code):
            links.append((lineno, match.group(1)))
    return links


def _extract_psstore_links(body_markdown: str) -> list[tuple[int, str]]:
    """Extract (body_line, psstore_target) pairs outside fenced code blocks and inline code."""
    links: list[tuple[int, str]] = []
    in_fence = False
    fence_marker = ""
    for lineno, line in enumerate(body_markdown.replace("\r\n", "\n").split("\n"), start=1):
        fence_match = _FENCE_MARKER_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            continue
        if in_fence:
            continue
        stripped_code = re.sub(r"`[^`\n]*`", "", line)
        for match in _PSSTORE_LINK_RE.finditer(stripped_code):
            links.append((lineno, match.group(1)))
    return links


def _extract_triage_summary(sections: dict[str, str]) -> str:
    """Extract concise Fast Triage text for search hit previews."""
    for heading, content in sections.items():
        if _normalize_heading(heading).startswith("fast triage"):
            lines: list[str] = []
            for raw_ln in content.splitlines():
                stripped = raw_ln.strip()
                if not stripped:
                    continue
                if re.match(r"^#{3,6}\s+", stripped):
                    cleaned = re.sub(r"^#{3,6}\s+", "", stripped).strip()
                    if cleaned:
                        lines.append(f"{cleaned}:")
                else:
                    lines.append(stripped)
            summary = " ".join(lines)
            if len(summary) > 400:
                return summary[:397].rstrip() + "..."
            return summary
    return ""


def load_playbook_file(root_dir: Path | None, file_path: Path) -> Playbook:
    """Parse a Markdown playbook file into a Playbook model (without full repo cross-checks)."""
    resolved_root = (root_dir if root_dir is not None else get_bundle_dir()).resolve()
    raw = file_path.read_text(encoding="utf-8")
    meta, body_markdown, _ = parse_frontmatter(raw)
    section_order, sections = extract_sections(body_markdown)
    rel_path = file_path.resolve().relative_to(resolved_root).as_posix()

    def _str_list(key: str) -> list[str]:
        val = meta.get(key, [])
        if isinstance(val, list):
            return [str(item) for item in val]
        return []

    return Playbook(
        id=str(meta.get("id", "")),
        path=rel_path,
        domain=str(meta.get("domain", "")),
        subject=str(meta.get("subject", "")),
        title=str(meta.get("title", "")),
        tier=str(meta.get("tier", "")),
        keywords_en=_str_list("keywords_en"),
        keywords_fr=_str_list("keywords_fr"),
        error_codes=_str_list("error_codes"),
        tags=_str_list("tags"),
        os=_str_list("os"),
        environment=_str_list("environment"),
        tools=_str_list("tools"),
        risk_level=str(meta.get("risk_level", "")),
        requires_admin=bool(meta.get("requires_admin", False)),
        last_verified=str(meta.get("last_verified", "")),
        subcategory=str(meta.get("subcategory", "") or "").strip(),
        related_ids=_str_list("related_ids"),
        linked_scripts=_str_list("linked_scripts"),
        sections=sections,
        section_order=section_order,
        body_markdown=body_markdown,
        triage_summary=_extract_triage_summary(sections),
    )


def _check_string_list(
    meta: dict[str, object],
    field: str,
    rel_path: str,
    *,
    allow_empty: bool,
    issues: list[ValidationIssue],
) -> list[str] | None:
    """Validate that metadata field is a list of non-empty strings."""
    if field not in meta:
        return None
    val = meta[field]
    if not isinstance(val, list):
        issues.append(
            ValidationIssue(
                severity="error",
                code="INVALID_TYPE",
                path=rel_path,
                message=f"Field '{field}' must be a YAML list of strings.",
            )
        )
        return None
    cleaned = [str(item).strip() for item in val]
    if any(not item for item in cleaned):
        issues.append(
            ValidationIssue(
                severity="error",
                code="EMPTY_LIST_ITEM",
                path=rel_path,
                message=f"Field '{field}' contains an empty item.",
            )
        )
        return None
    if not allow_empty and len(cleaned) == 0:
        issues.append(
            ValidationIssue(
                severity="error",
                code="EMPTY_LIST",
                path=rel_path,
                message=f"Field '{field}' must contain at least one item.",
            )
        )
        return None
    return cleaned


def validate_repository(
    root_dir: Path | None = None,
    *,
    max_age_days: int = 180,
    today: date | None = None,
    ps_scripts_dir: Path | None = None,
) -> ValidationReport:
    """Validate taxonomy files, playbook frontmatter/sections, cross-references, and PII rules."""
    issues: list[ValidationIssue] = []
    ref_today = today or date.today()
    resolved_root = (root_dir if root_dir is not None else get_bundle_dir()).resolve()

    try:
        taxonomy = load_taxonomy(resolved_root)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        issues.append(
            ValidationIssue(
                severity="error",
                code="TAXONOMY_LOAD_ERROR",
                path="taxonomy",
                message=f"Failed to load taxonomy configuration: {exc}",
            )
        )
        return ValidationReport(checked_files=0, issues=issues)

    # Lint taxonomy/keyword_map.json for accidental PII as well
    kw_path = get_taxonomy_dir(resolved_root) / "keyword_map.json"
    if kw_path.exists():
        issues.extend(_lint_pii_lines(kw_path.read_text(encoding="utf-8"), "taxonomy/keyword_map.json", taxonomy))

    playbooks_dir = get_playbooks_dir(resolved_root)
    if not playbooks_dir.is_dir():
        issues.append(
            ValidationIssue(
                severity="error",
                code="MISSING_PLAYBOOKS_DIR",
                path="playbooks",
                message="Playbooks directory does not exist.",
            )
        )
        return ValidationReport(checked_files=0, issues=issues)

    playbook_files: list[Path] = []
    for item in sorted(playbooks_dir.iterdir()):
        if item.is_file() and item.suffix.lower() == ".md":
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="MISPLACED_PLAYBOOK",
                    path=item.relative_to(resolved_root).as_posix(),
                    message="Playbooks must live inside a numbered domain subfolder (playbooks/01..09/), not playbooks/ root.",
                )
            )
        elif item.is_dir():
            if item.name not in taxonomy.domains_by_folder:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="UNKNOWN_DOMAIN_DIR",
                        path=item.relative_to(resolved_root).as_posix(),
                        message=f"Folder '{item.name}' is not registered in taxonomy/domains.json.",
                    )
                )
                continue
            for md_file in sorted(item.glob("*.md")):
                if md_file.name.lower() == "readme.md":
                    continue
                playbook_files.append(md_file)

    schema = taxonomy.schema
    known_fields = set(schema.required_fields) | set(schema.optional_fields)
    seen_ids: dict[str, str] = {}
    path_to_id: dict[Path, str] = {}
    parsed_playbooks: list[Playbook] = []
    used_tags: set[str] = set()

    for md_file in playbook_files:
        rel_path = md_file.relative_to(resolved_root).as_posix()
        parent_folder = md_file.parent.name
        domain_spec = taxonomy.domains_by_folder[parent_folder]
        raw_text = md_file.read_text(encoding="utf-8")

        # Always run PII linter even if frontmatter has issues
        issues.extend(_lint_pii_lines(raw_text, rel_path, taxonomy))

        try:
            meta, body_markdown, _ = parse_frontmatter(raw_text)
        except FrontmatterError as exc:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="YAML_SYNTAX",
                    path=rel_path,
                    line=exc.line,
                    message=exc.message,
                )
            )
            continue

        # Required & unknown fields
        for req_field in schema.required_fields:
            if req_field not in meta:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="MISSING_FIELD",
                        path=rel_path,
                        message=f"Missing required frontmatter field '{req_field}'.",
                    )
                )

        for key in meta:
            if key not in known_fields:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="UNKNOWN_FIELD",
                        path=rel_path,
                        message=f"Unknown frontmatter field '{key}'.",
                    )
                )

        # Scalar string checks
        pb_id = meta.get("id")
        if not isinstance(pb_id, str) or not pb_id.strip():
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_ID",
                    path=rel_path,
                    message="Field 'id' must be a non-empty string.",
                )
            )
            pb_id_str = ""
        else:
            pb_id_str = pb_id.strip()
            expected_id_re = re.compile(rf"^{re.escape(domain_spec.prefix)}-\d{{3,}}$")
            if not expected_id_re.match(pb_id_str):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="ID_DOMAIN_MISMATCH",
                        path=rel_path,
                        message=(
                            f"Playbook id '{pb_id_str}' must match '{domain_spec.prefix}-NNN' "
                            f"for domain folder '{parent_folder}'."
                        ),
                    )
                )
            if not _KEBAB_FILENAME_RE.match(md_file.name) or not md_file.name.startswith(f"{pb_id_str}-"):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="FILENAME_MISMATCH",
                        path=rel_path,
                        message=(
                            f"Filename '{md_file.name}' must be lowercase kebab-case starting with '{pb_id_str}-'."
                        ),
                    )
                )
            if pb_id_str in seen_ids:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="DUPLICATE_ID",
                        path=rel_path,
                        message=f"Duplicate playbook id '{pb_id_str}' (already defined in {seen_ids[pb_id_str]}).",
                    )
                )
            else:
                seen_ids[pb_id_str] = rel_path
                path_to_id[md_file.resolve()] = pb_id_str

        domain_val = meta.get("domain")
        if domain_val != parent_folder:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="DOMAIN_MISMATCH",
                    path=rel_path,
                    message=f"Field 'domain' ({domain_val!r}) must match folder '{parent_folder}'.",
                )
            )

        subject_val = meta.get("subject")
        if subject_val != domain_spec.subject:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="SUBJECT_MISMATCH",
                    path=rel_path,
                    message=(
                        f"Field 'subject' ({subject_val!r}) must match canonical subject "
                        f"'{domain_spec.subject}' for '{parent_folder}'."
                    ),
                )
            )

        subcategory_val = ""
        if "subcategory" in meta:
            raw_subcat = meta.get("subcategory")
            valid_subcats = {sub.id for sub in domain_spec.subcategories}
            if not isinstance(raw_subcat, str) or not raw_subcat.strip():
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="INVALID_SUBCATEGORY",
                        path=rel_path,
                        message="Field 'subcategory' must be a non-empty string.",
                    )
                )
            else:
                subcategory_val = raw_subcat.strip()
                if subcategory_val not in valid_subcats:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            code="INVALID_SUBCATEGORY",
                            path=rel_path,
                            message=(
                                f"Subcategory '{subcategory_val}' is not valid for domain "
                                f"'{parent_folder}' ({sorted(valid_subcats)})."
                            ),
                        )
                    )

        title_val = meta.get("title")
        if not isinstance(title_val, str) or not title_val.strip():
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_TITLE",
                    path=rel_path,
                    message="Field 'title' must be a non-empty string.",
                )
            )

        # Enum scalars
        tier_val = meta.get("tier")
        if not isinstance(tier_val, str) or tier_val not in schema.enums.get("tier", []):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_ENUM",
                    path=rel_path,
                    message=f"Field 'tier' ({tier_val!r}) must be one of {schema.enums.get('tier', [])}.",
                )
            )

        risk_val = meta.get("risk_level")
        if not isinstance(risk_val, str) or risk_val not in schema.enums.get("risk_level", []):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_ENUM",
                    path=rel_path,
                    message=(
                        f"Field 'risk_level' ({risk_val!r}) must be one of "
                        f"{schema.enums.get('risk_level', [])}."
                    ),
                )
            )

        requires_admin_val = meta.get("requires_admin")
        if not isinstance(requires_admin_val, bool):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_TYPE",
                    path=rel_path,
                    message="Field 'requires_admin' must be boolean true or false.",
                )
            )

        last_verified_val = meta.get("last_verified")
        if not isinstance(last_verified_val, str):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_DATE",
                    path=rel_path,
                    message="Field 'last_verified' must be an ISO date string YYYY-MM-DD.",
                )
            )
        else:
            try:
                verified_date = date.fromisoformat(last_verified_val)
                age_days = (ref_today - verified_date).days
                if age_days > max_age_days:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            code="STALE_PLAYBOOK",
                            path=rel_path,
                            message=(
                                f"Playbook last verified {last_verified_val} ({age_days} days ago, "
                                f"threshold {max_age_days} days)."
                            ),
                        )
                    )
            except ValueError:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="INVALID_DATE",
                        path=rel_path,
                        message=f"Field 'last_verified' ({last_verified_val!r}) is not a valid YYYY-MM-DD date.",
                    )
                )

        # List fields
        kw_en = _check_string_list(meta, "keywords_en", rel_path, allow_empty=False, issues=issues) or []
        kw_fr = _check_string_list(meta, "keywords_fr", rel_path, allow_empty=False, issues=issues) or []
        err_codes = _check_string_list(meta, "error_codes", rel_path, allow_empty=True, issues=issues) or []
        tags = _check_string_list(meta, "tags", rel_path, allow_empty=False, issues=issues) or []
        os_list = _check_string_list(meta, "os", rel_path, allow_empty=False, issues=issues) or []
        env_list = _check_string_list(meta, "environment", rel_path, allow_empty=False, issues=issues) or []
        tools = _check_string_list(meta, "tools", rel_path, allow_empty=False, issues=issues) or []
        related_ids = _check_string_list(meta, "related_ids", rel_path, allow_empty=True, issues=issues) or []
        linked_scripts = _check_string_list(
            meta, "linked_scripts", rel_path, allow_empty=True, issues=issues
        ) or []

        for tag in tags:
            used_tags.add(tag)
            if not _SNAKE_CASE_RE.match(tag):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="INVALID_TAG_FORMAT",
                        path=rel_path,
                        message=f"Tag '{tag}' must be lowercase snake_case.",
                    )
                )

        allowed_os = set(schema.enums.get("os", []))
        for os_item in os_list:
            if os_item not in allowed_os:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="INVALID_ENUM",
                        path=rel_path,
                        message=f"OS value '{os_item}' must be one of {sorted(allowed_os)}.",
                    )
                )

        allowed_env = set(schema.enums.get("environment", []))
        for env_item in env_list:
            if env_item not in allowed_env:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="INVALID_ENUM",
                        path=rel_path,
                        message=f"Environment value '{env_item}' must be one of {sorted(allowed_env)}.",
                    )
                )

        # Required sections in order
        section_order, sections = extract_sections(body_markdown)
        norm_order = [_normalize_heading(h) for h in section_order]
        last_pos = -1
        for req_sec in schema.required_sections:
            norm_req = _normalize_heading(req_sec)
            if norm_req not in norm_order:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="MISSING_SECTION",
                        path=rel_path,
                        message=f"Missing required section '## {req_sec}'.",
                    )
                )
            else:
                pos = norm_order.index(norm_req)
                if pos < last_pos:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            code="SECTION_ORDER",
                            path=rel_path,
                            message=f"Section '## {req_sec}' appears out of required schema order.",
                        )
                    )
                last_pos = pos

        parsed_playbooks.append(
            Playbook(
                id=pb_id_str,
                path=rel_path,
                domain=str(domain_val or ""),
                subject=str(subject_val or ""),
                title=str(title_val or ""),
                tier=str(tier_val or ""),
                keywords_en=kw_en,
                keywords_fr=kw_fr,
                error_codes=err_codes,
                tags=tags,
                os=os_list,
                environment=env_list,
                tools=tools,
                risk_level=str(risk_val or ""),
                requires_admin=bool(requires_admin_val) if isinstance(requires_admin_val, bool) else False,
                last_verified=str(last_verified_val or ""),
                subcategory=subcategory_val,
                related_ids=related_ids,
                linked_scripts=linked_scripts,
                sections=sections,
                section_order=section_order,
                body_markdown=body_markdown,
                triage_summary=_extract_triage_summary(sections),
            )
        )

    # Cross-playbook related_ids, relative .md links, and PowerShell linked_scripts checks
    valid_ids = set(seen_ids.keys())
    playbooks_root = playbooks_dir.resolve()
    scripts_root = (
        ps_scripts_dir if ps_scripts_dir is not None else get_ps_scripts_dir(resolved_root)
    ).resolve()
    available_scripts: set[str] = (
        {p.relative_to(scripts_root).as_posix() for p in scripts_root.rglob("*.ps1")}
        if scripts_root.is_dir()
        else set()
    )
    for pb in parsed_playbooks:
        for script_entry in pb.linked_scripts:
            if not _CANONICAL_SCRIPT_RELPATH_RE.match(script_entry):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="BROKEN_LINKED_SCRIPT",
                        path=pb.path,
                        message=(
                            f"linked_scripts entry '{script_entry}' must use strict canonical "
                            "'NN_Category/Verb-Noun.ps1' format."
                        ),
                    )
                )
            elif script_entry not in available_scripts:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="BROKEN_LINKED_SCRIPT",
                        path=pb.path,
                        message=(
                            f"linked_scripts references missing script '{script_entry}' "
                            "under powershell_scripts/."
                        ),
                    )
                )

        for lineno, raw_target in _extract_psstore_links(pb.body_markdown):
            script_rel = raw_target.split("?", 1)[0]
            if not _CANONICAL_SCRIPT_RELPATH_RE.match(script_rel):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="BROKEN_LINKED_SCRIPT",
                        path=pb.path,
                        line=lineno,
                        message=(
                            f"Inline psstore:// link '{raw_target}' must target a strict "
                            "canonical 'NN_Category/Verb-Noun.ps1' path."
                        ),
                    )
                )
            elif script_rel not in available_scripts:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="BROKEN_LINKED_SCRIPT",
                        path=pb.path,
                        line=lineno,
                        message=(
                            f"Inline psstore:// link '{raw_target}' references missing script "
                            f"'{script_rel}' under powershell_scripts/."
                        ),
                    )
                )
        for rel_id in pb.related_ids:
            if rel_id not in valid_ids:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="BROKEN_RELATED_ID",
                        path=pb.path,
                        message=f"related_ids references non-existent playbook '{rel_id}'.",
                    )
                )
            elif rel_id == pb.id:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="SELF_RELATED_ID",
                        path=pb.path,
                        message=f"related_ids references self ('{rel_id}').",
                    )
                )

        pb_file = (resolved_root / pb.path).resolve()
        for lineno, rel_target in _extract_relative_md_links(pb.body_markdown):
            target_file = (pb_file.parent / rel_target).resolve()
            try:
                in_playbooks_tree = target_file.is_relative_to(playbooks_root)
            except ValueError:
                in_playbooks_tree = False
            if not in_playbooks_tree or not target_file.is_file() or target_file not in path_to_id:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="BROKEN_MD_LINK",
                        path=pb.path,
                        line=lineno,
                        message=(
                            f"Relative Markdown link '{rel_target}' does not resolve to "
                            "a valid playbook inside playbooks/."
                        ),
                    )
                )
                continue
            target_id = path_to_id[target_file]
            if target_file == pb_file or (pb.id and target_id == pb.id):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="SELF_MD_LINK",
                        path=pb.path,
                        line=lineno,
                        message=f"Relative Markdown link '{rel_target}' points to self ('{target_id}').",
                    )
                )
            elif target_id not in pb.related_ids:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="UNSYNCED_MD_LINK",
                        path=pb.path,
                        line=lineno,
                        message=(
                            f"Relative Markdown link to '{target_id}' ({rel_target}) "
                            "is not listed in frontmatter related_ids."
                        ),
                    )
                )

    # Cross-repo keyword_map coverage and PowerShell script linkage checks (warnings)
    if parsed_playbooks:
        expected_tags: set[str] = set()
        for entry in taxonomy.keyword_entries:
            expected_tags.update(entry.tags)
        for tag in sorted(expected_tags - used_tags):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="UNCOVERED_TAG",
                    path="taxonomy/keyword_map.json",
                    message=f"Canonical tag '{tag}' in keyword_map.json is not used by any playbook yet.",
                )
            )
        linked_script_refs = {
            script_entry
            for pb in parsed_playbooks
            for script_entry in pb.linked_scripts
            if script_entry in available_scripts
        }
        for script_rel in sorted(available_scripts - linked_script_refs):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="UNLINKED_SCRIPT",
                    path=f"powershell_scripts/{script_rel}",
                    message=(
                        f"PowerShell script '{script_rel}' is not linked in frontmatter "
                        "linked_scripts of any playbook. Link it to a matching playbook or "
                        "create at least one new playbook."
                    ),
                )
            )

    return ValidationReport(checked_files=len(playbook_files), issues=issues)
