"""Tests for PC->Jetson network sharing (net_share module).

Covers the NetworkManager `ipv4.method shared` path (preferred), the
iptables fallback, state persistence, and the Jetson-side staged
verify/restore command builders.
"""
import unittest
from unittest.mock import patch

from seeed_jetson_develop.modules.remote import net_share


class TestJetsonVerifyCmd(unittest.TestCase):
    def test_verify_cmd_contains_steps_and_gateway(self):
        cmd = net_share.build_jetson_verify_cmd("192.168.88.24")
        self.assertIn("192.168.88.24", cmd)
        for marker in ("verify_ping_gw", "verify_ping_public",
                       "verify_dns", "verify_https"):
            self.assertIn(marker, cmd)

    def test_verify_cmd_quotes_gateway(self):
        cmd = net_share.build_jetson_verify_cmd("10.0.0.1'; rm -rf /; '")
        self.assertNotIn("rm -rf / ", cmd.replace("\\'", ""))

    def test_parse_verify_output(self):
        out = "verify_ping_gw=ok\nverify_ping_public=fail\nverify_dns=ok\nverify_https=ok\n"
        steps = net_share.parse_jetson_verify_output(out)
        self.assertEqual(steps, {"ping_gw": True, "ping_public": False,
                                 "dns": True, "https": True})

    def test_parse_verify_output_ignores_noise(self):
        out = "$ some command\nverify_ping_gw=ok\r\nrandom text\nverify_dns=fail\n"
        steps = net_share.parse_jetson_verify_output(out)
        self.assertEqual(steps, {"ping_gw": True, "dns": False})


class TestJetsonRestoreCmd(unittest.TestCase):
    def test_restore_cmd(self):
        cmd = net_share.build_jetson_restore_cmd("192.168.88.24")
        self.assertIn("ip route del default via", cmd)
        self.assertIn("192.168.88.24", cmd)
        self.assertIn("resolvectl revert", cmd)
        self.assertIn("restore_done", cmd)


class TestNmHelpers(unittest.TestCase):
    def test_nm_device_managed(self):
        out = "enp8s0:connected\nveth34faad8:unmanaged\n"
        with patch.object(net_share, "_run_argv", return_value=(0, out)):
            self.assertTrue(net_share._nm_device_managed("enp8s0"))
            self.assertFalse(net_share._nm_device_managed("veth34faad8"))
            self.assertFalse(net_share._nm_device_managed("missing0"))

    def test_nm_active_connection(self):
        out = "jetson-wired-share:enp8s0\nSEEED-MKT:wlp9s0\n"
        with patch.object(net_share, "_run_argv", return_value=(0, out)):
            self.assertEqual(net_share._nm_active_connection("enp8s0"),
                             "jetson-wired-share")
            self.assertEqual(net_share._nm_active_connection("wlp9s0"),
                             "SEEED-MKT")
            self.assertIsNone(net_share._nm_active_connection("eth9"))

    def test_nm_active_connection_with_escaped_colon_in_name(self):
        out = "my\\:conn:enp8s0\n"
        with patch.object(net_share, "_run_argv", return_value=(0, out)):
            self.assertEqual(net_share._nm_active_connection("enp8s0"), "my:conn")

    def test_state_roundtrip(self, ):
        with patch.object(net_share, "_NET_SHARE_STATE_PATH") as p:
            import tempfile, pathlib
            with tempfile.TemporaryDirectory() as td:
                real = pathlib.Path(td) / "state.json"
                p.read_text = real.read_text
                p.parent = real.parent
                p.write_text = real.write_text
                p.unlink = real.unlink
                net_share._save_share_state({"lan": "enp8s0", "backend": "networkmanager"})
                self.assertEqual(net_share._load_share_state()["lan"], "enp8s0")
                net_share._clear_share_state()
                self.assertEqual(net_share._load_share_state(), {})


class TestSmartEnableSelection(unittest.TestCase):
    def test_nm_path_preferred_when_managed(self):
        with patch.object(net_share, "_nmcli_available", return_value=True), \
             patch.object(net_share, "_nm_device_managed", return_value=True), \
             patch.object(net_share, "_enable_nat_linux_nm",
                          return_value=(True, "nm-ok")) as m_nm, \
             patch.object(net_share, "_enable_nat_linux_safe",
                          return_value=(True, "iptables-ok")) as m_ipt:
            ok, log = net_share._enable_nat_linux_smart("wlp9s0", "enp8s0", "")
            self.assertTrue(ok)
            self.assertEqual(log, "nm-ok")
            m_nm.assert_called_once()
            m_ipt.assert_not_called()

    def test_fallback_to_iptables_when_nm_fails(self):
        with patch.object(net_share, "_nmcli_available", return_value=True), \
             patch.object(net_share, "_nm_device_managed", return_value=True), \
             patch.object(net_share, "_enable_nat_linux_nm",
                          return_value=(False, "nm-fail")), \
             patch.object(net_share, "_enable_nat_linux_safe",
                          return_value=(True, "iptables-ok")) as m_ipt:
            ok, log = net_share._enable_nat_linux_smart("wlp9s0", "enp8s0", "")
            self.assertTrue(ok)
            self.assertIn("nm-fail", log)
            self.assertIn("iptables-ok", log)
            m_ipt.assert_called_once()

    def test_iptables_when_nm_missing(self):
        with patch.object(net_share, "_nmcli_available", return_value=False), \
             patch.object(net_share, "_enable_nat_linux_safe",
                          return_value=(True, "iptables-ok")) as m_ipt:
            ok, log = net_share._enable_nat_linux_smart("wlp9s0", "enp8s0", "")
            self.assertTrue(ok)
            m_ipt.assert_called_once()

    def test_disable_runs_nm_teardown_and_iptables_cleanup(self):
        with patch.object(net_share, "_nmcli_available", return_value=True), \
             patch.object(net_share, "_disable_nat_linux_nm",
                          return_value=(True, "nm-down")) as m_nm, \
             patch.object(net_share, "_disable_nat_linux_safe",
                          return_value=(True, "iptables-clean")) as m_ipt:
            ok, log = net_share._disable_nat_linux_smart("wlp9s0", "enp8s0", "")
            self.assertTrue(ok)
            self.assertIn("nm-down", log)
            self.assertIn("iptables-clean", log)
            m_nm.assert_called_once()
            m_ipt.assert_called_once()

    def test_invalid_iface_name_rejected(self):
        ok, log = net_share._enable_nat_linux_smart("wlan0; rm -rf /", "eth0", "")
        self.assertFalse(ok)
        self.assertIn("invalid interface name", log)


