"""Zero-dependency strict YAML frontmatter parser and Markdown section extractor."""

from __future__ import annotations

import re

_TOP_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(.*)$")
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


class FrontmatterError(ValueError):
    """Raised when YAML frontmatter is missing or syntactically invalid."""

    def __init__(self, message: str, line: int | None = None) -> None:
        self.line = line
        self.message = message
        prefix = f"Line {line}: " if line is not None else ""
        super().__init__(f"{prefix}{message}")


def _strip_inline_comment(value: str) -> str:
    """Strip an unquoted inline '#' comment preceded by whitespace (or at start)."""
    in_double = False
    in_single = False
    escaped = False
    i = 0
    n = len(value)
    while i < n:
        ch = value[i]
        if in_double:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_double = False
        elif in_single:
            if ch == "'":
                if i + 1 < n and value[i + 1] == "'":
                    i += 1
                else:
                    in_single = False
        else:
            if ch == '"':
                in_double = True
            elif ch == "'":
                in_single = True
            elif ch == "#" and (i == 0 or value[i - 1].isspace()):
                return value[:i].rstrip()
        i += 1
    return value.rstrip()


def _parse_double_quoted(raw: str, line: int) -> str:
    """Parse a double-quoted YAML scalar."""
    out: list[str] = []
    i = 1
    n = len(raw)
    escaped = False
    while i < n:
        ch = raw[i]
        if escaped:
            if ch == "n":
                out.append("\n")
            elif ch == "t":
                out.append("\t")
            elif ch == "r":
                out.append("\r")
            elif ch in ('"', "\\", "/"):
                out.append(ch)
            else:
                out.append("\\" + ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            trailing = raw[i + 1 :].strip()
            if trailing:
                raise FrontmatterError(
                    f"Unexpected trailing characters after quoted string: {trailing!r}.",
                    line=line,
                )
            return "".join(out)
        else:
            out.append(ch)
        i += 1
    raise FrontmatterError("Unclosed double-quoted string.", line=line)


def _parse_single_quoted(raw: str, line: int) -> str:
    """Parse a single-quoted YAML scalar (supports '' escape)."""
    out: list[str] = []
    i = 1
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "'":
            if i + 1 < n and raw[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            trailing = raw[i + 1 :].strip()
            if trailing:
                raise FrontmatterError(
                    f"Unexpected trailing characters after quoted string: {trailing!r}.",
                    line=line,
                )
            return "".join(out)
        out.append(ch)
        i += 1
    raise FrontmatterError("Unclosed single-quoted string.", line=line)


def _parse_scalar(raw: str, line: int, *, allow_bool: bool = True) -> str | bool:
    """Parse a YAML scalar value, preserving strings such as '4740' or '2026-11-22'."""
    text = raw.strip()
    if not text:
        raise FrontmatterError("Expected scalar value but found empty expression.", line=line)
    if text.startswith('"'):
        return _parse_double_quoted(text, line)
    if text.startswith("'"):
        return _parse_single_quoted(text, line)
    if text.startswith("[") or text.startswith("{"):
        raise FrontmatterError(f"Invalid collection syntax: {text!r}.", line=line)

    if allow_bool:
        lower = text.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
    return text


def _split_flow_items(inner: str, line: int) -> list[str]:
    """Split comma-separated items inside '[...]' respecting quotes."""
    items: list[str] = []
    buf: list[str] = []
    in_double = False
    in_single = False
    escaped = False
    i = 0
    n = len(inner)
    while i < n:
        ch = inner[i]
        if in_double:
            buf.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_double = False
        elif in_single:
            buf.append(ch)
            if ch == "'":
                if i + 1 < n and inner[i + 1] == "'":
                    buf.append("'")
                    i += 1
                else:
                    in_single = False
        else:
            if ch == '"':
                in_double = True
                buf.append(ch)
            elif ch == "'":
                in_single = True
                buf.append(ch)
            elif ch == ",":
                token = "".join(buf).strip()
                if not token:
                    raise FrontmatterError("Empty item in inline YAML list.", line=line)
                items.append(token)
                buf.clear()
            else:
                buf.append(ch)
        i += 1

    if in_double:
        raise FrontmatterError("Unclosed double-quoted string inside inline list.", line=line)
    if in_single:
        raise FrontmatterError("Unclosed single-quoted string inside inline list.", line=line)

    tail = "".join(buf).strip()
    if not tail:
        raise FrontmatterError("Trailing comma or empty element in inline YAML list.", line=line)
    items.append(tail)
    return items


def _parse_flow_list(raw: str, line: int) -> list[str]:
    """Parse a YAML flow sequence such as '[a, "b, c"]' or '[]'."""
    text = raw.strip()
    if not text.endswith("]"):
        raise FrontmatterError("Unclosed inline YAML list '['.", line=line)
    inner = text[1:-1].strip()
    if not inner:
        return []
    raw_items = _split_flow_items(inner, line)
    parsed: list[str] = []
    for item in raw_items:
        val = _parse_scalar(item, line, allow_bool=False)
        parsed.append(str(val))
    return parsed


def parse_frontmatter(text: str) -> tuple[dict[str, object], str, int]:
    """Parse strict YAML frontmatter and return (metadata, body_markdown, body_start_line).

    Raises FrontmatterError with exact 1-based line numbers on syntax issues.
    """
    normalized = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("Missing opening YAML frontmatter fence '---' on line 1.", line=1)

    close_idx: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            close_idx = idx
            break
    if close_idx is None:
        raise FrontmatterError("Missing closing YAML frontmatter fence '---'.", line=1)

    data: dict[str, object] = {}
    current_list_key: str | None = None

    for idx in range(1, close_idx):
        lineno = idx + 1
        raw_line = lines[idx]
        if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip(" \t"))]:
            raise FrontmatterError("Tab indentation is not allowed in YAML frontmatter.", line=lineno)

        stripped_ws = raw_line.lstrip(" ")
        if not stripped_ws or stripped_ws.startswith("#"):
            continue

        # Block list item
        if stripped_ws == "-" or stripped_ws.startswith("- "):
            if current_list_key is None:
                raise FrontmatterError(
                    "Unexpected list item '-' without a preceding key.",
                    line=lineno,
                )
            item_raw = _strip_inline_comment(stripped_ws[1:].strip())
            if not item_raw:
                raise FrontmatterError(
                    f"Empty block list item under key '{current_list_key}'.",
                    line=lineno,
                )
            item_val = _parse_scalar(item_raw, lineno, allow_bool=False)
            target_list = data[current_list_key]
            assert isinstance(target_list, list)
            target_list.append(str(item_val))
            continue

        # Top-level key: value
        if raw_line.startswith(" "):
            raise FrontmatterError(
                f"Unexpected indentation on line: {raw_line!r}.",
                line=lineno,
            )

        match = _TOP_KEY_RE.match(raw_line)
        if not match:
            raise FrontmatterError(f"Malformed YAML line: {raw_line!r}.", line=lineno)

        key = match.group(1)
        if key in data:
            raise FrontmatterError(f"Duplicate frontmatter key '{key}'.", line=lineno)

        val_raw = _strip_inline_comment(match.group(2).strip())
        if not val_raw:
            # Expect block list items on subsequent lines, or empty value if none follow
            data[key] = []
            current_list_key = key
            continue

        current_list_key = None
        if val_raw.startswith("["):
            data[key] = _parse_flow_list(val_raw, lineno)
        else:
            data[key] = _parse_scalar(val_raw, lineno, allow_bool=True)

    # Disallow dangling empty block key with zero items (require explicit '[]' or value)
    for idx in range(1, close_idx):
        lineno = idx + 1
        raw_line = lines[idx]
        if raw_line.startswith(" ") or not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        match = _TOP_KEY_RE.match(raw_line)
        if match:
            key = match.group(1)
            val_raw = _strip_inline_comment(match.group(2).strip())
            if not val_raw and data.get(key) == []:
                raise FrontmatterError(
                    f"Key '{key}' has no value or list items; use '[]' for an empty list.",
                    line=lineno,
                )

    body_lines = lines[close_idx + 1 :]
    body_markdown = "\n".join(body_lines).lstrip("\n")
    return data, body_markdown, close_idx + 2


def extract_sections(body_markdown: str) -> tuple[list[str], dict[str, str]]:
    """Extract ordered '##' Markdown headings and their bodies, ignoring fenced code blocks."""
    order: list[str] = []
    buffers: dict[str, list[str]] = {}
    current_heading: str | None = None
    in_fence = False
    fence_marker = ""

    for line in body_markdown.replace("\r\n", "\n").split("\n"):
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            if current_heading is not None:
                buffers[current_heading].append(line)
            continue

        if not in_fence:
            heading_match = _SECTION_RE.match(line)
            if heading_match:
                heading = heading_match.group(1).strip().rstrip("#").strip()
                if heading not in buffers:
                    order.append(heading)
                    buffers[heading] = []
                current_heading = heading
                continue

        if current_heading is not None:
            buffers[current_heading].append(line)

    sections = {h: "\n".join(buffers[h]).strip() for h in order}
    return order, sections
