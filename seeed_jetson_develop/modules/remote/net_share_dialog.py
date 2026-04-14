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
    apply_shadow, ask_question_message, make_button, make_card,
    make_label, pt, show_warning_message,
)
from seeed_jetson_develop.gui.runtime_i18n import (
    apply_language,
    get_current_lang,
    translate_text,
)
from seeed_jetson_develop.modules.remote.net_share import (
    detect_wan_interface, list_interfaces,
    enable_nat, disable_nat,
    get_interface_ip, build_jetson_gateway_cmd,
    build_jetson_time_sync_cmd,
    detect_local_proxy, build_jetson_proxy_cmd, build_jetson_clear_proxy_cmd,
)
from seeed_jetson_develop.core.runner import SSHRunner, get_runner


class _RefreshThread(QThread):
    """后台枚举网卡，避免 PowerShell 启动时阻塞 UI。"""
    done = pyqtSignal(list, object)  # ifaces, wan_default (str|None)

    def run(self):
        ifaces = list_interfaces()
        wan_default = detect_wan_interface()
        self.done.emit(ifaces, wan_default)


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


class _JetsonGatewayThread(QThread):
    """后台通过 SSH 配置 Jetson 的网关和 DNS。"""
    done = pyqtSignal(bool, str)  # ok, log

    def __init__(self, runner: SSHRunner, gateway: str, lang: str = "zh"):
        super().__init__()
        self._runner = runner
        self._gateway = gateway
        self._lang = lang

    def _msg(self, zh: str, en: str) -> str:
        return zh if self._lang == "zh" else en

    def _sync_time(self) -> str:
        cmd = build_jetson_time_sync_cmd(self._runner.sudo_password)
        rc, out = self._runner.run(cmd, timeout=20)
        if rc != 0:
            return self._msg(
                f"⚠ 时间同步执行失败：{out}",
                f"⚠ Time sync failed: {out}",
            )

        if "time_sync=ok" in out:
            return self._msg(
                f"✅ 已联网校时：{out}",
                f"✅ Time synchronized after network recovery: {out}",
            )
        if "time_sync=pending" in out:
            return self._msg(
                f"⚠ 已启用 NTP，正在等待同步：{out}",
                f"⚠ NTP enabled; waiting for sync: {out}",
            )
        return self._msg(
            f"⚠ 已尝试校时，但状态未明确：{out}",
            f"⚠ Time sync attempted, but the final state is unclear: {out}",
        )

    def _configure_proxy(self) -> str:
        """检测 PC 本地代理并自动配置到 Jetson。"""
        proxy = detect_local_proxy()
        if not proxy:
            return self._msg(
                "ℹ 未检测到 PC 本地代理，跳过代理配置",
                "ℹ No local proxy detected on PC, skipping proxy setup",
            )
        _, port = proxy
        # 代理地址用 PC 的 LAN IP（Jetson 能访问到的地址），不用 127.0.0.1
        proxy_host = self._gateway
        cmd = build_jetson_proxy_cmd(proxy_host, port)
        rc, out = self._runner.run(cmd, timeout=15)
        if rc == 0 and "proxy_set=" in out:
            proxy_url = f"http://{proxy_host}:{port}"
            return self._msg(
                f"✅ 已自动配置代理：{proxy_url}（PC 端口 {port} 检测到代理）",
                f"✅ Proxy configured: {proxy_url} (detected proxy on PC port {port})",
            )
        return self._msg(
            f"⚠ 代理配置失败：{out}",
            f"⚠ Proxy setup failed: {out}",
        )

    def run(self):
        cmd = build_jetson_gateway_cmd(self._runner.sudo_password, self._gateway)
        rc, out = self._runner.run(cmd, timeout=15)
        if rc == 0:
            # 验证连通性
            rc2, out2 = self._runner.run("ping -c 1 -W 3 8.8.8.8", timeout=10)
            if rc2 == 0:
                time_sync_log = self._sync_time()
                proxy_log = self._configure_proxy()
                self.done.emit(
                    True,
                    f"{out}\n\n"
                    f"{self._msg('✅ Jetson 已可上网（ping 8.8.8.8 成功）', '✅ Jetson is online (ping 8.8.8.8 succeeded)')}\n"
                    f"{time_sync_log}\n"
                    f"{proxy_log}",
                )
            else:
                self.done.emit(
                    True,
                    f"{out}\n\n"
                    f"{self._msg('⚠ 网关已配置，但 ping 8.8.8.8 失败，请检查 PC 端 NAT 是否生效', '⚠ Gateway configured, but ping 8.8.8.8 failed. Check whether PC-side NAT is working')}",
                )
        else:
            self.done.emit(False, self._msg(f"配置失败：{out}", f"Configuration failed: {out}"))


