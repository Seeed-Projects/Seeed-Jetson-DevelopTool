"""Console entry point for the packaged Seeed Jetson Developer GUI."""

from __future__ import annotations

import argparse
import os

from seeed_jetson_develop import __version__


def _launch_gui() -> int:
    os.environ.setdefault("NO_AT_BRIDGE", "1")
    os.environ.setdefault("QT_ACCESSIBILITY", "0")

    from seeed_jetson_develop.gui.main_window_v2 import main as gui_main

    gui_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seeed-jetson-developer",
        description="Launch the Seeed Jetson Developer Tool GUI.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="gui",
        choices=["gui"],
        help="Command to run. Defaults to launching the GUI.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "gui":
        return _launch_gui()
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
