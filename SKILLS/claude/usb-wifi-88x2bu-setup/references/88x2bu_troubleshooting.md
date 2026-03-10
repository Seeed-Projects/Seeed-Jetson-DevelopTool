# RTL88x2bu Troubleshooting Playbook

This playbook supports the `usb-wifi-88x2bu-setup` OpenClaw skill.

## T1. `sudo` required but blocked

Symptom:
- `[STOP] sudo is required but passwordless sudo is not available`

Fix:
1. Run the same phase in an interactive shell with `--sudo-mode prompt`.
2. Enter password when prompted.

Example:
```bash
bash ~/.agents/skills/usb-wifi-88x2bu-setup/scripts/install_88x2bu.sh \
  --phase deps --sudo-mode prompt
```

## T2. USB ID not detected

Symptom:
- `[STOP] usb device 0bda:b812 not detected via lsusb`

Fix:
1. Replug adapter (prefer direct USB port; avoid weak hub).
2. Verify detection:
```bash
lsusb | grep -i 0bda:b812
```
3. Rerun `preflight`.

## T3. Kernel source tree not found

Symptom:
- `[STOP] unable to locate a usable kernel source tree`

Fix on Ubuntu PC:
```bash
sudo apt-get update
sudo apt-get install -y linux-headers-$(uname -r)
```

Fix on Jetson:
```bash
sudo apt-get update
sudo apt-get install -y nvidia-l4t-kernel-headers

# Remove existing redundant build directory if it exists
sudo rm -r /lib/modules/$(uname -r)/build

# Recreate build symlink to Jetson kernel source
sudo ln -s /usr/src/linux-headers-$(uname -r)-ubuntu22.04_aarch64/3rdparty/canonical/linux-jammy/kernel-source \
  /lib/modules/$(uname -r)/build
```

Then rerun `deps` and `build`.

## T4. Build fails

Symptom:
- `[STOP] build failed; see /tmp/88x2bu-build.log`

Fix:
1. Inspect compiler tail:
```bash
tail -n 120 /tmp/88x2bu-build.log
```
2. Clean and rebuild:
```bash
cd ~/drivers/88x2bu-20210702
make clean
make -j$(nproc) KVER="$(uname -r)" KSRC="/lib/modules/$(uname -r)/build"
```

## T5. `modprobe 88x2bu` fails

Symptom:
- `[STOP] modprobe 88x2bu failed`

Fix:
1. Check kernel log:
```bash
dmesg | tail -n 100
```
2. Verify module built for running kernel:
```bash
uname -r
modinfo ~/drivers/88x2bu-20210702/88x2bu.ko | grep vermagic
```
3. Rebuild using current kernel and reinstall (`build` + `install` phase).

## T6. Module loaded but no interface appears

Symptom:
- `[FAIL] 88x2bu module loaded but no interface found`

Fix:
1. Unplug/replug USB adapter.
2. Reload module:
```bash
sudo modprobe -r 88x2bu || true
sudo modprobe 88x2bu
```
3. Check interface list:
```bash
ip -br link
nmcli device status
```

## T7. Interface exists but does not connect

Fix:
1. Scan APs:
```bash
nmcli dev wifi list ifname <IFACE>
```
2. Connect:
```bash
sudo nmcli dev wifi connect "<SSID>" password "<PASSWORD>" ifname <IFACE>
```
3. If internal Wi-Fi takes priority, disconnect it:
```bash
sudo nmcli dev disconnect <INTERNAL_WIFI_IFACE>
```
