from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Tuple

from dotenv import load_dotenv

# Track which project roots have already been processed to avoid re-loading.
_LOADED_ROOTS: set[str] = set()


def _default_env_paths(root: Path) -> List[Tuple[Path, bool]]:
    """
    Return default env file locations with override behavior.

    Order matters: later entries can override earlier ones when `override=True`.
    """
    return [
        (root / ".env", False),
        (root / "api" / ".env", False),
        (root / ".env.local", True),
        (root / "api" / ".env.local", True),
    ]


def load_env_once(
    project_root: Path | str | None = None,
    *,
    extra_paths: Iterable[Tuple[Path, bool]] | None = None,
    log: bool = True,
) -> List[Path]:
    """
    Load environment variables from standard project locations exactly once.

    Args:
        project_root: Base path to look for env files. Defaults to this file's parent.
        extra_paths: Optional iterable of (path, override) to include after defaults.
        log: When True, prints a short summary of what was loaded.

    Returns:
        List of env file paths that were successfully loaded (empty if already loaded).
    """
    root_path = Path(project_root) if project_root else Path(__file__).resolve().parent
    root_key = str(root_path.resolve())
    if root_key in _LOADED_ROOTS:
        return []

    env_paths: List[Tuple[Path, bool]] = _default_env_paths(root_path)
    if extra_paths:
        env_paths.extend(list(extra_paths))

    loaded: List[Path] = []
    for path, should_override in env_paths:
        if path.exists():
            load_dotenv(path, override=should_override)
            loaded.append(path)

    _LOADED_ROOTS.add(root_key)

    if log:
        summary = ", ".join(str(p) for p in loaded) if loaded else "none found"
        print(f"[env_loader] env files loaded: {summary}")

    return loaded

