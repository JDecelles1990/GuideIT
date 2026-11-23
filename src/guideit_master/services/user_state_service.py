"""Persistent JSON-backed user favorites and MRU recents state service."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guideit_master.paths import get_user_state_path

logger = logging.getLogger(__name__)

MAX_RECENT_ITEMS = 8
STATE_SCHEMA_VERSION = 1


@dataclass
class UserState:
    """In-memory representation of pinned favorites and recent history."""

    favorite_playbooks: list[str] = field(default_factory=list)
    recent_playbooks: list[str] = field(default_factory=list)
    favorite_scripts: list[str] = field(default_factory=list)
    recent_scripts: list[str] = field(default_factory=list)


def _normalize_playbook_id(playbook_id: str) -> str:
    return str(playbook_id).strip()


def _normalize_script_path(relative_path: str) -> str:
    return str(relative_path).strip().replace("\\", "/").lstrip("/")


def _clean_string_list(
    raw_items: Any,
    *,
    is_script: bool,
    limit: int | None = None,
) -> list[str]:
    if not isinstance(raw_items, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, str):
            continue
        norm = _normalize_script_path(item) if is_script else _normalize_playbook_id(item)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        cleaned.append(norm)
        if limit is not None and len(cleaned) >= limit:
            break
    return cleaned


class UserStateService:
    """Manages pinned favorites and MRU recents persisted to user_state.json."""

    def __init__(
        self,
        state_path: Path | None = None,
        *,
        max_recents: int = MAX_RECENT_ITEMS,
    ) -> None:
        self.state_path = (
            state_path.resolve() if state_path is not None else get_user_state_path()
        )
        self.max_recents = max(1, int(max_recents))
        self._state = UserState()
        self.load()

    def load(self) -> UserState:
        """Load state from disk, falling back gracefully on missing or malformed JSON."""
        if not self.state_path.is_file():
            self._state = UserState()
            return self._state

        try:
            raw_text = self.state_path.read_text(encoding="utf-8")
            raw_data = json.loads(raw_text)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning(
                "Malformed or unreadable user state at %s (%s); using empty state.",
                self.state_path,
                exc,
            )
            self._state = UserState()
            return self._state

        if not isinstance(raw_data, dict):
            logger.warning(
                "Expected JSON object in %s, got %s; using empty state.",
                self.state_path,
                type(raw_data).__name__,
            )
            self._state = UserState()
            return self._state

        self._state = UserState(
            favorite_playbooks=_clean_string_list(
                raw_data.get("favorite_playbooks"), is_script=False
            ),
            recent_playbooks=_clean_string_list(
                raw_data.get("recent_playbooks"),
                is_script=False,
                limit=self.max_recents,
            ),
            favorite_scripts=_clean_string_list(
                raw_data.get("favorite_scripts"), is_script=True
            ),
            recent_scripts=_clean_string_list(
                raw_data.get("recent_scripts"),
                is_script=True,
                limit=self.max_recents,
            ),
        )
        return self._state

    def save(self) -> None:
        """Persist state atomically via sibling .tmp file and os.replace()."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.state_path.with_name(f"{self.state_path.name}.tmp")
        payload = {
            "schema_version": STATE_SCHEMA_VERSION,
            "favorite_playbooks": list(self._state.favorite_playbooks),
            "recent_playbooks": list(self._state.recent_playbooks),
            "favorite_scripts": list(self._state.favorite_scripts),
            "recent_scripts": list(self._state.recent_scripts),
        }
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
            os.replace(tmp_path, self.state_path)
        except Exception:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            raise

    def get_favorite_playbooks(self) -> list[str]:
        return list(self._state.favorite_playbooks)

    def get_recent_playbooks(self) -> list[str]:
        return list(self._state.recent_playbooks)

    def get_favorite_scripts(self) -> list[str]:
        return list(self._state.favorite_scripts)

    def get_recent_scripts(self) -> list[str]:
        return list(self._state.recent_scripts)

    def is_favorite_playbook(self, playbook_id: str) -> bool:
        norm = _normalize_playbook_id(playbook_id)
        return bool(norm and norm in self._state.favorite_playbooks)

    def is_favorite_script(self, relative_path: str) -> bool:
        norm = _normalize_script_path(relative_path)
        return bool(norm and norm in self._state.favorite_scripts)

    def set_favorite_playbook(self, playbook_id: str, pinned: bool) -> bool:
        norm = _normalize_playbook_id(playbook_id)
        if not norm:
            return False
        changed = False
        if pinned:
            if norm not in self._state.favorite_playbooks:
                self._state.favorite_playbooks.append(norm)
                changed = True
        else:
            if norm in self._state.favorite_playbooks:
                self._state.favorite_playbooks.remove(norm)
                changed = True
        if changed:
            self.save()
        return pinned

    def toggle_favorite_playbook(self, playbook_id: str) -> bool:
        norm = _normalize_playbook_id(playbook_id)
        if not norm:
            return False
        new_state = norm not in self._state.favorite_playbooks
        return self.set_favorite_playbook(norm, new_state)

    def record_recent_playbook(self, playbook_id: str) -> list[str]:
        norm = _normalize_playbook_id(playbook_id)
        if not norm:
            return self.get_recent_playbooks()
        if (
            self._state.recent_playbooks
            and self._state.recent_playbooks[0] == norm
            and len(self._state.recent_playbooks) <= self.max_recents
        ):
            return self.get_recent_playbooks()
        updated = [norm] + [p for p in self._state.recent_playbooks if p != norm]
        self._state.recent_playbooks = updated[: self.max_recents]
        self.save()
        return self.get_recent_playbooks()

    def set_favorite_script(self, relative_path: str, pinned: bool) -> bool:
        norm = _normalize_script_path(relative_path)
        if not norm:
            return False
        changed = False
        if pinned:
            if norm not in self._state.favorite_scripts:
                self._state.favorite_scripts.append(norm)
                changed = True
        else:
            if norm in self._state.favorite_scripts:
                self._state.favorite_scripts.remove(norm)
                changed = True
        if changed:
            self.save()
        return pinned

    def toggle_favorite_script(self, relative_path: str) -> bool:
        norm = _normalize_script_path(relative_path)
        if not norm:
            return False
        new_state = norm not in self._state.favorite_scripts
        return self.set_favorite_script(norm, new_state)

    def record_recent_script(self, relative_path: str) -> list[str]:
        norm = _normalize_script_path(relative_path)
        if not norm:
            return self.get_recent_scripts()
        if (
            self._state.recent_scripts
            and self._state.recent_scripts[0] == norm
            and len(self._state.recent_scripts) <= self.max_recents
        ):
            return self.get_recent_scripts()
        updated = [norm] + [s for s in self._state.recent_scripts if s != norm]
        self._state.recent_scripts = updated[: self.max_recents]
        self.save()
        return self.get_recent_scripts()