class NetShareDialog(QDialog):
    def __init__(self, parent=None, jetson_ip: str = ""):
        super().__init__(parent)
        self._thread: _NatThread | None = None
        self._jetson_thread: _JetsonGatewayThread | None = None
        self._refresh_thread: _RefreshThread | None = None
        self._sharing = False
        self._jetson_ip = jetson_ip
        self._lang = get_current_lang(parent)
        self._ip_label: QLabel | None = None

        self.setWindowTitle("PC 网络共享")
        self.setMinimumSize(pt(640), pt(520))
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
            self._ip_label = make_label(
                self._format_jetson_ip_text(),
                11, C_GREEN, wrap=True,
            )
            root.addWidget(self._ip_label)

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
        self._wan_combo.setMinimumWidth(pt(200))
        self._wan_combo.setMaximumWidth(pt(520))
        self._wan_combo.setMinimumHeight(pt(38))
        self._wan_combo.setStyleSheet(self._combo_style())
        wan_row.addWidget(self._wan_combo)
        wan_row.addStretch()
        cl.addLayout(wan_row)

        # LAN 网卡
        lan_row = QHBoxLayout()
        lan_row.setSpacing(8)
        lan_row.addWidget(make_label("PC 连接 Jetson 的网卡 (LAN)", 12, C_TEXT2))
        self._lan_combo = QComboBox()
        self._lan_combo.setMinimumWidth(pt(200))
        self._lan_combo.setMaximumWidth(pt(520))
        self._lan_combo.setMinimumHeight(pt(38))
        self._lan_combo.setStyleSheet(self._combo_style())
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
            self._sudo_edit.setFixedWidth(pt(180))
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
            "提示：开启后会自动通过 SSH 配置 Jetson 的网关和 DNS，使 Jetson 可以上网。"
            "如果未建立 SSH 连接，需手动在 Jetson 上配置网关指向 PC 的 LAN 网卡 IP。",
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
        self._log.setMinimumHeight(pt(140))
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

        # 应用语言翻译
        if self._lang == "en":
            apply_language(self, "en")

    def _combo_style(self) -> str:
        return (
            f"QComboBox {{"
            f" background:{C_BG};"
            f" border:1px solid rgba(255,255,255,0.14);"
            f" border-radius:10px;"
            f" padding:0 {pt(36)}px 0 {pt(12)}px;"
            f" color:{C_TEXT};"
            f" font-size:{pt(11)}px;"
            f" min-height:{pt(22)}px;"
            f"}}"
            f" QComboBox:hover {{ border-color:rgba(255,255,255,0.22); }}"
            f" QComboBox:focus {{ border-color:{C_GREEN}; }}"
            f" QComboBox::drop-down {{ border:none; width:{pt(30)}px; }}"
            f" QComboBox::down-arrow {{"
            f" width:{pt(8)}px; height:{pt(8)}px;"
            f" border-left:2px solid {C_TEXT3};"
            f" border-bottom:2px solid {C_TEXT3};"
            f" margin-right:{pt(10)}px;"
            f"}}"
            f" QComboBox QAbstractItemView {{"
            f" background:{C_CARD_LIGHT};"
            f" border:1px solid rgba(255,255,255,0.10);"
            f" border-radius:8px;"
            f" color:{C_TEXT};"
            f" font-size:{pt(11)}px;"
            f" selection-background-color:rgba(141,194,31,0.18);"
            f" selection-color:{C_GREEN};"
            f" outline:none;"
            f" padding:{pt(4)}px;"
            f"}}"
        )

    def showEvent(self, event):
        super().showEvent(event)
        from PyQt5.QtWidgets import QApplication
        geo = QApplication.primaryScreen().availableGeometry()
        max_w = int(geo.width()  * 0.95)
        max_h = int(geo.height() * 0.92)
        self.setMinimumSize(min(self.minimumWidth(), max_w),
                            min(self.minimumHeight(), max_h))
        w = min(max(self.width(),  self.minimumWidth()),  max_w)
        h = min(max(self.height(), self.minimumHeight()), max_h)
        self.resize(w, h)
        x = geo.x() + (geo.width()  - self.width())  // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    def _refresh_ifaces(self):
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText(self._tr("检测中…"))
        self._wan_combo.clear()
        self._lan_combo.clear()
        self._wan_combo.addItem(self._tr("正在检测网卡…"))
        self._lan_combo.addItem(self._tr("正在检测网卡…"))

        self._refresh_thread = _RefreshThread()
        self._refresh_thread.done.connect(self._on_ifaces_loaded)
        self._refresh_thread.start()

    def _on_ifaces_loaded(self, ifaces: list, wan_default):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText(self._tr("刷新网卡"))

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
            jetson_parts = self._jetson_ip.rsplit(".", 1)[0]
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

    def _tr(self, text: str) -> str:
        return translate_text(text, self._lang)

    def _format_jetson_ip_text(self) -> str:
        if self._lang == "en":
            return (
                f"Current Jetson IP: {self._jetson_ip} "
                f"(LAN interface auto-matched via SSH connection)"
            )
        return f"当前 Jetson IP：{self._jetson_ip}（已根据 SSH 连接自动匹配 LAN 网卡）"

    def _format_enabled_status(self) -> str:
        wan, lan = self._get_wan(), self._get_lan()
        if self._lang == "en":
            return f"Enabled: {wan} -> {lan}"
        return f"已开启：{wan} -> {lan}"

    def _format_manual_gateway_log(self) -> tuple[str, str, str]:
        lan_ip = get_interface_ip(self._get_lan())
        gw = lan_ip or ("<PC LAN interface IP>" if self._lang == "en" else "<PC LAN 网卡 IP>")
        if lan_ip:
            cmd = (
                f"sudo ip route replace default via {gw}\n"
                f"echo 'nameserver 8.8.8.8' | sudo tee /etc/resolv.conf"
            )
        else:
            cmd = (
                "sudo ip route replace default via <PC LAN IP>\n"
                "echo 'nameserver 8.8.8.8' | sudo tee /etc/resolv.conf"
            )
        if self._lang == "en":
            return (
                "⚠ No SSH connection established. Jetson gateway cannot be configured automatically.",
                f"Run these commands on Jetson manually (gateway: {gw}):",
                cmd,
            )
        return (
            "⚠ 未建立 SSH 连接，无法自动配置 Jetson 网关。",
            f"请手动在 Jetson 上执行以下命令（网关: {gw}）：",
            cmd,
        )

    def _format_missing_lan_ip_log(self) -> str:
        lan = self._get_lan()
        if self._lang == "en":
            return f"⚠ Unable to get the IP address of LAN interface ({lan}), so Jetson cannot be configured automatically."
        return f"⚠ 无法获取 LAN 网卡 ({lan}) 的 IP 地址，无法自动配置 Jetson。"

    def _format_configuring_gateway_log(self, lan_ip: str) -> str:
        if self._lang == "en":
            return f"Configuring Jetson gateway via SSH -> {lan_ip}, DNS -> 8.8.8.8 ..."
        return f"正在通过 SSH 配置 Jetson 网关 → {lan_ip}，DNS → 8.8.8.8 …"

    def _do_enable(self):
        wan, lan = self._get_wan(), self._get_lan()
        if not wan or not lan:
            show_warning_message(self, self._tr("提示"), self._tr("请选择上网网卡和 Jetson 网卡。"))
            return
        if wan == lan:
            show_warning_message(self, self._tr("提示"), self._tr("上网网卡和 Jetson 网卡不能相同。"))
            return
        if sys.platform != "win32" and not self._get_sudo_pwd():
            show_warning_message(self, self._tr("提示"), self._tr("请输入 PC 的 sudo 密码。"))
            return

        self._enable_btn.setEnabled(False)
        self._enable_btn.setText(self._tr("开启中…"))
        self._status.setText(self._tr("正在配置…"))
        self._status.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(12)}px; background:transparent;")
        self._log.clear()

        self._thread = _NatThread("enable", wan, lan, self._get_sudo_pwd())
        self._thread.done.connect(self._on_enable_done)
        self._thread.start()

    def _on_enable_done(self, ok: bool, log: str):
        self._enable_btn.setEnabled(True)
        self._enable_btn.setText(self._tr("开启网络共享"))
        self._log.setPlainText(log)
        if ok:
            self._sharing = True
            self._status.setText(self._format_enabled_status())
            self._status.setStyleSheet(
                f"color:{C_GREEN}; font-size:{pt(12)}px; background:transparent; font-weight:700;")
            self._disable_btn.setEnabled(True)
            # 自动配置 Jetson 网关和 DNS
            self._configure_jetson_gateway()
        else:
            self._status.setText(self._tr("开启失败，请查看日志"))
            self._status.setStyleSheet(f"color:{C_RED}; font-size:{pt(12)}px; background:transparent;")

    def _configure_jetson_gateway(self):
        """PC NAT 开启后，自动通过 SSH 配置 Jetson 的网关和 DNS。"""
        runner = get_runner()
        if not isinstance(runner, SSHRunner):
            warn_text, tip_text, cmd = self._format_manual_gateway_log()
            self._log.append("\n" + warn_text)
            self._log.append(tip_text)
            self._log.append(f"  {cmd}")
            return

        lan_ip = get_interface_ip(self._get_lan())
        if not lan_ip:
            self._log.append("\n" + self._format_missing_lan_ip_log())
            return

        self._log.append("\n" + self._format_configuring_gateway_log(lan_ip))
        self._jetson_thread = _JetsonGatewayThread(runner, lan_ip, self._lang)
        self._jetson_thread.done.connect(self._on_jetson_gw_done)
        self._jetson_thread.start()

    def _on_jetson_gw_done(self, ok: bool, log: str):
        self._log.append("\n" + log)

    def _do_disable(self):
        wan, lan = self._get_wan(), self._get_lan()
        self._disable_btn.setEnabled(False)
        self._disable_btn.setText(self._tr("关闭中…"))

        self._thread = _NatThread("disable", wan, lan, self._get_sudo_pwd())
        self._thread.done.connect(self._on_disable_done)
        self._thread.start()

    def _on_disable_done(self, ok: bool, log: str):
        self._disable_btn.setText(self._tr("关闭网络共享"))
        self._disable_btn.setEnabled(False)
        self._sharing = False
        self._log.append("\n" + log)
        self._status.setText(self._tr("已关闭"))
        self._status.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}px; background:transparent;")
        # 关闭共享时顺带清除 Jetson 上的代理配置
        runner = get_runner()
        if isinstance(runner, SSHRunner):
            from seeed_jetson_develop.modules.remote.net_share import build_jetson_clear_proxy_cmd
            import threading
            def _clear():
                runner.run(build_jetson_clear_proxy_cmd(), timeout=10)
            threading.Thread(target=_clear, daemon=True).start()

    def closeEvent(self, event):
        if self._sharing:
            reply = ask_question_message(
                self, self._tr("网络共享仍在运行"),
                self._tr("关闭窗口不会停止网络共享。\n是否先关闭共享再退出？"),
                buttons=QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
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
