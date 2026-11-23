"""Dual-mode Windows clipboard and RMM parameter injection service."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from guideit_master.paths import get_ps_scripts_dir, get_user_custom_scripts_dir

logger = logging.getLogger(__name__)


def format_powershell_literal(value: Any) -> str:
    """Formats a Python value as a valid PowerShell literal."""
    if isinstance(value, bool):
        return "$true" if value else "$false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        items = ", ".join(format_powershell_literal(item) for item in value)
        return f"@({items})"
    val_str = str(value).replace("'", "''")
    return f"'{val_str}'"


def inject_parameters(script_content: str, param_values: dict[str, Any]) -> str:
    """Injects UI parameter values directly into the script's param(...) block defaults."""
    if not param_values:
        return script_content

    param_block_match = re.search(
        r"\bparam\s*\((.*?)\)\s*(?=\r?\n|$)",
        script_content,
        re.DOTALL | re.IGNORECASE,
    )
    if not param_block_match:
        return script_content

    original_block = param_block_match.group(1)
    modified_block = original_block

    for name, value in param_values.items():
        if value is None:
            continue

        literal_val = format_powershell_literal(value)

        has_default_pattern = re.compile(
            rf"(\${re.escape(name)}\s*=\s*)([^,\r\n\)]+)",
            re.IGNORECASE,
        )
        if has_default_pattern.search(modified_block):
            modified_block = has_default_pattern.sub(rf"\g<1>{literal_val}", modified_block)
            continue

        no_default_pattern = re.compile(
            rf"(\${re.escape(name)})(\s*)(?=[,\r\n\)])",
            re.IGNORECASE,
        )
        if no_default_pattern.search(modified_block):
            modified_block = no_default_pattern.sub(rf"\1 = {literal_val}\2", modified_block)

    start, end = param_block_match.span(1)
    return script_content[:start] + modified_block + script_content[end:]


