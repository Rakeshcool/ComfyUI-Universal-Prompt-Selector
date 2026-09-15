"""Persistent storage for the universal prompt library.

A tiny JSON-backed CRUD store. The library lives in the ComfyUI user
directory so it survives restarts and is shared across all workflows:

    <ComfyUI>/user/ComfyUI-Universal-Prompt-Selector/prompts.json

Design notes:
    - All mutating operations are serialized with an RLock and written
      atomically (temp file + os.replace), so concurrent queue runs or
      HTTP requests can never corrupt the file.
    - Prompt ids are stable strings (uuid4 hex), so workflows keep
      referencing the same prompt even if its text is edited later.
    - The store is written with UTF-8 (no BOM) and pretty-printed so the
      file stays human-editable.
    - A small set of useful starter prompts is seeded on first run so the
      selector combo is never empty for new users.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_STORE_ENV = "UPSEL_STORE_PATH"  # overridable for tests / portable setups
_DIRNAME = "ComfyUI-Universal-Prompt-Selector"
_FILENAME = "prompts.json"


def _now_iso() -> str:
    """UTC timestamp, second precision, ISO-8601."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class StorageError(Exception):
    """Raised for storage-layer failures (I/O errors, corrupt JSON)."""


def _user_dir() -> str:
    try:
        import folder_paths  # noqa: PLC0415 - only importable inside ComfyUI

        base = folder_paths.get_user_directory()
    except Exception:
        # Outside ComfyUI (unit tests, standalone tools): use a local dir.
        base = os.path.join(os.getcwd(), ".upsel_test_user")
    return os.path.join(base, _DIRNAME)


def _store_path() -> str:
    override = os.environ.get(_STORE_ENV)
    if override:
        return override
    return os.path.join(_user_dir(), _FILENAME)


def _default_seed() -> List[Dict[str, Any]]:
    """Starter prompts seeded on first run."""
    now = _now_iso()
    return [
        {
            "id": "video-prompt-writer",
            "name": "Video Prompt Writer",
            "description": "Turns a short description into a detailed video-generation prompt.",
            "prompt": (
                "You are an expert cinematic video prompt writer. Convert the user's "
                "description into a detailed video-generation prompt.\n\n"
                "Always include: subject, action, camera movement, lens and framing, "
                "lighting, mood, and style references. Keep the output a single "
                "cohesive paragraph with no preamble."
            ),
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "image-prompt-writer",
            "name": "Image Prompt Writer",
            "description": "Expands a rough idea into a rich image-generation prompt.",
            "prompt": (
                "You are an expert image prompt writer. Expand the user's idea into a "
                "vivid image-generation prompt.\n\nInclude: subject and details, "
                "composition and framing, lighting, color palette, art style and "
                "medium, and quality descriptors. Output only the final prompt."
            ),
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "ocr-expert",
            "name": "OCR Expert",
            "description": "Extracts and structures text from document images.",
            "prompt": (
                "You are an OCR expert. Extract all text from the user's document "
                "image exactly as written, preserving layout with line breaks. "
                "Output only the extracted text, no commentary."
            ),
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "coding-expert",
            "name": "Coding Expert",
            "description": "Answers technical questions with precise, runnable code.",
            "prompt": (
                "You are a senior software engineer. Answer the user's request with "
                "precise, runnable code and a short explanation. Prefer standard "
                "library solutions, note edge cases, and never invent APIs."
            ),
            "created_at": now,
            "updated_at": now,
        },
    ]


