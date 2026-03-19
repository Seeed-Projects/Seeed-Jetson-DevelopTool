"""PC 网络共享对话框 — 一键让 Jetson 通过 PC 上网。"""
from __future__ import annotations

import sys
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QSizePolicy, QTextEdit, QVBoxLayout,
)

from seeed_jetson_develop.gui.theme import (
    C_BG, C_CARD_LIGHT, C_GREEN, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    apply_shadow, make_button, make_card, make_label, pt,
)
from seeed_jetson_develop.modules.remote.net_share import (
    detect_wan_interface, list_interfaces,
    enable_nat, disable_nat,
)


class _NatThread(QThread):
    """后台执行 NAT 开启/关闭。"""
    done = pyqtSignal(bool, str)  # ok, log

    def __init__(self, action: str, wan: str, lan: str, sudo_pwd: str):
        super().__init__()
        self._action = action
        self._wan = wan
        self._lan = lan
        self._pwd = sudo_pwd

    def run(self):
        if self._action == "enable":
            ok, log = enable_nat(self._wan, self._lan, self._pwd)
        else:
            ok, log = disable_nat(self._wan, self._lan, self._pwd)
        self.done.emit(ok, log)


class NetShareDialog(QDialog):
    def __init__(self, parent=None, jetson_ip: str = ""):
        super().__init__(parent)
        self._thread: _NatThread | None = None
        self._sharing = False
        self._jetson_ip = jetson_ip

        self.setWindowTitle("PC 网络共享")
        self.setMinimumSize(640, 520)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        root.addWidget(make_label("PC 网络共享", 16, C_TEXT, bold=True))
        root.addWidget(make_label(
            "将 PC 的互联网连接共享给 Jetson，使 Jetson 通过 PC 上网。"
            "PC 需要有一个上网网卡（WiFi）和一个连接 Jetson 的网卡（以太网）。",
            11, C_TEXT2, wrap=True,
        ))

        # 显示已知的 Jetson IP
        if jetson_ip:
            root.addWidget(make_label(
                f"当前 Jetson IP：{jetson_ip}（已根据 SSH 连接自动匹配 LAN 网卡）",
                11, C_GREEN, wrap=True,
            ))

        # 网卡选择卡片
        card = make_card(12)
        apply_shadow(card, blur=18, y=4, alpha=60)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(12)

        # WAN 网卡
        wan_row = QHBoxLayout()
        wan_row.setSpacing(8)
        wan_row.addWidget(make_label("PC 上网网卡 (WAN)", 12, C_TEXT2))
        self._wan_combo = QComboBox()
        self._wan_combo.setMinimumWidth(200)
        wan_row.addWidget(self._wan_combo)
        wan_row.addStretch()
        cl.addLayout(wan_row)

        # LAN 网卡
        lan_row = QHBoxLayout()
        lan_row.setSpacing(8)
        lan_row.addWidget(make_label("PC 连接 Jetson 的网卡 (LAN)", 12, C_TEXT2))
        self._lan_combo = QComboBox()
        self._lan_combo.setMinimumWidth(200)
        lan_row.addWidget(self._lan_combo)
        lan_row.addStretch()
        cl.addLayout(lan_row)

        # sudo 密码（Linux）
        if sys.platform != "win32":
            pwd_row = QHBoxLayout()
            pwd_row.setSpacing(8)
            pwd_row.addWidget(make_label("PC sudo 密码", 11, C_TEXT2))
            self._sudo_edit = QLineEdit()
            self._sudo_edit.setEchoMode(QLineEdit.Password)
            self._sudo_edit.setPlaceholderText("本机管理员密码")
            self._sudo_edit.setFixedWidth(180)
            self._sudo_edit.setStyleSheet(
                f"QLineEdit {{ background:{C_CARD_LIGHT}; border:none; border-radius:8px;"
                f" padding:6px 10px; color:{C_TEXT}; font-size:{pt(11)}px; }}"
                f" QLineEdit:focus {{ background:#2a3040; }}"
            )
            pwd_row.addWidget(self._sudo_edit)
            pwd_row.addStretch()
            cl.addLayout(pwd_row)
        else:
            self._sudo_edit = None

        self._refresh_btn = make_button("刷新网卡", small=True)
        cl.addWidget(self._refresh_btn)

        # 状态
        self._status = make_label("未开启", 12, C_TEXT3)
        cl.addWidget(self._status)

        # 提示
        cl.addWidget(make_label(
            "提示：开启后 Jetson 的网关需指向 PC 的 LAN 网卡 IP，DNS 设为 8.8.8.8。"
            "可在'网络配置'对话框中通过串口完成。",
            10, C_TEXT3, wrap=True,
        ))
        root.addWidget(card)

        # 操作按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self._enable_btn = make_button("开启网络共享", primary=True, small=True)
        self._disable_btn = make_button("关闭网络共享", small=True)
        self._disable_btn.setEnabled(False)
        btn_row.addWidget(self._enable_btn)
        btn_row.addWidget(self._disable_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # 日志
        log_card = make_card(12)
        log_lay = QVBoxLayout(log_card)
        log_lay.setContentsMargins(18, 14, 18, 14)
        log_lay.setSpacing(8)
        log_lay.addWidget(make_label("执行日志", 12, C_TEXT, bold=True))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(140)
        self._log.setLineWrapMode(QTextEdit.WidgetWidth)
        self._log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._log.setStyleSheet(f"""
            QTextEdit {{
                background:{C_CARD_LIGHT}; border:none; border-radius:8px;
                color:{C_TEXT2}; padding:10px;
                font-size:{pt(10)}px; font-family:'JetBrains Mono','Consolas',monospace;
            }}
        """)
        log_lay.addWidget(self._log)
        root.addWidget(log_card, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = make_button("关闭")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        self._refresh_btn.clicked.connect(self._refresh_ifaces)
        self._enable_btn.clicked.connect(self._do_enable)
        self._disable_btn.clicked.connect(self._do_disable)

        self._refresh_ifaces()

    def _refresh_ifaces(self):
        ifaces = list_interfaces()
        wan_default = detect_wan_interface()

        self._wan_combo.clear()
        self._lan_combo.clear()
        for iface in ifaces:
            label = f"{iface['name']}  ({iface['ip']})" if iface['ip'] else iface['name']
            self._wan_combo.addItem(label, iface['name'])
            self._lan_combo.addItem(label, iface['name'])

        # 自动选择 WAN
        if wan_default:
            for i in range(self._wan_combo.count()):
                if self._wan_combo.itemData(i) == wan_default:
                    self._wan_combo.setCurrentIndex(i)
                    break

        # LAN 智能选择：如果有 Jetson IP，找同网段的 PC 网卡
        lan_picked = False
        if self._jetson_ip:
            jetson_parts = self._jetson_ip.rsplit(".", 1)[0]  # e.g. "192.168.6"
            for iface in ifaces:
                if iface["ip"] and iface["ip"].rsplit(".", 1)[0] == jetson_parts:
                    for i in range(self._lan_combo.count()):
                        if self._lan_combo.itemData(i) == iface["name"]:
                            self._lan_combo.setCurrentIndex(i)
                            lan_picked = True
                            break
                    if lan_picked:
                        break

        # 兜底：选第一个不是 WAN 的
        if not lan_picked:
            for i in range(self._lan_combo.count()):
                if self._lan_combo.itemData(i) != wan_default:
                    self._lan_combo.setCurrentIndex(i)
                    break

    def _get_wan(self) -> str:
        return self._wan_combo.currentData() or ""

    def _get_lan(self) -> str:
        return self._lan_combo.currentData() or ""

    def _get_sudo_pwd(self) -> str:
        return self._sudo_edit.text() if self._sudo_edit else ""

    def _do_enable(self):
        wan, lan = self._get_wan(), self._get_lan()
        if not wan or not lan:
            QMessageBox.warning(self, "提示", "请选择上网网卡和 Jetson 网卡。")
            return
        if wan == lan:
            QMessageBox.warning(self, "提示", "上网网卡和 Jetson 网卡不能相同。")
            return
        if sys.platform != "win32" and not self._get_sudo_pwd():
            QMessageBox.warning(self, "提示", "请输入 PC 的 sudo 密码。")
            return

        self._enable_btn.setEnabled(False)
        self._enable_btn.setText("开启中…")
        self._status.setText("正在配置…")
        self._status.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(12)}px; background:transparent;")
        self._log.clear()

        self._thread = _NatThread("enable", wan, lan, self._get_sudo_pwd())
        self._thread.done.connect(self._on_enable_done)
        self._thread.start()

    def _on_enable_done(self, ok: bool, log: str):
        self._enable_btn.setEnabled(True)
        self._enable_btn.setText("开启网络共享")
        self._log.setPlainText(log)
        if ok:
            self._sharing = True
            self._status.setText(f"已开启：{self._get_wan()} -> {self._get_lan()}")
            self._status.setStyleSheet(
                f"color:{C_GREEN}; font-size:{pt(12)}px; background:transparent; font-weight:700;")
            self._disable_btn.setEnabled(True)
        else:
            self._status.setText("开启失败，请查看日志")
            self._status.setStyleSheet(f"color:{C_RED}; font-size:{pt(12)}px; background:transparent;")

    def _do_disable(self):
        wan, lan = self._get_wan(), self._get_lan()
        self._disable_btn.setEnabled(False)
        self._disable_btn.setText("关闭中…")

        self._thread = _NatThread("disable", wan, lan, self._get_sudo_pwd())
        self._thread.done.connect(self._on_disable_done)
        self._thread.start()

    def _on_disable_done(self, ok: bool, log: str):
        self._disable_btn.setText("关闭网络共享")
        self._disable_btn.setEnabled(False)
        self._sharing = False
        self._log.append("\n" + log)
        self._status.setText("已关闭")
        self._status.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}px; background:transparent;")

    def closeEvent(self, event):
        if self._sharing:
            reply = QMessageBox.question(
                self, "网络共享仍在运行",
                "关闭窗口不会停止网络共享。\n是否先关闭共享再退出？",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Yes:
                self._do_disable()
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        super().closeEvent(event)


def open_net_share_dialog(parent=None, jetson_ip: str = "", on_state_change=None):
    dlg = NetShareDialog(parent=parent, jetson_ip=jetson_ip)
    if on_state_change:
        dlg._on_state_change = on_state_change
    dlg.exec_()
    # 对话框关闭后通知调用方当前共享状态
    if on_state_change:
        on_state_change(dlg._sharing)
