"""Regression tests for the backup page one-click environment prepare.

Covers the L4T version extraction (>= 36.0.0, dedup, descending) and the
command/environment construction of both background-script threads. Pure
logic only — no QApplication / widget instantiation.
"""
from __future__ import annotations

import pytest

from seeed_jetson_develop.modules.backup_restore import page as page_mod
from seeed_jetson_develop.modules.backup_restore.thread import (
    BackupRestoreThread,
    PrepareThread,
)


def test_load_versions_filters_below_35_dedupes_sorts_desc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """l4t 字段提取纯版本号: <35 剔除(GMSL 注记不影响)、去重、降序。"""
    monkeypatch.setattr(
        page_mod,
        "load_json_data",
        lambda name, default=None: [
            {"l4t": "36.4.3 (GMSL✅)"},
            {"l4t": "39.2.0"},
            {"l4t": "36.4.3"},          # 重复 → 合并
            {"l4t": "35.5.0"},
            {"l4t": "36.4.0"},
            {"l4t": "38.4.0"},
            "not-a-dict",               # 脏数据 → 忽略
        ],
    )
    assert page_mod.BackupRestorePage._load_versions() == [
        "39.2.0",
        "38.4.0",
        "36.4.3",
        "36.4.0",
        "35.5.0",
    ]


def test_load_versions_handles_empty_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """数据缺失/为空时返回空列表, 页面落入「无可用版本」守卫。"""
    monkeypatch.setattr(page_mod, "load_json_data", lambda name, default=None: None)
    assert page_mod.BackupRestorePage._load_versions() == []

    monkeypatch.setattr(page_mod, "load_json_data", lambda name, default=None: [])
    assert page_mod.BackupRestorePage._load_versions() == []


def test_prepare_thread_cmd_minimal_with_sudo() -> None:
    """准备线程: bash <script> R<ver> --root <root> --minimal + SUDO_PASS 透传。"""
    th = PrepareThread("setup.sh", "36.4.3", "/tmp/root", sudo_pass="pw")
    assert th._build_cmd() == [
        "bash", "setup.sh", "R36.4.3", "--root", "/tmp/root", "--minimal",
    ]
    env = th._build_env()
    assert env["SUDO_PASS"] == "pw"


def test_prepare_thread_no_sudo_and_non_minimal() -> None:
    """无密码时不注入 SUDO_PASS; minimal=False 时不加 --minimal。"""
    th = PrepareThread("setup.sh", "36.4.3", "/tmp/root")
    assert "SUDO_PASS" not in th._build_env()

    th2 = PrepareThread("setup.sh", "36.4.3", "/tmp/root", minimal=False)
    assert th2._build_cmd() == ["bash", "setup.sh", "R36.4.3", "--root", "/tmp/root"]


def test_backup_thread_cmd_and_env_regression() -> None:
    """备份线程: 模式旗标/-b|-r/--wait-apx 与 L4T_DIR/EXTERNAL_DEVICE/SUDO_PASS。"""
    th = BackupRestoreThread(
        "br.sh", "backup", "recomputer-orin-j401", "/tmp/l4t",
        device="nvme0n1", wait_apx=True, sudo_pass="pw",
    )
    assert th._build_cmd() == [
        "bash", "br.sh", "-b", "recomputer-orin-j401", "--wait-apx",
    ]
    env = th._build_env()
    assert env["L4T_DIR"] == "/tmp/l4t"
    assert env["EXTERNAL_DEVICE"] == "nvme0n1"
    assert env["SUDO_PASS"] == "pw"

    th2 = BackupRestoreThread("br.sh", "restore", "seeed-test", "/tmp/l4t")
    assert th2._build_cmd() == ["bash", "br.sh", "-r", "seeed-test"]
    assert "SUDO_PASS" not in th2._build_env()