class PromptStore:
    """Thread-safe JSON-backed CRUD store for system prompts."""

    SCHEMA_VERSION = 1

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or _store_path()
        self._lock = threading.RLock()
        self._cache: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------ io

    @property
    def path(self) -> str:
        return self._path

    def _load(self) -> Dict[str, Any]:
        if self._cache is not None:
            return self._cache
        if not os.path.exists(self._path):
            data = {
                "version": self.SCHEMA_VERSION,
                "prompts": _default_seed(),
            }
        else:
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                # Never destroy user data: back the corrupt file up and start fresh.
                backup = self._path + ".corrupt-" + _now_iso().replace(":", "")
                try:
                    os.replace(self._path, backup)
                except OSError:
                    pass
                raise StorageError(
                    f"Prompt library at {self._path} was corrupt; backed up to {backup}. "
                    "A fresh library has been created."
                ) from e
            except OSError as e:
                raise StorageError(f"Cannot read prompt library {self._path}: {e}") from e
            if not isinstance(data, dict) or not isinstance(data.get("prompts"), list):
                raise StorageError(f"Prompt library at {self._path} has an unexpected format.")
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._cache = data
        self._flush()
        return data

    def _flush(self) -> None:
        assert self._cache is not None
        tmp = self._path + ".tmp"
        payload = json.dumps(self._cache, indent=2, ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, self._path)

    # ---------------------------------------------------------------- crud

    def list_prompts(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """All prompts, sorted by name (case-insensitive)."""
        with self._lock:
            data = self._load()
            items = [
                p
                for p in data["prompts"]
                if include_deleted or not p.get("deleted")
            ]
            return [dict(p) for p in sorted(items, key=lambda p: p.get("name", "").lower())]

    def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._load()
            for p in data["prompts"]:
                if p.get("id") == prompt_id and not p.get("deleted"):
                    return dict(p)
        return None

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Case-insensitive lookup by name; first match wins."""
        target = (name or "").strip().lower()
        if not target:
            return None
        with self._lock:
            for p in self.list_prompts():
                if p.get("name", "").strip().lower() == target:
                    return p
        return None

    def create_prompt(self, name: str, prompt: str, description: str = "") -> Dict[str, Any]:
        name = (name or "").strip()
        if not name:
            raise StorageError("Prompt name cannot be empty.")
        if not (prompt or "").strip():
            raise StorageError("Prompt text cannot be empty.")
        with self._lock:
            data = self._load()
            if self.get_by_name(name) is not None:
                raise StorageError(f"A prompt named {name!r} already exists.")
            now = _now_iso()
            item = {
                "id": uuid.uuid4().hex,
                "name": name,
                "description": (description or "").strip(),
                "prompt": prompt,
                "created_at": now,
                "updated_at": now,
            }
            data["prompts"].append(item)
            self._flush()
            return dict(item)

    def update_prompt(
        self,
        prompt_id: str,
        name: Optional[str] = None,
        prompt: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            data = self._load()
            for p in data["prompts"]:
                if p.get("id") == prompt_id and not p.get("deleted"):
                    if name is not None:
                        name = name.strip()
                        if not name:
                            raise StorageError("Prompt name cannot be empty.")
                        other = self.get_by_name(name)
                        if other is not None and other["id"] != prompt_id:
                            raise StorageError(f"A prompt named {name!r} already exists.")
                        p["name"] = name
                    if prompt is not None:
                        if not prompt.strip():
                            raise StorageError("Prompt text cannot be empty.")
                        p["prompt"] = prompt
                    if description is not None:
                        p["description"] = description.strip()
                    p["updated_at"] = _now_iso()
                    self._flush()
                    return dict(p)
        raise StorageError(f"No prompt with id {prompt_id!r}.")

    def delete_prompt(self, prompt_id: str) -> Dict[str, Any]:
        with self._lock:
            data = self._load()
            for i, p in enumerate(data["prompts"]):
                if p.get("id") == prompt_id and not p.get("deleted"):
                    removed = data["prompts"].pop(i)
                    self._flush()
                    return dict(removed)
        raise StorageError(f"No prompt with id {prompt_id!r}.")


# Module-level singleton used by the nodes and HTTP routes.
_store: Optional[PromptStore] = None
_store_lock = threading.Lock()


def get_store() -> PromptStore:
    """Process-wide PromptStore (path fixed at first use)."""
    global _store
    with _store_lock:
        if _store is None:
            _store = PromptStore()
        return _store


def reset_store_for_tests(path: Optional[str] = None) -> PromptStore:
    """Test helper: swap the singleton for an isolated store."""
    global _store
    with _store_lock:
        _store = PromptStore(path) if path else PromptStore()
        return _store
