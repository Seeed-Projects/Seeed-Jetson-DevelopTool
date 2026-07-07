"""Tests for the remote file transfer thread."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from qtpy.QtCore import QCoreApplication, QEventLoop, QTimer

from seeed_jetson_develop.modules.remote.file_download_thread import FileDownloadThread
from seeed_jetson_develop.modules.remote.file_transfer_thread import FileTransferThread


@pytest.fixture(scope="session")
def qapp() -> QCoreApplication:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    return app


class _FakeSFTP:
    def __init__(self, existing_dirs: set[str] | None = None) -> None:
        self.existing_dirs: set[str] = set(existing_dirs or ())
        self.put_calls: list[tuple[str, str]] = []
        self.mkdir_calls: list[str] = []
        self.get_calls: list[tuple[str, str]] = []
        self.closed = False

    def mkdir(self, path: str) -> None:
        self.mkdir_calls.append(path)
        if path in self.existing_dirs:
            raise OSError("directory already exists")
        self.existing_dirs.add(path)

    def put(self, local: str, remote: str, callback: Any = None) -> None:
        self.put_calls.append((local, remote))
        size = Path(local).stat().st_size
        if callback:
            callback(0, size)
            callback(size, size)

    def get(self, remote: str, local: str, callback: Any = None) -> None:
        self.get_calls.append((remote, local))
        if callback:
            callback(0, 100)
            callback(100, 100)

    def stat(self, path: str) -> Any:
        # By default all remote paths exist; override via _raise_stat for missing files.
        return MagicMock()

    def close(self) -> None:
        self.closed = True


class _FakeClient:
    def __init__(self, sftp: _FakeSFTP) -> None:
        self._sftp = sftp
        self.closed = False

    def open_sftp(self) -> _FakeSFTP:
        return self._sftp

    def close(self) -> None:
        self.closed = True


def _make_runner(sftp: _FakeSFTP) -> MagicMock:
    runner = MagicMock()
    runner.open_sftp.return_value = (_FakeClient(sftp), sftp)
    return runner


def _wait_for_thread(thread: FileTransferThread | FileDownloadThread, timeout_ms: int = 5000) -> None:
    loop = QEventLoop()
    thread.finished.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)
    thread.start()
    loop.exec_()


def test_upload_single_file(tmp_path: Path, qapp: QCoreApplication) -> None:
    source = tmp_path / "hello.txt"
    source.write_text("hello")

    sftp = _FakeSFTP()
    thread = FileTransferThread(_make_runner(sftp), [source], "/home/seeed")

    logs: list[str] = []
    progress: list[int] = []
    done_results: list[tuple[bool, str]] = []
    thread.log.connect(logs.append)
    thread.progress.connect(progress.append)
    thread.done.connect(lambda ok, msg: done_results.append((ok, msg)))

    _wait_for_thread(thread)

    assert len(sftp.put_calls) == 1
    assert sftp.put_calls[0] == (str(source), "/home/seeed/hello.txt")
    assert any("hello.txt" in log for log in logs)
    assert progress == [100, 100]
    assert done_results == [(True, "upload completed")]
    assert sftp.closed


def test_skip_directory(tmp_path: Path, qapp: QCoreApplication) -> None:
    source_dir = tmp_path / "folder"
    source_dir.mkdir()
    source_file = tmp_path / "file.txt"
    source_file.write_text("x")

    sftp = _FakeSFTP()
    thread = FileTransferThread(_make_runner(sftp), [source_dir, source_file], "/home/seeed")

    logs: list[str] = []
    file_done: list[tuple[str, bool]] = []
    done_results: list[tuple[bool, str]] = []
    thread.log.connect(logs.append)
    thread.file_done.connect(lambda path, ok: file_done.append((path, ok)))
    thread.done.connect(lambda ok, msg: done_results.append((ok, msg)))

    _wait_for_thread(thread)

    assert len(sftp.put_calls) == 1
    assert any("directory not supported" in log for log in logs)
    assert any(ok is False and "folder" in path for path, ok in file_done)
    assert done_results == [(True, "upload completed")]


def test_skip_missing_file(tmp_path: Path, qapp: QCoreApplication) -> None:
    missing = tmp_path / "missing.txt"

    sftp = _FakeSFTP()
    thread = FileTransferThread(_make_runner(sftp), [missing], "/home/seeed")

    logs: list[str] = []
    file_done: list[tuple[str, bool]] = []
    done_results: list[tuple[bool, str]] = []
    thread.log.connect(logs.append)
    thread.file_done.connect(lambda path, ok: file_done.append((path, ok)))
    thread.done.connect(lambda ok, msg: done_results.append((ok, msg)))

    _wait_for_thread(thread)

    assert not sftp.put_calls
    assert any("file not found" in log for log in logs)
    assert file_done == [(str(missing), False)]
    assert done_results == [(True, "upload completed")]


def test_remote_dir_created_recursively(tmp_path: Path, qapp: QCoreApplication) -> None:
    source = tmp_path / "data.bin"
    source.write_bytes(b"\x00" * 1024)

    sftp = _FakeSFTP(existing_dirs={"tmp"})
    thread = FileTransferThread(_make_runner(sftp), [source], "/tmp/uploads/jetson")

    done_results: list[tuple[bool, str]] = []
    thread.done.connect(lambda ok, msg: done_results.append((ok, msg)))

    _wait_for_thread(thread)

    assert sftp.mkdir_calls == ["tmp", "tmp/uploads", "tmp/uploads/jetson"]
    assert sftp.put_calls[0][1] == "/tmp/uploads/jetson/data.bin"
    assert done_results == [(True, "upload completed")]


def test_progress_callback_reported(tmp_path: Path, qapp: QCoreApplication) -> None:
    source = tmp_path / "chunked.bin"
    source.write_bytes(b"a" * 100)

    progress_log: list[str] = []

    class _LoggingSFTP(_FakeSFTP):
        def put(self, local: str, remote: str, callback: Any = None) -> None:
            self.put_calls.append((local, remote))
            if callback:
                callback(0, 100)
                callback(50, 100)
                callback(100, 100)

    sftp = _LoggingSFTP()
    thread = FileTransferThread(_make_runner(sftp), [source], "/home/seeed", on_log=progress_log.append)

    done_results: list[tuple[bool, str]] = []
    thread.done.connect(lambda ok, msg: done_results.append((ok, msg)))

    _wait_for_thread(thread)

    assert any("50%" in log for log in progress_log)
    assert done_results == [(True, "upload completed")]


def test_open_sftp_failure_emits_done(qapp: QCoreApplication) -> None:
    runner = MagicMock()
    runner.open_sftp.side_effect = RuntimeError("ssh unreachable")

    thread = FileTransferThread(runner, [Path("/tmp/x.txt")], "/home/seeed")

    done_results: list[tuple[bool, str]] = []
    logs: list[str] = []
    thread.log.connect(logs.append)
    thread.done.connect(lambda ok, msg: done_results.append((ok, msg)))

    _wait_for_thread(thread)

    assert done_results == [(False, "ssh unreachable")]
    assert any("ssh unreachable" in log for log in logs)


def test_download_single_file(tmp_path: Path, qapp: QCoreApplication) -> None:
    local_dir = tmp_path / "downloads"
    sftp = _FakeSFTP()
    thread = FileDownloadThread(_make_runner(sftp), ["/home/seeed/log.txt"], local_dir)

    done_results: list[tuple[bool, str]] = []
    logs: list[str] = []
    thread.log.connect(logs.append)
    thread.done.connect(lambda ok, msg: done_results.append((ok, msg)))

    _wait_for_thread(thread)

    assert sftp.get_calls == [("/home/seeed/log.txt", str(local_dir / "log.txt"))]
    assert local_dir.exists()
    assert done_results == [(True, "download completed")]
    assert sftp.closed


def test_download_skip_missing_remote_file(tmp_path: Path, qapp: QCoreApplication) -> None:
    local_dir = tmp_path / "downloads"

    class _MissingStatSFTP(_FakeSFTP):
        def stat(self, path: str) -> Any:
            if "missing" in path:
                raise FileNotFoundError(path)
            return MagicMock()

    sftp = _MissingStatSFTP()
    thread = FileDownloadThread(
        _make_runner(sftp),
        ["/home/seeed/missing.txt", "/home/seeed/exists.txt"],
        local_dir,
    )

    file_done: list[tuple[str, bool]] = []
    done_results: list[tuple[bool, str]] = []
    thread.file_done.connect(lambda path, ok: file_done.append((path, ok)))
    thread.done.connect(lambda ok, msg: done_results.append((ok, msg)))

    _wait_for_thread(thread)

    assert len(sftp.get_calls) == 1
    assert sftp.get_calls[0][0] == "/home/seeed/exists.txt"
    assert any("missing.txt" in path and ok is False for path, ok in file_done)
    assert done_results == [(True, "download completed")]


def test_download_local_dir_created(tmp_path: Path, qapp: QCoreApplication) -> None:
    local_dir = tmp_path / "nested" / "save" / "here"
    assert not local_dir.exists()

    sftp = _FakeSFTP()
    thread = FileDownloadThread(_make_runner(sftp), ["/tmp/data.bin"], local_dir)

    done_results: list[tuple[bool, str]] = []
    thread.done.connect(lambda ok, msg: done_results.append((ok, msg)))

    _wait_for_thread(thread)

    assert local_dir.exists()
    assert done_results == [(True, "download completed")]


def test_download_sftp_failure_emits_done(qapp: QCoreApplication) -> None:
    runner = MagicMock()
    runner.open_sftp.side_effect = RuntimeError("connection lost")

    thread = FileDownloadThread(runner, ["/home/seeed/a.txt"], Path("/tmp/out"))

    done_results: list[tuple[bool, str]] = []
    thread.done.connect(lambda ok, msg: done_results.append((ok, msg)))

    _wait_for_thread(thread)

    assert done_results == [(False, "connection lost")]
