"""Pure-Python Markdown section block parser and safe HTML formatter for GuideIT UI."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

_FENCE_OPEN_RE = re.compile(r"^\s*```([A-Za-z0-9_+-]*)\s*$")
_FENCE_CLOSE_RE = re.compile(r"^\s*```\s*$")
_ORDERED_ITEM_RE = re.compile(r"^(\s*)\d+\.\s+(.+)$")
_BULLET_ITEM_RE = re.compile(r"^(\s*)[-*]\s+(.+)$")
_CLIENT_EN_RE = re.compile(r"^\s*[-*]\s*\*\*EN:\*\*\s*(.+)$", re.IGNORECASE)
_CLIENT_FR_RE = re.compile(r"^\s*[-*]\s*\*\*FR:\*\*\s*(.+)$", re.IGNORECASE)

_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_PLAYBOOK_REF_RE = re.compile(r"\[([a-z]{2,5}-\d{3,})\](?!\()")
_MD_PLAYBOOK_LINK_RE = re.compile(
    r"\[([^\]\n]+)\]\((?!https?://|mailto:|#)(?:(?:\.\./)*playbooks/[0-9]{2}_[A-Za-z0-9_]+/|\.\./[0-9]{2}_[A-Za-z0-9_]+/|\./)?([a-z]{2,5}-\d{3,})-[a-z0-9-]+\.md(?:#[^\s)]+)?\)"
)
_MD_PSSTORE_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((psstore://[^\s)]+)\)")
_MD_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\w)\*([^\*\n]+?)\*(?!\w)")
_URL_RE = re.compile(r"(https?://[^\s<>()]+)")


@dataclass(frozen=True, slots=True)
class ProseBlock:
    """Markdown prose block paired with dark-mode Qt rich HTML."""

    markdown: str
    html: str


@dataclass(frozen=True, slots=True)
class CodeBlock:
    """Fenced code/command block extracted for copyable syntax-highlighted rendering."""

    language: str
    code: str
    is_remediation: bool


@dataclass(frozen=True, slots=True)
class ClientSnippets:
    """Extracted EN/FR client update messages ready for one-click copy."""

    en: str | None = None
    fr: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedSection:
    """Structured playbook section ready for rendering."""

    heading: str
    category: str
    blocks: list[ProseBlock | CodeBlock]
    snippets: ClientSnippets | None = None


def classify_section(heading: str) -> str:
    """Map a section heading to a semantic category."""
    norm = " ".join(heading.replace("–", "-").replace("—", "-").split()).lower()
    if norm.startswith("fast triage"):
        return "triage"
    if norm.startswith("read-only diagnostics"):
        return "diagnostics"
    if norm.startswith("deep-dive investigation"):
        return "deep_dive"
    if norm.startswith("remediation"):
        return "remediation"
    if norm.startswith("verification"):
        return "verification"
    if norm.startswith("cross-subject") or norm.startswith("escalation & pivot"):
        return "pivots"
    if norm.startswith("useful links") or norm.startswith("external tools"):
        return "links"
    if norm.startswith("client update snippets"):
        return "client_snippets"
    return "other"


def _format_inline(raw_text: str) -> str:
    """Convert safe inline Markdown into dark-themed HTML while preserving code spans."""
    placeholders: dict[str, str] = {}

    def _stash(html_fragment: str) -> str:
        token = f"\x00PH{len(placeholders)}\x00"
        placeholders[token] = html_fragment
        return token

    def _replace_code(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        ref_match = re.fullmatch(r"\[([a-z]{2,5}-\d{3,})\]", inner)
        if ref_match:
            pb_id = html.escape(ref_match.group(1))
            return _stash(
                f'<a href="guideit://{pb_id}" '
                f'style="color:#38BDF8;text-decoration:none;font-weight:600;">[{pb_id}]</a>'
            )
        escaped_inner = html.escape(inner)
        return _stash(
            '<code style="background-color:#0B0F14;color:#7DD3FC;padding:1px 5px;'
            'border-radius:4px;font-family:\'Cascadia Mono\',\'Consolas\',monospace;">'
            f"{escaped_inner}</code>"
        )

    # First stash inline code spans so asterisks/URLs inside commands stay untouched
    working = _INLINE_CODE_RE.sub(_replace_code, raw_text)
    working = html.escape(working, quote=False)

    # Bare playbook ID references outside backticks -> clickable guideit:// links
    def _replace_ref(match: re.Match[str]) -> str:
        pb_id = match.group(1)
        return _stash(
            f'<a href="guideit://{pb_id}" '
            f'style="color:#38BDF8;text-decoration:none;font-weight:600;">[{pb_id}]</a>'
        )

    working = _PLAYBOOK_REF_RE.sub(_replace_ref, working)

    # Relative playbook .md links -> clickable internal guideit:// navigation
    def _replace_pb_md_link(match: re.Match[str]) -> str:
        label = match.group(1)
        pb_id = match.group(2)
        return _stash(
            f'<a href="guideit://{pb_id}" style="color:#22D3EE;text-decoration:underline;font-weight:600;">'
            f"{label} →</a>"
        )

    working = _MD_PLAYBOOK_LINK_RE.sub(_replace_pb_md_link, working)

    # Inline PowerShellStore deep links [Label](psstore://...) -> interactive action badge
    def _replace_psstore_link(match: re.Match[str]) -> str:
        label = match.group(1)
        uri = match.group(2)
        return _stash(
            f'<a href="{uri}" style="color:#C084FC;text-decoration:underline;font-weight:600;">'
            f"⚡ {label}</a>"
        )

    working = _MD_PSSTORE_LINK_RE.sub(_replace_psstore_link, working)

    # Markdown links [Label](https://...) outside code spans
    def _replace_md_link(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        return _stash(
            f'<a href="{url}" style="color:#38BDF8;text-decoration:underline;font-weight:600;">'
            f"{label} ↗</a>"
        )

    working = _MD_LINK_RE.sub(_replace_md_link, working)

    # Bare HTTP/HTTPS links outside code spans
    def _replace_url(match: re.Match[str]) -> str:
        url = match.group(1).rstrip(".,;:")
        suffix = match.group(1)[len(url) :]
        return (
            _stash(f'<a href="{url}" style="color:#60A5FA;text-decoration:underline;">{url}</a>')
            + suffix
        )

    working = _URL_RE.sub(_replace_url, working)

    # Bold & Italic
    def _replace_bold(match: re.Match[str]) -> str:
        inner = match.group(1)
        if "REMEDIATION" in inner.upper() or "CONFIRM BEFORE RUNNING" in inner.upper():
            return f'<strong style="color:#FBBF24;">{inner}</strong>'
        return f'<strong style="color:#F3F7FB;">{inner}</strong>'

    working = _BOLD_RE.sub(_replace_bold, working)
    working = _ITALIC_RE.sub(r'<em style="color:#CBD5E1;">\1</em>', working)

    for token, replacement in placeholders.items():
        working = working.replace(token, replacement)
    return working


def markdown_prose_to_html(markdown_text: str) -> str:
    """Render a prose Markdown chunk (lists, quotes, paragraphs) into clean Qt HTML."""
    lines = markdown_text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    list_stack: list[str] = []
    para_lines: list[str] = []

    def _flush_para() -> None:
        if para_lines:
            joined = " ".join(part.strip() for part in para_lines)
            out.append(f'<p style="margin:4px 0px;line-height:1.45;">{_format_inline(joined)}</p>')
            para_lines.clear()

    def _close_lists() -> None:
        while list_stack:
            out.append(f"</{list_stack.pop()}>")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            _flush_para()
            _close_lists()
            continue

        if stripped.startswith(">"):
            _flush_para()
            _close_lists()
            quote_text = stripped.lstrip(">").strip()
            out.append(
                '<div style="background-color:#121923;border-left:3px solid #38BDF8;'
                'padding:6px 10px;margin:4px 0px;color:#CBD5E1;">'
                f"{_format_inline(quote_text)}</div>"
            )
            continue

        ord_match = _ORDERED_ITEM_RE.match(line)
        if ord_match:
            _flush_para()
            if not list_stack or list_stack[-1] != "ol":
                _close_lists()
                list_stack.append("ol")
                out.append('<ol style="margin:4px 0px 4px 18px;padding-left:4px;">')
            out.append(f'<li style="margin:3px 0px;">{_format_inline(ord_match.group(2))}</li>')
            continue

        bul_match = _BULLET_ITEM_RE.match(line)
        if bul_match:
            _flush_para()
            if not list_stack or list_stack[-1] != "ul":
                _close_lists()
                list_stack.append("ul")
                out.append('<ul style="margin:4px 0px 4px 18px;padding-left:4px;">')
            out.append(f'<li style="margin:3px 0px;">{_format_inline(bul_match.group(2))}</li>')
            continue

        # Continuation line inside a list item or regular paragraph
        if list_stack and out and out[-1].endswith("</li>"):
            prev_li = out.pop()
            out.append(prev_li[:-5] + " " + _format_inline(stripped) + "</li>")
        else:
            _close_lists()
            para_lines.append(stripped)

    _flush_para()
    _close_lists()
    return "".join(out)


def _clean_snippet_text(raw: str) -> str:
    """Normalize a client-facing snippet into clean plain text ready for email/ticket paste."""
    cleaned = raw.strip()
    cleaned = cleaned.replace("`", "")
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    return cleaned.strip()


def _extract_client_snippets(content: str) -> ClientSnippets | None:
    """Parse EN and FR client update bullets from the Client Update Snippets section."""
    en_text: str | None = None
    fr_text: str | None = None
    for line in content.replace("\r\n", "\n").split("\n"):
        en_match = _CLIENT_EN_RE.match(line)
        if en_match:
            en_text = _clean_snippet_text(en_match.group(1))
            continue
        fr_match = _CLIENT_FR_RE.match(line)
        if fr_match:
            fr_text = _clean_snippet_text(fr_match.group(1))
    if en_text is None and fr_text is None:
        return None
    return ClientSnippets(en=en_text, fr=fr_text)


def parse_section_blocks(heading: str, content: str) -> ParsedSection:
    """Split a Markdown section body into ordered prose and copyable code blocks."""
    category = classify_section(heading)
    snippets = _extract_client_snippets(content) if category == "client_snippets" else None

    blocks: list[ProseBlock | CodeBlock] = []
    prose_buf: list[str] = []
    code_buf: list[str] = []
    in_code = False
    code_lang = "text"

    def _flush_prose() -> None:
        raw = "\n".join(prose_buf).strip()
        prose_buf.clear()
        if raw:
            blocks.append(ProseBlock(markdown=raw, html=markdown_prose_to_html(raw)))

    for line in content.replace("\r\n", "\n").split("\n"):
        if not in_code:
            open_match = _FENCE_OPEN_RE.match(line)
            if open_match:
                _flush_prose()
                in_code = True
                code_lang = open_match.group(1).strip() or "text"
                code_buf.clear()
                continue
            prose_buf.append(line)
        else:
            if _FENCE_CLOSE_RE.match(line):
                raw_code = "\n".join(code_buf).rstrip("\n")
                code_buf.clear()
                in_code = False
                if raw_code:
                    blocks.append(
                        CodeBlock(
                            language=code_lang,
                            code=raw_code,
                            is_remediation=(category == "remediation"),
                        )
                    )
                continue
            code_buf.append(line)

    if in_code and code_buf:
        blocks.append(
            CodeBlock(
                language=code_lang,
                code="\n".join(code_buf).rstrip("\n"),
                is_remediation=(category == "remediation"),
            )
        )
    else:
        _flush_prose()

    return ParsedSection(
        heading=heading,
        category=category,
        blocks=blocks,
        snippets=snippets,
    )
