"""
各设备 Recovery 模式进入指南（中文）
数据结构：
product_key -> {
    "title", "cable", "steps": [...], "usb_ids": [...],
    "image_url", "local_image"
}
"""

# USB ID 组合
NX_IDS = [
    ("Orin NX 16GB", "0955:7323"),
    ("Orin NX 8GB",  "0955:7423"),
]
NANO_IDS = [
    ("Orin Nano 8GB", "0955:7523"),
    ("Orin Nano 4GB", "0955:7623"),
]
NX_NANO_IDS = NX_IDS + NANO_IDS
NX_NANO_XAVIER_IDS = NX_NANO_IDS + [("Xavier NX", "0955:7e19")]
AGX_IDS = [
    ("AGX Orin 32GB", "0955:7223"),
    ("AGX Orin 64GB", "0955:7023"),
]

GUIDES = {
    # ── Mini 系列 ──────────────────────────────────────────────────────────────
    "mini": {
        "title": "reComputer Mini — 进入 Recovery 模式",
        "cable": "USB Micro-B 数据线",
        "steps": [
            "将 USB Micro-B 线连接 USB2.0 DEVICE 口与 Ubuntu 主机。",
            "用细针按住 RECOVERY 孔内的按钮并保持。",
            "接通电源。",
            "松开 RECOVERY 按钮。",
        ],
        "usb_ids": NX_NANO_IDS,
        "image_url": "https://files.seeedstudio.com/wiki/reComputer-Jetson/mini/reComputer_mini_rec.png",
        "local_image": "seeed_jetson_develop/assets/recovery/reComputer_mini_rec.png",
        "note": None,
    },

    # ── Robotics 系列 ──────────────────────────────────────────────────────────
    "robotics": {
        "title": "reComputer Robotics — 进入 Recovery 模式",
        "cable": "USB Type-C 数据线",
        "steps": [
            "将拨码开关切至 RESET 档位。",
            "连接电源线，为载板上电。",
            "用 USB Type-C 数据线将载板与 Ubuntu 主机连接。",
            "在主机终端执行 lsusb，确认设备已进入 Recovery 模式。",
        ],
        "usb_ids": NX_NANO_IDS,
        "image_url": "https://files.seeedstudio.com/wiki/reComputer-Jetson/robotics_j401/flash1.jpg",
        "local_image": "seeed_jetson_develop/assets/recovery/flash1.jpg",
        "note": None,
    },

    # ── Super 系列 ─────────────────────────────────────────────────────────────
    "super": {
        "title": "reComputer Super — 进入 Recovery 模式",
        "cable": "USB Type-C 数据线",
        "steps": [
            "将拨码开关切至 RESET 档位。",
            "连接电源线，为载板上电。",
            "用 USB Type-C 数据线将载板与 Ubuntu 主机连接。",
            "在主机终端执行 lsusb，确认设备已进入 Recovery 模式。",
        ],
        "usb_ids": NX_NANO_IDS,
        "image_url": "https://files.seeedstudio.com/wiki/reComputer-Jetson/reComputer-super/flash.jpg",
        "local_image": "seeed_jetson_develop/assets/recovery/flash.jpg",
        "note": None,
    },

    # ── Classic 系列 ───────────────────────────────────────────────────────────
    "classic": {
        "title": "reComputer J401 — 进入 Recovery 模式",
        "cable": "USB Type-C 数据线",
        "steps": [
            "用跳线短接 FC REC 引脚与 GND 引脚（参考下方引脚图）。",
            "将电源适配器连接至设备，为 reComputer 上电。",
            "用 USB Type-C 数据线将载板与 Ubuntu 主机连接。",
            "在主机终端执行 lsusb，确认设备已进入 Recovery 模式。",
        ],
        "usb_ids": NX_NANO_IDS,
        "image_url": "https://files.seeedstudio.com/wiki/reComputer-J4012/1.png",
        "local_image": "seeed_jetson_develop/assets/recovery/1.png",
        "note": "⚠ 使用 Orin NX 16GB/8GB 模组时，请勿开启 MAXN SUPER 模式，载板散热不足以支撑该模式，强制开启可能损坏模组。",
    },

    # ── Industrial 系列 ────────────────────────────────────────────────────────
    "industrial": {
        "title": "reComputer Industrial — 进入 Recovery 模式",
        "cable": "USB Type-C 数据线",
        "steps": [
            "用 USB Type-C 线将 USB2.0 DEVICE 口与电脑连接。",
            "用细针按住 RECOVERY 孔内的按钮并保持。",
            "将随附的两针端子电源连接器接到板上电源口，连接电源适配器开机。",
            "松开 RECOVERY 按钮。",
            "在主机终端执行 lsusb，确认设备已进入 Recovery 模式。",
        ],
        "usb_ids": NX_NANO_XAVIER_IDS,
        "image_url": "https://files.seeedstudio.com/wiki/reComputer-Industrial/97.png",
        "local_image": "seeed_jetson_develop/assets/recovery/97.png",
        "note": None,
    },

    # ── reServer Industrial 系列 ───────────────────────────────────────────────
    "reserver": {
        "title": "reServer Industrial — 进入 Recovery 模式",
        "cable": "USB Type-C 数据线",
        "steps": [
            "用 USB Type-C 线将 DEVICE 口与电脑连接。",
            "用细针按住 REC 孔内的按钮并保持。",
            "将随附的两针端子电源连接器接到板上电源口，连接电源适配器开机。",
            "松开 REC 按钮。",
            "在主机终端执行 lsusb，确认设备已进入 Recovery 模式。",
        ],
        "usb_ids": NX_NANO_XAVIER_IDS,
        "image_url": "https://files.seeedstudio.com/wiki/reServer-Industrial/4.jpg",
        "local_image": "seeed_jetson_develop/assets/recovery/4.jpg",
        "note": None,
    },

    # ── J501 Carrier 系列 ──────────────────────────────────────────────────────
    "j501-carrier": {
        "title": "reServer J501 Carrier Board — 进入 Recovery 模式",
        "cable": "USB Type-C 数据线",
        "steps": [
            "先用 USB Type-C 数据线将载板连接到 Ubuntu 主机。",
            "再连接电源线，为载板上电。",
            "松开强制恢复按钮。",
            "松开 REC 按钮。",
            "在主机终端执行 lsusb，确认设备已进入 Recovery 模式。",
        ],
        "usb_ids": AGX_IDS,
        "image_url": "https://files.seeedstudio.com/wiki/reComputer-Jetson/J501/button.jpg",
        "local_image": "seeed_jetson_develop/assets/recovery/button.jpg",
        "note": None,
    },

    # ── J501 Mini 系列 ─────────────────────────────────────────────────────────
    "j501mini": {
        "title": "reComputer Robotics J501 Mini — 进入 Recovery 模式",
        "cable": "USB Type-C 数据线",
        "steps": [
            "按住 RESET 按钮并保持。",
            "连接电源线为载板上电，然后松开 REC 按钮。",
            "用 USB Type-C 数据线将载板与 Ubuntu 主机连接。",
            "在主机终端执行 lsusb，确认设备已进入 Recovery 模式。",
        ],
        "usb_ids": AGX_IDS,
        "image_url": "https://files.seeedstudio.com/wiki/recomputer-j501-mini/reset.png",
        "local_image": "seeed_jetson_develop/assets/recovery/reset.png",
        "note": None,
    },

    # ── J501 Robotics 系列 ─────────────────────────────────────────────────────
    "j501-agx": {
        "title": "reComputer Robotics J501 — 进入 Recovery 模式",
        "cable": "USB Type-C 数据线",
        "steps": [
            "用 USB Type-C 线将 USB2.0 DEVICE 口与 Ubuntu 主机连接。",
            "用细针按住 RECOVERY 孔内的按钮并保持。",
            "接通电源。",
            "松开 RECOVERY 按钮。",
            "在主机终端执行 lsusb，确认设备已进入 Recovery 模式。",
        ],
        "usb_ids": AGX_IDS,
        "image_url": "https://files.seeedstudio.com/wiki/recomputer_robotic_j501/flash_1.png",
        "local_image": "seeed_jetson_develop/assets/recovery/flash_1.png",
        "note": None,
    },
}

