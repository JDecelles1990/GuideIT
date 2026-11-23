"""Static and PowerShell 5.1 AST contract linter for powershell_scripts/."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCRIPTS_DIR = PROJECT_ROOT / "powershell_scripts"

ALLOWED_RISK_LEVELS = {"read_only", "remediation"}
ALLOWED_EDITIONS = {"Desktop", "Core"}
ALLOWED_OUTPUT_MODES = {"json", "text"}
ALLOWED_PARAM_TYPES = {"string", "int", "bool"}

META_BLOCK_RE = re.compile(r"<#(?P<body>.*?)#>", re.DOTALL)
SYNOPSIS_RE = re.compile(r"\.SYNOPSIS\s+(?P<syn>.+?)(?=\r?\n\s*\.[A-Z_]+|\Z)", re.DOTALL)
META_JSON_RE = re.compile(r"\.PSSTORE_META\s+(?P<json>\{.*\})", re.DOTALL)
PARAM_BLOCK_RE = re.compile(
    r"param\s*\((?P<inner>.*?)\r?\n\)",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class LintResult:
    path: Path
    relative_path: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _strip_comments_for_scan(text: str) -> str:
    """Removes <# ... #> block comments and # line comments while preserving strings cleanly."""
    no_blocks = re.sub(r"<#.*?#>", "", text, flags=re.DOTALL)
    lines = []
    for line in no_blocks.splitlines():
        if line.lstrip().startswith("#"):
            lines.append("")
        else:
            lines.append(line)
    return "\n".join(lines)


def _extract_param_block(text: str) -> tuple[str | None, int | None]:
    """Extracts the top-level param(...) block using balanced parenthesis matching."""
    match = re.search(r"\bparam\s*\(", text, flags=re.IGNORECASE)
    if not match:
        return None, None
    start = match.end()
    depth = 1
    in_single = False
    in_double = False
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "'" and not in_double:
            if in_single and i + 1 < len(text) and text[i + 1] == "'":
                i += 2
                continue
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "`" and in_double:
            i += 2
            continue
        elif not in_single and not in_double:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return text[start:i], i
        i += 1
    return None, None


