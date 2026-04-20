from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / "seeed_jetson_develop" / "locales"


def load_dir(lang: str) -> dict[str, str]:
    locale_dir = LOCALES_DIR / lang
    merged: dict[str, str] = {}
    for file_path in sorted(locale_dir.glob("*.json")):
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{file_path} must contain a JSON object")
        for key, value in payload.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError(f"{file_path} has non-string key/value: {key!r}")
            if key in merged:
                raise ValueError(f"Duplicate locale key {key!r} in {file_path}")
            merged[key] = value
    return merged


def main() -> int:
    zh = load_dir("zh-CN")
    en = load_dir("en")

    zh_only = sorted(set(zh) - set(en))
    en_only = sorted(set(en) - set(zh))

    if zh_only or en_only:
        if zh_only:
            print("Keys only in zh-CN:")
            for key in zh_only:
                print(f"  {key}")
        if en_only:
            print("Keys only in en:")
            for key in en_only:
                print(f"  {key}")
        return 1

    print(f"Locale check passed: {len(zh)} keys")
    return 0


if __name__ == "__main__":
    sys.exit(main())