# product key -> guide key 映射
PRODUCT_GUIDE_MAP = {
    # mini
    "j4012mini": "mini", "j4011mini": "mini",
    "j3011mini": "mini", "j3010mini": "mini",
    # robotics
    "j4012robotics": "robotics", "j4011robotics": "robotics",
    "j3011robotics": "robotics", "j3010robotics": "robotics",
    # super
    "j4012s": "super", "j4011s": "super",
    "j3011s": "super", "j3010s": "super",
    # classic
    "j4012classic": "classic", "j4011classic": "classic",
    "j3011classic": "classic", "j3010classic": "classic",
    # industrial
    "j4012industrial": "industrial", "j4011industrial": "industrial",
    "j3011industrial": "industrial", "j3010industrial": "industrial",
    "j2012industrial": "industrial", "j2011industrial": "industrial",
    # reserver
    "j4012reserver": "reserver", "j4011reserver": "reserver",
    "j3011reserver": "reserver", "j3010reserver": "reserver",
    # j501 carrier
    "j501-carrier AGX-Orin 64g": "j501-carrier",
    "j501-carrier AGX-Orin 32g": "j501-carrier",
    # j501 mini
    "j501mini-agx-orin-64g": "j501mini",
    "j501mini-agx-orin-32g": "j501mini",
    # j501 robotics
    "j501-agx-orin-64g": "j501-agx",
    "j501-agx-orin-32g": "j501-agx",
}


def get_guide(product: str) -> dict | None:
    key = PRODUCT_GUIDE_MAP.get(product)
    return GUIDES.get(key) if key else None
