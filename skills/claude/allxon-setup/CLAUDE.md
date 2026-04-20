---
name: allxon-setup
description: Install and configure Allxon DMS agent on NVIDIA Jetson devices for remote monitoring and management via the Allxon cloud portal. Supports JetPack 4.6+.
---

# Allxon DMS Setup on Jetson

Allxon is an edge device management solution for remote monitoring and management
of Jetson devices via a cloud portal. Installation is a single command.

Hardware: Any NVIDIA Jetson device, OOB Enabler (optional for out-of-band management)
Software: JetPack 4.6+, internet connection

---

## Execution model

Run one phase at a time. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed

---

## Phase 1 — prerequisites check (~30 s)

```bash
cat /etc/nv_tegra_release
```

Confirm JetPack 4.6 or later. Check internet:
```bash
ping -c 2 get.allxon.net
```

`[OK]` when JetPack version confirmed and internet works.
`[STOP]` if JetPack < 4.6 or no internet.

---

## Phase 2 — create Allxon account (human action)

Ask the user: "Do you already have an Allxon DMS account?"

If no:
1. Sign up at: https://dms.allxon.com/next/signup
2. Verify account via activation email
3. Create a password

`[OK]` when user confirms they have an account.

---

## Phase 3 — install Allxon DMS agent (~2 min)

```bash
sudo wget -qO - "https://get.allxon.net/linux/standard" | sudo bash -s
```

During installation, it will ask whether to install Trend Micro IoT Security
(3-month free trial). User can choose Y or N.

Verify agent is running:
```bash
systemctl status allxon-dms-agent
```

`[OK]` when agent is active/running.

---

## Phase 4 — get pairing code (~30 s)

CLI method:
```bash
dms-get-pairing-code
```

Or GUI method: press `Ctrl + Shift + B` on the Jetson desktop to open the agent window,
then click "Get device pairing code".

`[OK]` when pairing code is obtained.

---

## Phase 5 — pair device with portal (~1 min)

1. Login to https://dms.allxon.com/next/signin
2. Click Devices → + Add Device
3. Enter the pairing code from Phase 4
4. Click Next to complete pairing

`[OK]` when device appears in the Allxon DMS Portal.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `wget` install script fails | Check internet. Verify `get.allxon.net` is reachable. Try with `sudo`. |
| Agent not running after install | Run `sudo systemctl start allxon-dms-agent`. Check logs with `journalctl -u allxon-dms-agent`. |
| GUI agent doesn't appear | Press `Ctrl + Shift + B` to start it. Or use CLI `dms-get-pairing-code`. |
| Pairing code rejected | Ensure device has internet. Regenerate code and try again. |
| Device not showing in portal | Wait 1–2 minutes. Refresh the portal page. Check agent status. |

---

## Uninstall

```bash
sudo systemctl disable dms-install.service
sudo wget -qO - "https://get.allxon.net/linux/uninstall" | sudo bash -s
```

---

## Reference files

- `references/source.body.md` — Original Seeed wiki with screenshots and wiring diagrams
