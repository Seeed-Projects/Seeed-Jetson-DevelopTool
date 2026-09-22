"""Backup/Restore module threads — background script execution for the UI.

- :class:`BackupRestoreThread` wraps the bundled jetson-backup-restore.sh
  (official ``l4t_backup_restore.sh`` plus pre-checks).
- :class:`PrepareThread` wraps the bundled setup-workspace.sh to download and
  assemble a backup-ready ``Linux_for_Tegra`` tree from scratch.

Both stream console output to the UI and can be cancelled.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
from pathlib import Path

from qtpy.QtCore import QThread, Signal

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

BOARD_CONF_PREFIXES = ("recomputer-", "reserver-", "seeed-")

BACKUP_TOOL_REL = Path("tools/backup_restore/l4t_backup_restore.sh")


def strip_ansi(text: str) -> str:
    """Remove ANSI color escapes so log lines render cleanly in QTextEdit."""
    return _ANSI_RE.sub("", text).rstrip()


def discover_l4t_dirs() -> list[str]:
    """Auto-discover Linux_for_Tegra trees that carry the backup/restore tooling.

    Mirrors the shell script's heuristics (SSD_ROOT/bsp/*_build/Linux_for_Tegra)
    across common host locations, plus an explicit L4T_DIR env override.
    """
    found: list[str] = []
    seen: set[str] = set()
    env_dir = os.environ.get("L4T_DIR")
    if env_dir:
        found.append(env_dir)
        seen.add(env_dir)

    roots: list[Path] = [Path.home()]
    try:
        media = Path("/media")
        roots += [p for p in media.iterdir() if p.is_dir()]
        roots += [p for p in media.glob("*/*") if p.is_dir()]
    except OSError:
        pass

    for root in roots:
        globs = (
            root.glob("bsp/*_build/Linux_for_Tegra"),
            root.glob("bsp/*/Linux_for_Tegra"),
            root.glob("Linux_for_Tegra"),
        )
        for glob in globs:
            try:
                cands = sorted(glob)
            except OSError:
                # unreadable / dead mount under the root (e.g. detached SSD)
                continue
            for cand in cands:
                try:
                    is_tree = cand.is_dir() and (cand / BACKUP_TOOL_REL).is_file()
                except OSError:
                    is_tree = False
                if is_tree:
                    key = str(cand)
                    if key not in seen:
                        found.append(key)
                        seen.add(key)
    return found


def is_valid_l4t_dir(l4t_dir: str | Path) -> bool:
    """True when the directory is a Linux_for_Tegra tree with the backup tool."""
    return (Path(l4t_dir) / BACKUP_TOOL_REL).is_file()


def discover_boards(l4t_dir: str | Path) -> list[str]:
    """List supported boards from <L4T_DIR>/*.conf (same filter as the script)."""
    d = Path(l4t_dir)
    boards: set[str] = set()
    if not d.is_dir():
        return []
    for conf in sorted(d.glob("*.conf")):
        name = conf.stem
        if name.startswith(BOARD_CONF_PREFIXES):
            boards.add(name)
    return sorted(boards)


class _ScriptThread(QThread):
    """Run a shell script in a background process group and stream stdout.

    Signals:
        log: one console line (ANSI-stripped)
        done: (success: bool, message: str)

    Subclasses implement :meth:`_build_cmd` and :meth:`_build_env`.
    """

    log = Signal(str)
    progress = Signal(int, int, str)
    download_list = Signal(list)
    download_start = Signal(str)
    download_done = Signal(str)
    done = Signal(bool, str)
    phase = Signal(str)
    download_progress = Signal(str, str)

    def __init__(self):
        super().__init__()
        self._cancel = False
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None

    # ── subclass hooks ───────────────────────────────────────────────────
    def _build_cmd(self) -> list[str]:
        raise NotImplementedError

    def _build_env(self) -> dict[str, str]:
        raise NotImplementedError

    # ── control ──────────────────────────────────────────────────────────
    def cancel(self) -> None:
        with self._lock:
            self._cancel = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            self._kill_proc()

    def _should_cancel(self) -> bool:
        with self._lock:
            return self._cancel

    def _kill_proc(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            os.killpg(proc.pid, subprocess.signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, subprocess.signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass

    # ── work ─────────────────────────────────────────────────────────────
    def run(self):
        try:
            proc = subprocess.Popen(
                self._build_cmd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=self._build_env(),
                start_new_session=True,
            )
        except OSError as exc:
            self.done.emit(False, f"Failed to start script: {exc}")
            return
        self._proc = proc

        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if self._should_cancel():
                    self._kill_proc()
                    break
                text = strip_ansi(line)
                if not text:
                    continue
                if text.startswith("[PROGRESS]"):
                    parts = text.split(None, 3)
                    if len(parts) >= 4:
                        try:
                            cur, total = int(parts[1]), int(parts[2])
                            self.progress.emit(cur, total, parts[3])
                        except ValueError:
                            pass
                    continue
                if text.startswith("[PHASE]"):
                    self.phase.emit(text[len("[PHASE] "):].strip())
                    continue
                if text.startswith("[DOWNLOAD_PROGRESS]"):
                    parts = text[len("[DOWNLOAD_PROGRESS] "):].strip().split(None, 1)
                    if len(parts) == 2:
                        self.download_progress.emit(parts[0], parts[1].rstrip("%"))
                    continue
                if text.startswith("[DOWNLOADS]"):
                    items = [x.strip() for x in text[len("[DOWNLOADS] "):].split(";") if x.strip()]
                    self.download_list.emit(items)
                    continue
                if text.startswith("[DOWNLOAD_START]"):
                    name = text[len("[DOWNLOAD_START] "):].strip()
                    self.download_start.emit(name)
                    continue
                if text.startswith("[DOWNLOAD_DONE]"):
                    name = text[len("[DOWNLOAD_DONE] "):].strip()
                    self.download_done.emit(name)
                    continue
                self.log.emit(text)
            rc = proc.wait()
        finally:
            self._proc = None

        if self._should_cancel():
            self.done.emit(False, "Cancelled")
            return
        self.done.emit(rc == 0, f"exit={rc}")


class BackupRestoreThread(_ScriptThread):
    """Run one backup or restore pass against the Jetson over USB."""

    def __init__(
        self,
        script: str,
        mode: str,                 # "backup" | "restore"
        board: str,
        l4t_dir: str,
        device: str = "nvme0n1",
        wait_apx: bool = False,
        sudo_pass: str = "",
        source_dir: str = "",
    ):
        super().__init__()
        self._script = script
        self._mode = mode
        self._board = board
        self._l4t_dir = l4t_dir
        self._device = device or "nvme0n1"
        self._wait_apx = wait_apx
        self._sudo_pass = sudo_pass
        self._source_dir = source_dir

    def _build_cmd(self) -> list[str]:
        flag = "-b" if self._mode == "backup" else "-r"
        cmd = ["bash", self._script, flag, self._board]
        if self._source_dir:
            cmd.append("--source")
            cmd.append(self._source_dir)
        if self._wait_apx:
            cmd.append("--wait-apx")
        return cmd

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["L4T_DIR"] = self._l4t_dir
        env["EXTERNAL_DEVICE"] = self._device
        sudo = self._sudo_pass.strip() if self._sudo_pass else ""
        if sudo:
            env["SUDO_PASS"] = sudo
        return env


class PrepareThread(_ScriptThread):
    """Run the bundled setup-workspace.sh to download & assemble a BSP tree.

    Uses ``--minimal`` (no kernel sources / toolchain — backup/restore does not
    need them) and redirects the workspace into the user-chosen root dir.
    """

    def __init__(
        self,
        script: str,
        version: str,
        root: str,
        sudo_pass: str = "",
        minimal: bool = True,
    ):
        super().__init__()
        self._script = script
        self._version = version
        self._root = root
        self._sudo_pass = sudo_pass
        self._minimal = minimal

    def _build_cmd(self) -> list[str]:
        cmd = ["bash", self._script, f"R{self._version}", "--root", self._root]
        if self._minimal:
            cmd.append("--minimal")
        return cmd

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self._sudo_pass:
            env["SUDO_PASS"] = self._sudo_pass
        return env