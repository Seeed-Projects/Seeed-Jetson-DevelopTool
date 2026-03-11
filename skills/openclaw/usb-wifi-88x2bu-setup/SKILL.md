---
name: usb-wifi-88x2bu-setup
description: Install and enable Realtek RTL88x2bu USB Wi-Fi adapters (for example 0bda:b812) on Ubuntu/Jetson. Clones a maintained driver repo, builds against the running kernel, installs the module, loads it, and verifies the new Wi-Fi interface.
---

# USB Wi-Fi RTL88x2bu Setup

---

## Execution model

Run one phase at a time. After each phase:
- Relay `[install]` lines to the user.
- If output contains `[STOP]` -> stop and use the failure decision tree.
- If output ends with `[OK]` -> continue to the next phase.

The script is idempotent and safe to rerun.

---

## Phase commands

Default chipset ID is `0bda:b812` and default repo is `morrownr/88x2bu-20210702`.

### Phase 1 - Preflight (detect adapter + kernel info)
```bash
bash ~/.agents/skills/usb-wifi-88x2bu-setup/scripts/install_88x2bu.sh \
  --phase preflight --usb-id 0bda:b812 --sudo-mode noninteractive
```

### Phase 2 - Dependencies (build toolchain + headers)
```bash
bash ~/.agents/skills/usb-wifi-88x2bu-setup/scripts/install_88x2bu.sh \
  --phase deps --usb-id 0bda:b812 --sudo-mode noninteractive
```

### Phase 3 - Clone/update driver repo
```bash
bash ~/.agents/skills/usb-wifi-88x2bu-setup/scripts/install_88x2bu.sh \
  --phase repo --usb-id 0bda:b812
```

### Phase 4 - Build module (`88x2bu.ko`)
```bash
bash ~/.agents/skills/usb-wifi-88x2bu-setup/scripts/install_88x2bu.sh \
  --phase build --usb-id 0bda:b812
```

### Phase 5 - Install module into `/lib/modules/...`
```bash
bash ~/.agents/skills/usb-wifi-88x2bu-setup/scripts/install_88x2bu.sh \
  --phase install --usb-id 0bda:b812 --sudo-mode noninteractive
```

### Phase 6 - Load driver + bring interface up
```bash
bash ~/.agents/skills/usb-wifi-88x2bu-setup/scripts/install_88x2bu.sh \
  --phase enable --usb-id 0bda:b812 --sudo-mode noninteractive
```

### Phase 7 - Verify loaded module + interface state
```bash
bash ~/.agents/skills/usb-wifi-88x2bu-setup/scripts/install_88x2bu.sh \
  --phase verify --usb-id 0bda:b812
```

### Optional - Run all phases in one command
```bash
bash ~/.agents/skills/usb-wifi-88x2bu-setup/scripts/install_88x2bu.sh \
  --phase all --usb-id 0bda:b812 --sudo-mode noninteractive
```

### Optional - Connect via `nmcli` during enable phase
```bash
bash ~/.agents/skills/usb-wifi-88x2bu-setup/scripts/install_88x2bu.sh \
  --phase enable --usb-id 0bda:b812 --ifname wlx90de80cf79d2 \
  --ssid "<SSID>" --password "<PASSWORD>" --sudo-mode prompt
```

---

## Jetson required fix (before compile when `build` path is wrong)

On some Jetson setups, compile fails unless `/lib/modules/$(uname -r)/build`
points to the installed kernel source tree.

Run this exact sequence:

```bash
sudo rm -r /lib/modules/$(uname -r)/build
sudo ln -s /usr/src/linux-headers-$(uname -r)-ubuntu22.04_aarch64/3rdparty/canonical/linux-jammy/kernel-source \
  /lib/modules/$(uname -r)/build
```

Then run phase `build` again.

---

## Failure decision tree

| Output | Action |
|--------|--------|
| `[STOP] sudo is required...` | Ask user to rerun with `--sudo-mode prompt` in an interactive terminal, or grant passwordless sudo for this session. |
| `[STOP] usb device <ID> not detected` | Ask user to re-plug adapter, confirm with `lsusb`, then rerun phase `preflight`. |
| `[STOP] unable to locate a usable kernel source tree` | On Jetson, install `nvidia-l4t-kernel-headers`; on Ubuntu PC install `linux-headers-$(uname -r)`. Then rerun phase `deps`. |
| `[STOP] build failed` | Relay final compiler lines; check `references/88x2bu_troubleshooting.md`, then retry phase `build`. |
| `[STOP] modprobe 88x2bu failed` | Check `dmesg | tail -n 80`, verify module `vermagic` vs `uname -r`, then rebuild/reinstall. |
| `[FAIL] 88x2bu module loaded but no interface found` | Unplug/replug adapter, then rerun phases `enable` and `verify`; check for USB power issues. |

---

## Reference files

- `references/88x2bu_troubleshooting.md` - Known failures and exact recovery commands
- `scripts/install_88x2bu.sh` - Main phase-driven installer and verifier
