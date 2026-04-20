#!/usr/bin/env python3
"""Compare two project directories and classify merge candidates.

Usage:
  python scripts/compare_project_dirs.py LEFT_DIR RIGHT_DIR

The script ignores common noise such as .git, __pycache__, .pyc files, and
prints:
  1. files only present on one side
  2. files with content differences
  3. a coarse merge recommendation for each differing file
"""

from __future__ import annotations

import argparse
import difflib
import filecmp
from dataclasses import dataclass
from pathlib import Path


IGNORE_DIRS = {
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".uv-cache",
    ".venv",
    "venv",
}
IGNORE_SUFFIXES = {".pyc", ".pyo"}
IGNORE_FILES = {"Thumbs.db", ".DS_Store"}


@dataclass
class DiffStat:
    path: str
    removed: int
    added: int
    recommendation: str
    reason: str


def wanted(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in IGNORE_DIRS for part in rel.parts):
        return False
    if path.name in IGNORE_FILES:
        return False
    if path.suffix in IGNORE_SUFFIXES:
        return False
    return path.is_file()


def collect_files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if wanted(path, root)
    }


def compute_line_delta(left: Path, right: Path) -> tuple[int, int]:
    left_lines = left.read_text(encoding="utf-8", errors="ignore").splitlines()
    right_lines = right.read_text(encoding="utf-8", errors="ignore").splitlines()
    removed = 0
    added = 0
    for line in difflib.unified_diff(left_lines, right_lines, n=0):
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith("-"):
            removed += 1
        elif line.startswith("+"):
            added += 1
    return removed, added


def classify(path: str, removed: int, added: int) -> tuple[str, str]:
    if path in {
        "seeed_jetson_develop/core/config.py",
        "setup.py",
    }:
        return "merge", "small focused change, low conflict risk"

    if path in {
        "seeed_jetson_develop/core/runner.py",
        "seeed_jetson_develop/gui/ai_chat.py",
        "seeed_jetson_develop/modules/apps/page.py",
        "seeed_jetson_develop/modules/remote/page.py",
        "seeed_jetson_develop/modules/skills/page.py",
        "seeed_jetson_develop/modules/remote/desktop_dialog.py",
    }:
        return "manual", "feature-rich file; merge selectively to avoid regressions"

    if path in {
        "seeed_jetson_develop/gui/theme.py",
    }:
        return "skip", "large UI/theme rewrite; high regression risk"

    if path in {
        "seeed_jetson_develop/modules/apps/data/apps.json",
        "seeed_jetson_develop/modules/apps/data/jetson_examples.json",
        "seeed_jetson_develop/modules/remote/desktop_remote.py",
        "seeed_jetson_develop/modules/remote/agent_install_dialog.py",
        "seeed_jetson_develop/modules/remote/jetson_init.py",
        "seeed_jetson_develop/modules/remote/native_terminal.py",
        "seeed_jetson_develop/modules/remote/net_share_dialog.py",
        "seeed_jetson_develop/gui/main_window_v2.py",
    }:
        return "manual", "safe to inspect for incremental features, but keep current fixes"

    if removed == 0 or added == 0:
        return "merge", "one-sided delta, likely additive"

    total = removed + added
    if total <= 20:
        return "merge", "small textual delta"
    if total >= 300:
        return "manual", "large diff; needs file-by-file inspection"
    return "manual", "non-trivial code diff"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left_dir", type=Path, help="current/main project directory")
    parser.add_argument("right_dir", type=Path, help="comparison project directory")
    args = parser.parse_args()

    left = args.left_dir.resolve()
    right = args.right_dir.resolve()

    if not left.is_dir():
        raise SystemExit(f"left_dir does not exist: {left}")
    if not right.is_dir():
        raise SystemExit(f"right_dir does not exist: {right}")

    left_files = collect_files(left)
    right_files = collect_files(right)

    left_only = sorted(set(left_files) - set(right_files))
    right_only = sorted(set(right_files) - set(left_files))

    diff_stats: list[DiffStat] = []
    for rel in sorted(set(left_files) & set(right_files)):
        left_path = left_files[rel]
        right_path = right_files[rel]
        same = (
            left_path.stat().st_size == right_path.stat().st_size
            and filecmp.cmp(left_path, right_path, shallow=False)
        )
        if same:
            continue
        removed, added = compute_line_delta(left_path, right_path)
        recommendation, reason = classify(rel, removed, added)
        diff_stats.append(
            DiffStat(
                path=rel,
                removed=removed,
                added=added,
                recommendation=recommendation,
                reason=reason,
            )
        )

    print(f"LEFT:  {left}")
    print(f"RIGHT: {right}")
    print()
    print(f"left_only_files: {len(left_only)}")
    print(f"right_only_files: {len(right_only)}")
    print(f"different_files: {len(diff_stats)}")
    print()

    if left_only:
        print("[left_only]")
        for rel in left_only:
            print(rel)
        print()

    if right_only:
        print("[right_only]")
        for rel in right_only:
            print(rel)
        print()

    if diff_stats:
        print("[diff_files]")
        for item in diff_stats:
            print(
                f"{item.path} | -{item.removed} +{item.added} | "
                f"{item.recommendation} | {item.reason}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
