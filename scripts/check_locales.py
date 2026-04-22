from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / "seeed_jetson_develop" / "locales"


def load_dir(lang: str) -> dict[str, str]:
    locale_dir = LOCALES_DIR / lang
    if not locale_dir.is_dir():
        raise ValueError(f"Missing locale directory: {locale_dir}")
    merged: dict[str, str] = {}
    for file_path in sorted(locale_dir.glob("*.json")):
        payload = json.loads(file_path.read_text(encoding="utf-8-sig"))
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
    langs = sorted(path.name for path in LOCALES_DIR.iterdir() if path.is_dir())
    if "en" not in langs:
        print("Missing required baseline locale: en")
        return 1

    try:
        payloads = {lang: load_dir(lang) for lang in langs}
    except ValueError as exc:
        print(exc)
        return 1

    baseline = payloads["en"]
    baseline_keys = set(baseline)
    failed = False
    for lang in langs:
        if lang == "en":
            continue
        keys = set(payloads[lang])
        missing = sorted(baseline_keys - keys)
        extra = sorted(keys - baseline_keys)
        if missing or extra:
            failed = True
            if missing:
                print(f"Keys missing in {lang}:")
                for key in missing:
                    print(f"  {key}")
            if extra:
                print(f"Keys only in {lang}:")
                for key in extra:
                    print(f"  {key}")

    if failed:
        return 1

    counts = {lang: len(payloads[lang]) for lang in langs}
    print(
        "Locale check passed: "
        + ", ".join(f"{lang}={count}" for lang, count in counts.items())
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