def _check_static_contract(path: Path, rel_path: str) -> tuple[list[str], list[str], str]:
    """Validates top comment block, .PSSTORE_META JSON, param(), error handling & compatibility."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        raw = path.read_text(encoding="utf-8-sig")
    except Exception as exc:
        return [f"Could not read UTF-8 file: {exc}"], [], ""

    block_match = META_BLOCK_RE.search(raw)
    if not block_match:
        errors.append("Missing <# ... #> header comment block with .SYNOPSIS and .PSSTORE_META.")
        return errors, warnings, raw

    header_body = block_match.group("body")
    syn_match = SYNOPSIS_RE.search(header_body)
    if not syn_match or not syn_match.group("syn").strip():
        errors.append("Missing or empty .SYNOPSIS inside header comment block.")

    meta_match = META_JSON_RE.search(header_body)
    if not meta_match:
        errors.append("Missing .PSSTORE_META JSON block inside header comment block.")
        return errors, warnings, raw

    try:
        meta: dict[str, Any] = json.loads(meta_match.group("json"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid .PSSTORE_META JSON: {exc}")
        return errors, warnings, raw

    title = meta.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append(".PSSTORE_META.title must be a non-empty string.")

    risk = meta.get("risk_level")
    if risk not in ALLOWED_RISK_LEVELS:
        errors.append(f".PSSTORE_META.risk_level must be one of {sorted(ALLOWED_RISK_LEVELS)}, got {risk!r}.")

    ps_edition = meta.get("ps_edition")
    if ps_edition not in ALLOWED_EDITIONS:
        errors.append(f".PSSTORE_META.ps_edition must be one of {sorted(ALLOWED_EDITIONS)}, got {ps_edition!r}.")

    if not isinstance(meta.get("requires_admin"), bool):
        errors.append(".PSSTORE_META.requires_admin must be a JSON boolean.")

    timeout = meta.get("timeout_seconds")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        errors.append(".PSSTORE_META.timeout_seconds must be a positive integer.")

    output_mode = meta.get("output_mode")
    if output_mode not in ALLOWED_OUTPUT_MODES:
        errors.append(f".PSSTORE_META.output_mode must be one of {sorted(ALLOWED_OUTPUT_MODES)}, got {output_mode!r}.")

    params = meta.get("params")
    if not isinstance(params, list):
        errors.append(".PSSTORE_META.params must be a JSON array.")
        params = []

    body_after_header = raw[block_match.end() :]
    if "[CmdletBinding()]" not in body_after_header:
        errors.append("Missing [CmdletBinding()] attribute.")

    # Extract param block and verify closing ) is on its own line (as required for injector compatibility)
    param_inner, close_idx = _extract_param_block(body_after_header)
    if param_inner is None or close_idx is None:
        errors.append("Missing valid param(...) block.")
        param_inner = ""
        after_param = body_after_header
    else:
        line_start = body_after_header.rfind("\n", 0, close_idx) + 1
        before_close = body_after_header[line_start:close_idx]
        if (param_inner.strip() or params) and before_close.strip():
            errors.append("Closing ')' of param(...) must appear on its own line.")
        # Check for nested parens inside Parameter attributes vs disallowed ValidateSet/ValidateRange
        if re.search(r"\[Validate(Set|Range|Pattern|Length)\s*\(", param_inner, re.IGNORECASE):
            errors.append("Disallowed [Validate*(...)] attribute with nested parentheses inside param(...).")
        after_param = body_after_header[close_idx + 1 :]

    # Validate each declared parameter against .PSSTORE_META.params
    for p in params:
        if not isinstance(p, dict):
            errors.append(f"Parameter metadata entry must be an object: {p!r}")
            continue
        pname = p.get("name")
        ptype = p.get("type")
        default = p.get("default")
        if not isinstance(pname, str) or not pname:
            errors.append(f"Invalid parameter name in metadata: {p!r}")
            continue
        if ptype not in ALLOWED_PARAM_TYPES:
            errors.append(f"Parameter '{pname}' has unsupported type {ptype!r}; must be string, int, or bool.")
        if ptype == "string" and isinstance(default, str) and "," in default:
            warnings.append(f"Parameter '{pname}' default contains a comma; avoid commas inside param() defaults.")

        decl_pat = re.compile(
            rf"\[{re.escape(str(ptype))}\]\s*\${re.escape(pname)}\b",
            re.IGNORECASE,
        )
        if param_inner and not decl_pat.search(param_inner):
            errors.append(f"Parameter '[ {ptype} ] ${pname}' missing or mismatched in param(...) block.")

        ref_pat = re.compile(rf"\${re.escape(pname)}\b", re.IGNORECASE)
        if not ref_pat.search(after_param):
            errors.append(f"Declared parameter '${pname}' is never referenced in the script body.")

    stripped_body = _strip_comments_for_scan(body_after_header)

    if not re.search(r"\$ErrorActionPreference\s*=\s*['\"]Stop['\"]", stripped_body):
        errors.append("Missing `$ErrorActionPreference = 'Stop'` after param(...).")

    if not (
        re.search(r"\btry\s*\{", stripped_body, re.IGNORECASE)
        and re.search(r"\bcatch\b", stripped_body, re.IGNORECASE)
        and re.search(r"\bfinally\s*\{", stripped_body, re.IGNORECASE)
    ):
        errors.append("Script must wrap execution in a `try { ... } catch { ... } finally { ... }` block.")

    # Batch-compatibility & PowerShell 5.1 safety rules
    if re.search(r"^\s*#Requires\b", body_after_header, re.MULTILINE | re.IGNORECASE):
        errors.append("Forbidden `#Requires` directive breaks PowerShell 5.1 batch script bundles.")
    if re.search(r"^\s*using\s+namespace\b", stripped_body, re.MULTILINE | re.IGNORECASE):
        errors.append("Forbidden `using namespace` breaks PowerShell 5.1 batch script bundles.")
    if "[Environment]::TickCount64" in stripped_body:
        errors.append("Forbidden `[Environment]::TickCount64` (.NET 5+ only); use [Environment]::TickCount or Win32.")

    for interactive_cmd in ("Read-Host", "Pause", "Out-GridView"):
        if re.search(rf"\b{re.escape(interactive_cmd)}\b", stripped_body, re.IGNORECASE):
            errors.append(f"Script must be non-interactive (found '{interactive_cmd}').")

    if output_mode == "json":
        if re.search(r"(?m)^\s*exit\b", stripped_body, re.IGNORECASE):
            errors.append("Forbidden top-level `exit` inside output_mode='json' script breaks batch execution.")
        if "ConvertTo-Json" not in stripped_body:
            errors.append("Missing `ConvertTo-Json` JSON envelope output in output_mode='json' script.")
        if ", @($errors)" in stripped_body or ",@($errors)" in stripped_body:
            errors.append("Do not wrap errors array with comma unary operator `, @($errors)`.")

    return errors, warnings, raw


def _run_powershell_ast_batch(paths: list[Path]) -> dict[str, list[str]]:
    """Parses all PowerShell scripts using Windows PowerShell 5.1 Language.Parser in one process."""
    if not paths:
        return {}

    encoded_paths = json.dumps([str(p.resolve()) for p in paths])
    ps_script = (
        "$ErrorActionPreference = 'Stop'\n"
        f"$paths = ConvertFrom-Json -InputObject '{encoded_paths.replace(chr(39), chr(39)*2)}'\n"
        "$out = @{}\n"
        "foreach ($p in $paths) {\n"
        "    $tokens = $null\n"
        "    $parseErrors = $null\n"
        "    [void][System.Management.Automation.Language.Parser]::ParseFile($p, [ref]$tokens, [ref]$parseErrors)\n"
        "    $msgs = @()\n"
        "    if ($parseErrors) {\n"
        "        foreach ($e in $parseErrors) {\n"
        "            $msgs += ('Line {0}: {1}' -f $e.Extent.StartLineNumber, $e.Message)\n"
        "        }\n"
        "    }\n"
        "    $out[$p] = @($msgs)\n"
        "}\n"
        "$out | ConvertTo-Json -Depth 3 -Compress\n"
    )

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except FileNotFoundError:
        return {}
    except Exception as exc:
        return {"__runner__": [f"PowerShell AST check invocation failed: {exc}"]}

    if proc.returncode != 0 or not proc.stdout.strip():
        return {
            "__runner__": [
                f"PowerShell AST check failed (rc={proc.returncode}): {proc.stderr.strip()}"
            ]
        }

    try:
        parsed = json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return {}

    return {k: list(v or []) for k, v in parsed.items() if isinstance(v, list)}


def lint_script(path: Path, root_dir: Path | None = None, run_ast: bool = True) -> LintResult:
    """Runs static contract (and optionally standalone PS 5.1 AST) checks on one script."""
    base = (root_dir or DEFAULT_SCRIPTS_DIR).resolve()
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(base).as_posix()
    except ValueError:
        rel = path.name

    errors, warnings, _ = _check_static_contract(resolved, rel)
    if run_ast and not errors:
        ast_map = _run_powershell_ast_batch([resolved])
        ast_errors = ast_map.get(str(resolved)) or ast_map.get("__runner__", [])
        for err in ast_errors:
            errors.append(f"PS 5.1 AST: {err}")

    return LintResult(
        path=resolved,
        relative_path=rel,
        passed=(len(errors) == 0),
        errors=errors,
        warnings=warnings,
    )


def run_linter(scripts_dir: Path | str = DEFAULT_SCRIPTS_DIR) -> list[LintResult]:
    """Lints all .ps1 scripts under scripts_dir using static checks + PowerShell 5.1 AST."""
    root = Path(scripts_dir).resolve()
    if not root.exists():
        return []

    ps1_files = sorted(root.rglob("*.ps1"))
    ast_errors_by_path = _run_powershell_ast_batch(ps1_files)
    global_ast_err = ast_errors_by_path.get("__runner__", [])

    results: list[LintResult] = []
    for path in ps1_files:
        resolved = path.resolve()
        rel = resolved.relative_to(root).as_posix()
        errors, warnings, _ = _check_static_contract(resolved, rel)
        for err in ast_errors_by_path.get(str(resolved), []):
            errors.append(f"PS 5.1 AST: {err}")
        for g_err in global_ast_err:
            errors.append(g_err)
        results.append(
            LintResult(
                path=resolved,
                relative_path=rel,
                passed=(len(errors) == 0),
                errors=errors,
                warnings=warnings,
            )
        )
    return results


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Lint GuideIT Master PowerShell scripts.")
    parser.add_argument(
        "scripts_dir",
        nargs="?",
        default=str(DEFAULT_SCRIPTS_DIR),
        help="Path to powershell_scripts directory (defaults to repo powershell_scripts/).",
    )
    args = parser.parse_args(argv)

    results = run_linter(Path(args.scripts_dir))
    passed_count = 0
    failed_count = 0

    for item in results:
        if item.passed:
            passed_count += 1
            print(f"[PASS] {item.relative_path}")
        else:
            failed_count += 1
            print(f"[FAIL] {item.relative_path}")
            for err in item.errors:
                print(f"   - ERROR: {err}")
        for warn in item.warnings:
            print(f"   - WARN:  {warn}")

    print(
        f"\nLinted {len(results)} script(s): {passed_count} passed, {failed_count} failed."
    )
    return 0 if failed_count == 0 and len(results) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
