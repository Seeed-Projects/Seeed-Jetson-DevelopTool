#!/usr/bin/env python3
"""Native MCP with synthetic MOCK gripper contact, only for offline validation.

This is not a hardware server entrypoint. Guard profiles before importing MCP.
"""

import os
import sys


def main():
    if (os.environ.get("CASCADE_ARM") != "mock"
            or os.environ.get("CASCADE_CAMERAS") != "mock"
            or any(os.environ.get(key) for key in ("CASCADE_ARMS", "CASCADE_ROBOT", "CASCADE_BASE"))):
        print("mock contact fixture refuses any non-mock or composed selector", file=sys.stderr)
        return 2
    from cascade.config import load_demo_config
    cfg = load_demo_config(arm="mock", cameras=["mock"], llm="mock")
    if cfg.arm.type != "mock" or any(c.get("type") != "mock" for c in cfg.cameras):
        print("mock contact fixture refuses profiles with physical backends", file=sys.stderr)
        return 2
    from cascade.control.mock_arm import MockArm
    original_init = MockArm.__init__

    def contact_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.object_stop_frac = 0.45

    MockArm.__init__ = contact_init
    print("[rebot-skill-smoke] synthetic MockArm contact at 45% travel; no physical evidence", file=sys.stderr)
    from cascade.apps.mcp_server import main as mcp_main
    return mcp_main()


if __name__ == "__main__":
    raise SystemExit(main())
