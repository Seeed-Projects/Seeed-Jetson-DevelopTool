---
name: ota-deploy
description: Perform NVIDIA Jetson Over-the-Air (OTA) updates on reComputer devices to upgrade from JetPack 5.1.3 to JetPack 6.2 without USB re-flashing. Covers pre-built OTA payloads and custom OTA package generation. Requires Ubuntu x86_64 host PC and Orin-based reComputer.
---

# Deploy OTA on reComputer

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
| Jetson device | Orin-based reComputer (mini, J30/40, Industrial, reServer Industrial, J501) |
| Current JetPack | 5.1.3 (for pre-built OTA payloads) |
| Host PC | Ubuntu x86_64 (for transferring OTA payload) |
| Network | SSH access between host PC and Jetson |
| Storage | Sufficient space for OTA payload (~several GB) |

> Pre-built OTA payloads are available for: reComputer mini, J30/40/401B, Industrial, reServer Industrial, and J501 AGX-Orin (with/without GMSL). See `references/source.body.md` for download links and SHA256 checksums.

---

## Phase 1 — Preflight (on Jetson)

```bash
cat /etc/nv_tegra_release
df -h /
```

Expected: R35.5.0 (JP5.1.3), sufficient disk space for OTA tools and payload. `[OK]` when confirmed. `[STOP]` if not JP5.1.3 (for pre-built payloads).

---

## Phase 2 — Install dependencies and OTA tools (on Jetson)

```bash
sudo apt-get update
sudo apt-get install efibootmgr nvme-cli -y

mkdir ~/ota_ws
cd ~/ota_ws
wget https://developer.nvidia.com/downloads/embedded/l4t/r36_release_v4.3/release/ota_tools_r36.4.3_aarch64.tbz2
tar xvf ota_tools_r36.4.3_aarch64.tbz2
```

Expected: `Linux_for_Tegra` folder extracted in `~/ota_ws`. `[OK]` when extraction completes.

---

## Phase 3 — Transfer OTA payload (on host PC)

Download the appropriate `ota_payload_package.tar.gz` for your device from the links in `references/source.body.md`, then transfer to Jetson:

```bash
# Run on host PC — replace <Jetson_IP> with actual IP
scp /path/to/ota_payload_package.tar.gz seeed@<Jetson_IP>:/home/seeed/ota_ws/
```

Verify the SHA256 checksum on the Jetson:

```bash
sha256sum ~/ota_ws/ota_payload_package.tar.gz
```

`[OK]` when checksum matches. `[STOP]` if mismatch — re-download the payload.

---

## Phase 4 — Back up files and start OTA (on Jetson)

Edit the backup file list to preserve important files/folders:

```bash
cd ~/ota_ws/Linux_for_Tegra/tools/ota_tools/version_upgrade/
vim ota_backup_files_list.txt
# Add absolute paths of files/folders to preserve, one per line
```

Run the backup preservation script:

```bash
./nv_ota_preserve_data.sh
```

Start the OTA process:

```bash
cd ~/ota_ws/Linux_for_Tegra/tools/ota_tools/version_upgrade
sudo ./nv_ota_start.sh ~/ota_ws/ota_payload_package.tar.gz
```

After the script completes, reboot to initiate the OTA:

```bash
sudo reboot
```

The device will show the NVIDIA logo, enter kernel overlay, go black briefly (normal), then proceed with OTA. After completion, configure username and password for the new system.

`[OK]` when OTA script completes without errors and reboot is initiated.

---

## Phase 5 — Post-upgrade validation (on Jetson)

```bash
cat /etc/nv_tegra_release
nvbootctrl -t
sudo nvme list
```

Expected: `R36 (release), REVISION: 4.3` (JetPack 6.2). `[OK]` when release matches and applications start normally.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| OTA tools download fails | Check internet. Verify NVIDIA download URL is accessible. |
| `scp` transfer fails | Verify SSH access: `ssh seeed@<Jetson_IP>`. Check firewall and network. |
| SHA256 checksum mismatch | Re-download the OTA payload. File may be corrupted during transfer. |
| `nv_ota_start.sh` fails | Verify payload path is correct. Check disk space: `df -h`. Ensure dependencies are installed. |
| Device stuck on black screen after reboot | Wait — black screen during OTA is normal. Process can take 10–30 minutes. Do not power off. |
| Post-reboot shows old JetPack version | OTA may have failed silently. Check `/var/log/` for OTA logs. Re-run the OTA process. |
| Need custom OTA (different version pair) | See `references/source.body.md` for full BSP preparation and `start_generate_ota_pkg.sh` workflow. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with pre-built OTA payload download links per device, SHA256 checksums, custom OTA package generation from BSP sources, and kernel build instructions (reference only)
