"""Standalone stdlib-only CLI; usable outside the application's Python environment."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True)
    commands = parser.add_subparsers(dest="action", required=True)
    for name in ("status", "connect", "network"):
        commands.add_parser(name)
    ssh = commands.add_parser("ssh")
    ssh.add_argument("--command", required=True)
    ssh.add_argument("--timeout", type=int, default=30)
    publish = commands.add_parser("publish")
    publish.add_argument("--json", required=True, dest="values")
    publish.add_argument("--source", default="agent")
    for name in ("camera", "monitor"):
        sub = commands.add_parser(name)
        sub.add_argument("operation", choices=("start", "stop"))
        if name == "camera":
            sub.add_argument("--source", default="/dev/video0")
    args = vars(parser.parse_args(argv))
    try:
        runtime = json.loads(Path(args.pop("runtime")).read_text(encoding="utf-8"))
        if "values" in args:
            args["values"] = json.loads(args["values"])
        args["target"] = runtime["target"]
        request = urllib.request.Request(runtime["url"], data=json.dumps(args).encode("utf-8"),
                                         headers={"Authorization": "Bearer " + runtime["token"],
                                                  "Content-Type": "application/json"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=max(30, min(args.get("timeout", 30), 600)) + 15) as response:
            result = json.load(response)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
