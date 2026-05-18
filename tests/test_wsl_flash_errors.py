from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seeed_jetson_develop.wsl_flash import _looks_like_nfs_mount_failure


def test_detects_nfs_mount_failure_message():
    text = """
Flash failure
Either the device cannot mount the NFS server on the host or a flash command has failed.
Check your network setting (VPN, firewall,...) to make sure the device can mount NFS server.
Debug log saved to /tmp/tmp.VkmeOeTpMp.
Cleaning up...
"""
    assert _looks_like_nfs_mount_failure(text)


def test_does_not_confuse_boot_timeout_with_nfs_failure():
    text = """
Waiting for target to boot-up...
Waiting for target to boot-up...
"""
    assert not _looks_like_nfs_mount_failure(text)