def combine_scripts_bundle(
    items: list[tuple[str, str, str]],
    mode_label: str = "RMM-Ready",
) -> str:
    """Combines multiple scripts into a single standalone PowerShell 5.1 script bundle."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0][2]

    total = len(items)
    sections = [
        "# ==============================================================================",
        f"# GuideIT Master (PowerShellStore) — Combined Multi-Script Bundle ({total} scripts)",
        f"# Mode: {mode_label}",
        "# ==============================================================================",
        "",
    ]

    for idx, (title, relative_path, script_content) in enumerate(items, start=1):
        safe_title = title.replace("'", "''")
        body = script_content.lstrip("\ufeff").rstrip()
        sections.extend(
            [
                "# ------------------------------------------------------------------------------",
                f"# [{idx}/{total}] {title} ({relative_path})",
                "# ------------------------------------------------------------------------------",
                "Write-Output ''",
                f"Write-Output '===== [{idx}/{total}] {safe_title} ====='",
                "try {",
                "& {",
                body,
                "}",
                "}",
                "catch {",
                f"    Write-Error ('[ERROR] Script {safe_title} failed: ' + $_.Exception.Message)",
                "}",
                "",
            ]
        )

    return "\n".join(sections).rstrip() + "\n"


class ClipboardService:
    combine_scripts_bundle = staticmethod(combine_scripts_bundle)

    def __init__(
        self,
        scripts_dir: Path | str | None = None,
        user_scripts_dir: Path | str | None = None,
    ) -> None:
        if scripts_dir is None:
            self.scripts_dir = get_ps_scripts_dir()
            self.user_scripts_dir: Path | None = (
                Path(user_scripts_dir)
                if user_scripts_dir is not None
                else get_user_custom_scripts_dir()
            )
        else:
            self.scripts_dir = Path(scripts_dir)
            self.user_scripts_dir = (
                Path(user_scripts_dir) if user_scripts_dir is not None else None
            )

    def resolve_script_path(self, relative_path: str) -> Path:
        """Resolves a relative script path, preferring user_scripts_dir over scripts_dir."""
        rel_clean = relative_path.replace("\\", "/").lstrip("/")
        if rel_clean:
            roots = [r for r in (self.user_scripts_dir, self.scripts_dir) if r is not None]
            for root in roots:
                root_resolved = root.resolve()
                try:
                    candidate = (root_resolved / rel_clean).resolve()
                except OSError:
                    continue
                if candidate.is_relative_to(root_resolved) and candidate.is_file():
                    return candidate
        raise FileNotFoundError(f"Script not found at {self.scripts_dir / relative_path}")

    def read_script(self, relative_path: str) -> str:
        """Reads script content from disk."""
        target_path = self.resolve_script_path(relative_path)

        try:
            return target_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return target_path.read_text(encoding="utf-8-sig", errors="replace")

    def get_raw_script(self, relative_path: str) -> str:
        """Returns the raw script content as stored on disk."""
        return self.read_script(relative_path)

    def get_rmm_ready_script(self, relative_path: str, param_values: dict[str, Any]) -> str:
        """Returns the script with parameter values injected into param(...) block defaults."""
        raw_content = self.read_script(relative_path)
        return inject_parameters(raw_content, param_values)

    def copy_to_clipboard(self, text: str) -> bool:
        """Copies text to the system clipboard using PySide6 or Win32 fallback."""
        try:
            from PySide6.QtGui import QGuiApplication

            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(text)
                return True
        except Exception as e:
            logger.warning("QGuiApplication clipboard unavailable: %s", e)

        try:
            import ctypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            if user32.OpenClipboard(0):
                user32.EmptyClipboard()
                h_cd = kernel32.GlobalAlloc(0x0042, len(text.encode("utf-16-le")) + 2)
                pch_data = kernel32.GlobalLock(h_cd)
                ctypes.cdll.msvcrt.wcscpy(ctypes.c_wchar_p(pch_data), text)
                kernel32.GlobalUnlock(h_cd)
                user32.SetClipboardData(13, h_cd)
                user32.CloseClipboard()
                return True
        except Exception as e:
            logger.error("Clipboard copy failed: %s", e)

        return False

    def copy_raw_script(self, relative_path: str) -> str:
        """Reads raw script from disk and copies to clipboard. Returns copied text."""
        content = self.get_raw_script(relative_path)
        self.copy_to_clipboard(content)
        return content

    def copy_rmm_ready_script(self, relative_path: str, param_values: dict[str, Any]) -> str:
        """Generates RMM-ready script with injected parameters and copies to clipboard."""
        content = self.get_rmm_ready_script(relative_path, param_values)
        self.copy_to_clipboard(content)
        return content

    def get_combined_raw_scripts(self, scripts: list[tuple[str, str]]) -> str:
        """Reads multiple raw scripts from disk and bundles them into one script."""
        items = [(title, rel_path, self.get_raw_script(rel_path)) for title, rel_path in scripts]
        return combine_scripts_bundle(items, mode_label="Raw")

    def copy_raw_scripts(self, scripts: list[tuple[str, str]]) -> str:
        """Builds a combined raw bundle for multiple scripts and copies it to clipboard."""
        content = self.get_combined_raw_scripts(scripts)
        if content:
            self.copy_to_clipboard(content)
        return content

    def get_combined_rmm_ready_scripts(
        self, scripts: list[tuple[str, str, dict[str, Any]]]
    ) -> str:
        """Injects per-script parameters and bundles multiple scripts for RMM deployment."""
        items = [
            (title, rel_path, self.get_rmm_ready_script(rel_path, params))
            for title, rel_path, params in scripts
        ]
        return combine_scripts_bundle(
            items, mode_label="RMM-Ready (With Injected Parameters)"
        )

    def copy_rmm_ready_scripts(
        self, scripts: list[tuple[str, str, dict[str, Any]]]
    ) -> str:
        """Builds a combined RMM-ready bundle and copies it to the Windows Clipboard."""
        content = self.get_combined_rmm_ready_scripts(scripts)
        if content:
            self.copy_to_clipboard(content)
        return content
