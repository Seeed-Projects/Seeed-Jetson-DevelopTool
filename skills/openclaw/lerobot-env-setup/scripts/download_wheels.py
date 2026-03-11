#!/usr/bin/env python3
"""
download_wheels.py
Download Jetson torch/torchvision wheel files from SharePoint.

SharePoint sharing links set a FedAuth cookie on the first 302 redirect,
then serve the file on the redirected URL using that cookie.
requests.Session() handles this automatically.

Usage:
    python3 download_wheels.py [--dest <dir>]

Exit codes:
    0  all files downloaded (or already present)
    1  one or more downloads failed
"""

import argparse
import sys
from pathlib import Path

WHEELS = {
    "torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl": (
        "https://seeedstudio88-my.sharepoint.com/:u:/g/personal/"
        "youjiang_yu_seeedstudio88_onmicrosoft_com/"
        "IQCPB-wlwOrsSZNkhH9I27DMAcXbUvnXhRmshioXZz-N4Jk?e=7lNXct&download=1"
    ),
    "torchvision-0.23.0-cp310-cp310-linux_aarch64.whl": (
        "https://seeedstudio88-my.sharepoint.com/:u:/g/personal/"
        "youjiang_yu_seeedstudio88_onmicrosoft_com/"
        "IQBerMERh1BARK9-J5_S5NpvAdV_v9YgOh7BtPCa4Ne5Qho?e=DBWNMD&download=1"
    ),
}

CHUNK = 65536  # 64 KB


def _sizeof_fmt(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num //= 1024
    return f"{num:.1f} TB"


def download(filename: str, url: str, dest: Path) -> bool:
    try:
        import requests
    except ImportError:
        print("[error] requests not installed. Run: pip install requests", file=sys.stderr)
        return False

    target = dest / filename
    if target.exists():
        print(f"[skip]  {filename} already exists ({_sizeof_fmt(target.stat().st_size)})")
        return True

    print(f"[get]   {filename}")
    try:
        # Session carries FedAuth cookie across the SharePoint 302 redirect
        with requests.Session() as s:
            s.headers["User-Agent"] = "Mozilla/5.0"
            r = s.get(url, stream=True, allow_redirects=True, timeout=60)
            r.raise_for_status()

            # Sanity check: SharePoint error pages are HTML, not wheels
            ct = r.headers.get("Content-Type", "")
            if "html" in ct:
                print(f"[error] Got HTML instead of binary — URL may have expired", file=sys.stderr)
                return False

            total = int(r.headers.get("Content-Length", 0))
            received = 0
            tmp = target.with_suffix(".tmp")
            with tmp.open("wb") as f:
                for chunk in r.iter_content(chunk_size=CHUNK):
                    f.write(chunk)
                    received += len(chunk)
                    if total:
                        pct = received * 100 // total
                        print(f"\r        {pct:3d}%  {_sizeof_fmt(received)} / {_sizeof_fmt(total)}", end="", flush=True)
            print()
            tmp.rename(target)
            print(f"[done]  {filename} ({_sizeof_fmt(received)})")
            return True

    except Exception as e:
        print(f"[error] {filename}: {e}", file=sys.stderr)
        if (dest / f"{filename}.tmp").exists():
            (dest / f"{filename}.tmp").unlink()
        return False


def main():
    p = argparse.ArgumentParser(description="Download Jetson torch/torchvision wheels")
    p.add_argument("--dest", default=".", help="Directory to save wheels (default: current dir)")
    args = p.parse_args()

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    failed = []
    for filename, url in WHEELS.items():
        if not download(filename, url, dest):
            failed.append(filename)

    if failed:
        print(f"\n[fail]  {len(failed)} file(s) not downloaded:", file=sys.stderr)
        for f in failed:
            print(f"        {f}", file=sys.stderr)
        sys.exit(1)

    print(f"\n[ok]    All wheels ready in: {dest.resolve()}")
    print("        Next: pip install <wheel>.whl")


if __name__ == "__main__":
    main()
