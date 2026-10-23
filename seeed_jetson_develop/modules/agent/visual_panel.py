"""Live remote camera and scalar readings, independent of agent response speed."""
from __future__ import annotations

import base64
import json
import shlex
import time

from qtpy.QtCore import Qt, QThread, Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import QGridLayout, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from seeed_jetson_develop.core.runner import SSHRunner, get_runner
from seeed_jetson_develop.gui.i18n import t
from seeed_jetson_develop.gui.theme import (
    C_TEXT2, C_TEXT3, StatusBadge, make_button, make_card, make_input_field,
    make_label, make_tab_button, pt,
)
from seeed_jetson_develop.gui.widgets.empty_state_widget import EmptyStateWidget
from seeed_jetson_develop.gui.widgets.toast_notification import Toast


METRICS_SCRIPT = r'''
import glob, json, os, shutil, time
def cpu():
    row = list(map(int, open('/proc/stat').readline().split()[1:]))
    return sum(row), row[3] + row[4]
previous = cpu()
while True:
    time.sleep(2)
    current = cpu()
    delta = current[0] - previous[0]
    usage = round(100 * (1 - (current[1] - previous[1]) / delta), 1) if delta else 0
    previous = current
    mem = {k: int(v.split()[0]) for k, v in
           (line.split(':', 1) for line in open('/proc/meminfo'))}
    disk = shutil.disk_usage('/')
    values = {'cpu_percent': usage, 'memory_used_mib': (mem['MemTotal'] - mem['MemAvailable']) // 1024,
              'memory_total_mib': mem['MemTotal'] // 1024,
              'disk_free_gib': round(disk.free / 1024**3, 1),
              'load_1m': os.getloadavg()[0],
              'cameras': ', '.join(sorted(glob.glob('/dev/video*'))) or '—',
              'serial_ports': ', '.join(sorted(glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyUSB*'))) or '—'}
    for path in glob.glob('/sys/class/thermal/thermal_zone*/temp')[:1]:
        try:
            values['temperature_c'] = round(int(open(path).read()) / 1000, 1)
        except (OSError, ValueError):
            pass
    print('SEEED_DATA:' + json.dumps(values), flush=True)
'''


def camera_script(source: str) -> str:
    # JSON/repr + shell quoting keep device paths, URLs and pipelines out of shell syntax.
    return '''
import base64, time
import cv2
source = %r
if source.isdigit():
    source = int(source)
cap = cv2.VideoCapture(source, cv2.CAP_GSTREAMER) if isinstance(source, str) and '!' in source else cv2.VideoCapture(source)
if not cap.isOpened():
    raise RuntimeError('Cannot open camera; check source, permissions, driver and whether it is in use')
try:
    while True:
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError('Camera returned no frame')
        height, width = frame.shape[:2]
        if width > 640:
            frame = cv2.resize(frame, (640, max(1, int(height * 640 / width))))
        ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
        if ok:
            print('SEEED_FRAME:' + base64.b64encode(encoded).decode('ascii'), flush=True)
        time.sleep(0.2)
finally:
    cap.release()
''' % source


class DeviceStream(QThread):
    frame = Signal(bytes)
    readings = Signal(dict)
    failed = Signal(str)

    def __init__(self, runner: SSHRunner, kind: str, source="/dev/video0", parent=None):
        super().__init__(parent)
        self.runner, self.kind, self.source = runner, kind, source
        self._channel = None
        self._client = None

    def stop(self):
        self.requestInterruption()
        channel = self._channel
        if channel is not None:
            channel.close()
        if self._client is not None:
            self._client.close()

    def run(self):
        import paramiko
        client = self._client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(self.runner.host, port=self.runner.port, username=self.runner.username,
                           password=self.runner.password or None, timeout=10,
                           auth_timeout=10, banner_timeout=10, look_for_keys=True, allow_agent=True)
            if self.isInterruptionRequested():
                return
            client.get_transport().set_keepalive(30)
            script = camera_script(self.source) if self.kind == "camera" else METRICS_SCRIPT
            _, stdout, _ = client.exec_command("python3 -u -c " + shlex.quote(script) + " 2>&1", timeout=10)
            channel = self._channel = stdout.channel
            buffer = b""
            last_data = time.monotonic()
            errors = []
            while not self.isInterruptionRequested():
                if channel.recv_ready():
                    buffer += channel.recv(65536)
                    if len(buffer) > 4 * 1024 * 1024:
                        raise ValueError("Remote frame exceeds the preview size limit")
                    parts = buffer.split(b"\n")
                    buffer = parts.pop()
                    for line in parts:
                        if line.startswith(b"SEEED_FRAME:"):
                            self.frame.emit(base64.b64decode(line[12:], validate=True))
                            last_data = time.monotonic()
                        elif line.startswith(b"SEEED_DATA:"):
                            self.readings.emit(json.loads(line[11:]))
                            last_data = time.monotonic()
                        else:
                            errors.append(line.decode("utf-8", errors="replace")[:500])
                            errors = errors[-6:]
                elif channel.exit_status_ready():
                    raise RuntimeError("\n".join(errors) or "Remote stream ended")
                elif time.monotonic() - last_data > 20:
                    raise TimeoutError("No camera frame or readings received within 20 seconds")
                else:
                    self.msleep(30)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
        finally:
            self._channel = None
            client.close()
            self._client = None


class VisualPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = {}
        self._latest = {}
        self._rows = {}
        self._pixmap = None
        self._labels = []
        self._buttons = []
        self._visual_ready = set()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(pt(12))
        tabs = QHBoxLayout()
        self._tabs = []
        self._stack = QStackedWidget()
        for index, kind in enumerate(("camera", "monitor")):
            tab = make_tab_button(t(f"agent.visual.{kind}.title"), active=index == 0)
            tab.clicked.connect(lambda _=False, i=index: self._select_tab(i))
            self._tabs.append(tab)
            self._labels.append((tab, f"agent.visual.{kind}.title"))
            tabs.addWidget(tab)
        layout.addLayout(tabs)
        layout.addWidget(self._stack, 1)
        for kind in ("camera", "monitor"):
            card = make_card(with_shadow=False)
            body = QVBoxLayout(card)
            body.setContentsMargins(pt(12), pt(12), pt(12), pt(12))
            body.setSpacing(pt(8))
            body.setAlignment(Qt.AlignTop)
            header = QHBoxLayout()
            label = make_label(t(f"agent.visual.{kind}.title"), 13, bold=True)
            self._labels.append((label, f"agent.visual.{kind}.title"))
            header.addWidget(label)
            badge = StatusBadge(t("agent.visual.idle"), "default")
            header.addWidget(badge)
            setattr(self, f"_{kind}_badge", badge)
            body.addLayout(header)
            controls = QHBoxLayout()
            for operation in ("start", "stop"):
                button = make_button(t(f"agent.visual.{operation}"), small=True)
                button.clicked.connect(lambda _=False, k=kind, o=operation: self.control(k, {"operation": o}))
                self._buttons.append((button, f"agent.visual.{operation}"))
                controls.addWidget(button)
                setattr(self, f"_{kind}_{operation}", button)
            getattr(self, f"_{kind}_stop").setEnabled(False)
            if kind == "camera":
                self._source = make_input_field(t("agent.visual.camera.source"))
                self._source.setText("/dev/video0")
                body.addWidget(self._source)
                self._image = make_label("")
                self._image.setAlignment(Qt.AlignCenter)
                self._image.setMinimumHeight(pt(180))
                self._image.setMinimumWidth(1)
                self._image.hide()
                self._camera_empty = EmptyStateWidget(t("agent.visual.camera.empty"),
                                                      t("agent.visual.camera.hint"), "wifi")
                self._compact_empty(self._camera_empty)
                body.addWidget(self._camera_empty)
                body.addWidget(self._image)
            else:
                self._monitor_empty = EmptyStateWidget(t("agent.visual.monitor.empty"),
                                                       t("agent.visual.monitor.hint"), "search")
                self._compact_empty(self._monitor_empty)
                body.addWidget(self._monitor_empty)
                self._grid = QGridLayout()
                self._grid.setHorizontalSpacing(pt(12))
                self._grid.setVerticalSpacing(pt(6))
                body.addLayout(self._grid)
                self._updated = make_label("", 10, C_TEXT3, wrap=True)
                self._updated.setTextFormat(Qt.PlainText)
                body.addWidget(self._updated)
            body.addLayout(controls)
            body.addStretch(1)
            self._stack.addWidget(card)

    @staticmethod
    def _compact_empty(widget):
        widget.layout().setContentsMargins(pt(12), pt(12), pt(12), pt(12))
        widget.layout().setSpacing(pt(8))
        widget._canvas.setFixedSize(pt(80), pt(64))

    def _select_tab(self, index):
        self._stack.setCurrentIndex(index)
        for item, tab in enumerate(self._tabs):
            tab.setActive(index == item)

    def control(self, kind: str, payload: dict):
        if payload.get("operation") == "stop":
            self._stop_worker(kind)
            return
        if kind in self._workers:
            return
        runner = get_runner()
        if not isinstance(runner, SSHRunner):
            Toast.warning(self, t("agent.badge.jetson_none"))
            return
        source = payload.get("source", self._source.text().strip())
        if kind == "camera" and not source:
            Toast.warning(self, t("agent.visual.camera.missing_source"))
            return
        if kind == "camera":
            self._source.setText(source)
        worker = DeviceStream(runner, kind, source, self)
        self._workers[kind] = worker
        worker.frame.connect(lambda data, w=worker: self._show_frame(data) if self._accept(w) else None)
        worker.readings.connect(lambda values, w=worker: self.publish(values, "system") if self._accept(w) else None)
        worker.failed.connect(lambda error, k=kind, w=worker: self._failed(k, error) if self._accept(w) else None)
        worker.finished.connect(lambda k=kind, w=worker: self._finished(k, w))
        getattr(self, f"_{kind}_badge").set_status("info", t("agent.visual.starting"))
        getattr(self, f"_{kind}_start").setEnabled(False)
        getattr(self, f"_{kind}_stop").setEnabled(True)
        if kind == "camera":
            self._source.setEnabled(False)
        worker.start()

    def _accept(self, worker):
        return not worker.isInterruptionRequested() and get_runner() is worker.runner

    def _show_frame(self, data: bytes):
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self._failed("camera", t("agent.visual.camera.invalid"))
            return
        self._pixmap = pixmap
        self._camera_empty.hide()
        self._image.show()
        self._scale_frame()
        self._camera_badge.set_status("ok", t("agent.visual.live"))
        self._notify_ready("camera")

    def _notify_ready(self, kind):
        if kind not in self._visual_ready:
            self._visual_ready.add(kind)
            Toast.success(self, t("agent.visual.ready", name=t(f"agent.visual.{kind}.title")))

    def _scale_frame(self):
        if self._pixmap is not None:
            self._image.setPixmap(self._pixmap.scaled(max(pt(180), self.width() - pt(24)), pt(220),
                                                     Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        self._scale_frame()
        super().resizeEvent(event)

    def publish(self, values: dict, source="agent"):
        self._monitor_empty.hide()
        for key, value in values.items():
            identity = (source, key)
            if identity not in self._rows:
                if len(self._rows) >= 64:
                    continue
                row = len(self._rows)
                label = make_label(self._reading_name(source, key), 11, C_TEXT3, wrap=True)
                label.setTextFormat(Qt.PlainText)
                reading = make_label("", 12, C_TEXT2, wrap=True)
                reading.setTextFormat(Qt.PlainText)
                self._grid.addWidget(label, row, 0)
                self._grid.addWidget(reading, row, 1)
                self._rows[identity] = (label, reading)
            self._rows[identity][1].setText(str(value) if value is not None else "—")
        self._latest[source] = time.strftime("%H:%M:%S")
        self._refresh_updated()
        self._monitor_badge.set_status("ok", t("agent.visual.updated"))
        if source == "system":
            self._notify_ready("monitor")

    def _reading_name(self, source, key):
        if source != "system":
            return f"{source} · {key}"
        translation_key = f"agent.visual.metric.{key}"
        name = t(translation_key)
        return key if name == translation_key else name

    def _refresh_updated(self):
        self._updated.setText(t("agent.visual.timestamp", time=" · ".join(
            f"{source}: {stamp}" for source, stamp in self._latest.items())))

    def _failed(self, kind, error):
        getattr(self, f"_{kind}_badge").set_status("error", t("agent.visual.failed"))
        getattr(self, f"_{kind}_badge").setToolTip(error)
        Toast.error(self, t("agent.visual.error", error=error[:350]))

    def _stop_worker(self, kind):
        worker = self._workers.get(kind)
        if worker is not None:
            worker.stop()
        self._visual_ready.discard(kind)
        getattr(self, f"_{kind}_stop").setEnabled(False)
        getattr(self, f"_{kind}_badge").set_status("default", t("agent.visual.stopped"))

    def _finished(self, kind, worker):
        if self._workers.get(kind) is worker:
            self._workers.pop(kind)
        getattr(self, f"_{kind}_start").setEnabled(True)
        getattr(self, f"_{kind}_stop").setEnabled(False)
        if kind == "camera":
            self._source.setEnabled(True)
        worker.deleteLater()
        self._visual_ready.discard(kind)

    def reset_device(self):
        self.stop_all()
        self._pixmap = None
        self._image.clear()
        self._image.hide()
        self._camera_empty.show()
        for label, value in self._rows.values():
            self._grid.removeWidget(label)
            self._grid.removeWidget(value)
            label.deleteLater()
            value.deleteLater()
        self._rows.clear()
        self._latest.clear()
        self._updated.clear()
        self._monitor_empty.show()
        self._camera_badge.set_status("default", t("agent.visual.idle"))
        self._monitor_badge.set_status("default", t("agent.visual.idle"))

    def stop_all(self):
        for kind in list(self._workers):
            self._stop_worker(kind)

    def shutdown(self):
        self.stop_all()
        for worker in list(self._workers.values()):
            worker.wait(5000)

    def retranslate_ui(self, lang=None):
        for widget, key in self._labels + self._buttons:
            widget.setText(t(key, lang=lang))
        self._source.setPlaceholderText(t("agent.visual.camera.source", lang=lang))
        for (source, key), (label, _) in self._rows.items():
            label.setText(self._reading_name(source, key))
        for kind in ("camera", "monitor"):
            empty = getattr(self, f"_{kind}_empty")
            from qtpy.QtWidgets import QLabel
            for label in empty.findChildren(QLabel):
                key = f"agent.visual.{kind}.hint" if label.wordWrap() else f"agent.visual.{kind}.empty"
                label.setText(t(key, lang=lang))
            badge = getattr(self, f"_{kind}_badge")
            if getattr(badge, "_status", "default") != "error":  # 保留失败态，不被语言切换覆盖
                badge.set_status("info" if kind in self._workers else "default",
                                 t("agent.visual.live" if kind in self._workers else "agent.visual.idle", lang=lang))
        if self._latest:
            self._refresh_updated()
