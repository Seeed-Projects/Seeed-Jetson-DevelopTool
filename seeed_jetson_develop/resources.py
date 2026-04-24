"""Runtime resource helpers for source and installed package layouts."""
from __future__ import annotations


from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent


def resolve_runtime_path(relative_path: str) -> Path | None:
    """Resolve packaged assets for both repo and site-packages installs."""
    if not relative_path:
        return None

    rel = Path(relative_path)
    candidates: list[Path] = [PROJECT_ROOT / rel]

    if rel.parts and rel.parts[0] == PACKAGE_ROOT.name:
        stripped = Path(*rel.parts[1:])
        candidates.append(PACKAGE_ROOT / stripped)
    else:
        candidates.append(PACKAGE_ROOT / rel)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