class TestNmEnableCommands(unittest.TestCase):
    """Verify nmcli command shapes in the NM enable path."""

    def test_modify_existing_profile_preserves_addr(self):
        calls = []

        def fake_run_argv(args, pwd="", timeout=30):
            calls.append(args)
            if args[:2] == ["sysctl", "-w"]:
                return 0, ""
            if args[:3] == ["nmcli", "connection", "show"]:
                return 0, "x"  # profile exists
            return 0, ""

        with patch.object(net_share, "_run_argv", side_effect=fake_run_argv), \
             patch.object(net_share, "_nm_active_connection",
                          return_value="wired-original"), \
             patch.object(net_share, "_iface_cidr",
                          side_effect=["192.168.88.24/24", "192.168.88.24/24"]), \
             patch.object(net_share, "_save_share_state"), \
             patch.object(net_share.shutil, "which", return_value="/usr/sbin/dnsmasq"):
            ok, log = net_share._enable_nat_linux_nm("wlp9s0", "enp8s0", "")

        self.assertTrue(ok, log)
        modify = next(c for c in calls if c[:3] == ["nmcli", "connection", "modify"])
        self.assertIn("shared", modify)
        self.assertIn("192.168.88.24/24", modify)
        self.assertIn("no", modify)  # autoconnect no
        up = next(c for c in calls if c[:3] == ["nmcli", "connection", "up"])
        self.assertIn(net_share.NM_SHARE_PROFILE, up)

    def test_create_profile_when_absent(self):
        calls = []

        def fake_run_argv(args, pwd="", timeout=30):
            calls.append(args)
            if args[:3] == ["nmcli", "connection", "show"]:
                return 1, ""  # profile does not exist
            return 0, ""

        with patch.object(net_share, "_run_argv", side_effect=fake_run_argv), \
             patch.object(net_share, "_nm_active_connection", return_value=None), \
             patch.object(net_share, "_iface_cidr",
                          side_effect=["192.168.88.24/24", "192.168.88.24/24"]), \
             patch.object(net_share, "_save_share_state"), \
             patch.object(net_share.shutil, "which", return_value="/usr/sbin/dnsmasq"):
            ok, log = net_share._enable_nat_linux_nm("wlp9s0", "enp8s0", "")

        self.assertTrue(ok, log)
        add = next(c for c in calls if c[:3] == ["nmcli", "connection", "add"])
        self.assertIn("shared", add)
        self.assertIn("ipv4.never-default", add)

    def test_fails_when_addr_lost_after_up(self):
        def fake_run_argv(args, pwd="", timeout=30):
            return 0, ""

        with patch.object(net_share, "_run_argv", side_effect=fake_run_argv), \
             patch.object(net_share, "_nm_active_connection", return_value=None), \
             patch.object(net_share, "_iface_cidr",
                          side_effect=["192.168.88.24/24", None]), \
             patch.object(net_share.shutil, "which", return_value="/usr/sbin/dnsmasq"):
            ok, log = net_share._enable_nat_linux_nm("wlp9s0", "enp8s0", "")
        self.assertFalse(ok)
        self.assertIn("lost its IPv4 address", log)


class TestNmDisable(unittest.TestCase):
    def test_down_share_and_restore_original(self):
        calls = []

        def fake_run_argv(args, pwd="", timeout=30):
            calls.append(args)
            if args[:3] == ["nmcli", "connection", "show"]:
                return 0, "x"  # profiles exist
            return 0, ""

        with patch.object(net_share, "_run_argv", side_effect=fake_run_argv), \
             patch.object(net_share, "_load_share_state",
                          return_value={"original_connection": "wired-original"}), \
             patch.object(net_share, "_clear_share_state") as m_clear:
            handled, log = net_share._disable_nat_linux_nm("")

        self.assertTrue(handled)
        down = next(c for c in calls if c[:3] == ["nmcli", "connection", "down"])
        self.assertIn(net_share.NM_SHARE_PROFILE, down)
        up = next(c for c in calls if c[:3] == ["nmcli", "connection", "up"])
        self.assertIn("wired-original", up)
        m_clear.assert_called_once()

    def test_noop_when_profile_absent(self):
        with patch.object(net_share, "_nm_profile_exists", return_value=False):
            handled, log = net_share._disable_nat_linux_nm("")
        self.assertFalse(handled)
        self.assertEqual(log, "")


if __name__ == "__main__":
    unittest.main()
