---
name: neqto-engine-setup
description: Install and configure NEQTO Engine for Linux on reComputer J30 series. Covers account creation, API key setup, daemon installation, device registration, and Hello World script deployment via NEQTO Console. Requires any Linux-based Jetson with ≥32MB disk and network adapter.
---

# Getting Started with NEQTO Engine for Linux on reComputer J30

---

## Execution model

Run one phase at a time. After each phase:
- Relay all command output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree below.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Minimum |
|-------------|---------|
| Hardware | reComputer J3011 / J4011 or any Linux machine (armv6l/armv7l/aarch64/x86_64) |
| Disk | ≥ 32 MB free |
| RAM | ≥ 4 MB |
| Network | Physical network adapter required, internet access |
| NEQTO account | Free account at https://console.neqto.com/register |

---

## Phase 1 — Preflight

Verify architecture, disk space, and network connectivity.

```bash
uname -m
df -h /
ping -c 3 console.neqto.com
```

Expected: supported architecture shown, ≥32 MB free, ping succeeds. `[OK]` when all pass. `[STOP]` if no network.

---

## Phase 2 — Create NEQTO account and API key (manual)

1. Visit https://console.neqto.com/register — sign up and verify via activation email.
2. In NEQTO Console, select "Manage API Keys for Linux-based Device" from the menu.
3. Click "CREATE API KEY" and copy the generated API key.

`[OK]` when you have the API key copied.

---

## Phase 3 — Install NEQTO Engine

Download the installer from the NEQTO Console (copy the download link for "Installer of NEQTO Engine for Linux"):

```bash
wget <PASTE_DOWNLOAD_LINK_HERE> -O neqto-daemon-install.latest.sh
chmod +x neqto-daemon-install.latest.sh
sudo ./neqto-daemon-install.latest.sh -k <YOUR_API_KEY>
```

When prompted, enter your password and type `agree` to accept the terms. Wait for "Installation completed successfully!" message.

Verify the device appears in NEQTO Console under registered devices.

`[OK]` when installation completes and device is visible in NEQTO Console. `[STOP]` if installer fails.

---

## Phase 4 — Deploy Hello World script

All steps below are performed in the NEQTO Console web UI:

1. Click "ADD GROUP" → name it `reComputer J30` → click "SAVE".
2. Select the group → click "SCRIPTS" → "ADD SCRIPT" → name it `Hello World` → "SAVE".
3. Paste the [sample code](https://docs.neqto.com/docs/en/getting-started/tutorial-step1#sample-code) into the script editor → click "Save".
4. Click "TEMPLATES" → "ADD TEMPLATE":
   - Name: `reComputer J30 Template`
   - Firmware Type: `Linux-based device`
   - Firmware Version: latest
   - Script: `Hello World`
   - Click "SAVE"
5. Click "NODES" → "ADD NODE":
   - Name: `reComputer J30`
   - Template: `reComputer J30 Template`
   - Select your registered device → click "SAVE"

Verify on the Jetson terminal:

```bash
tail -F /tmp/neqto/log/neqto.log
```

Click "Reload Script" in NEQTO Console. You should see `Hello World!!!` in the terminal output.

`[OK]` when "Hello World!!!" appears in the log. `[STOP]` if no output after reload.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Installer download fails | Verify the download link from NEQTO Console is correct. Check internet with `ping console.neqto.com`. |
| `chmod` or `sudo` permission denied | Ensure you have root/sudo access on the device. |
| Installation fails with API key error | Re-copy the API key from NEQTO Console. Ensure no extra spaces. |
| Device not appearing in console | Check network connectivity. Restart the NEQTO daemon: `sudo systemctl restart neqto`. |
| No log output from `tail -F` | Verify NEQTO service is running: `sudo systemctl status neqto`. Check `/tmp/neqto/log/` exists. |
| "Hello World" not appearing after reload | Ensure the node is correctly linked to the template and script. Try "Reload Script" again. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with NEQTO Console screenshots, step-by-step UI walkthrough, and troubleshooting links (reference only)
