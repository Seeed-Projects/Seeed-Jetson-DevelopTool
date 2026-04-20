---
name: allxon-ota-update
description: Perform over-the-air JetPack/L4T updates on Jetson devices using Allxon DMS Portal. Covers OTA payload generation, upload, and fleet distribution. Requires Ubuntu host PC and Allxon DMS agent.
---

# OTA Update Jetson via Allxon DMS

Uses Allxon DMS Portal to generate, upload, and distribute OTA Payload Packages
for updating Jetson devices from one JetPack version to another. The OTA payload
is delta-based (Base BSP → Target BSP).

Hardware: Jetson Xavier NX / AGX Xavier / TX2 (NOT Nano), USB-C cable, HDMI display (optional)
Software: Ubuntu 20.04 host PC (native), Allxon DMS agent installed on Jetson

---

## Execution model

Run one phase at a time. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed

**Warning:** The OTA update erases the file system. Only `/ota` survives. Ensure the user
has backed up important data before proceeding.

---

## Phase 1 — prerequisites check (~1 min)

On the Jetson device:
```bash
cat /etc/nv_tegra_release
```

Confirm Allxon DMS agent is installed:
```bash
dpkg -l | grep allxon-dms-agent
```

Confirm Ethernet is connected (required throughout the entire OTA process).

On the Ubuntu host PC, confirm native Ubuntu 20.04 or 22.04.

`[OK]` when all prerequisites confirmed.
`[STOP]` if using Jetson Nano (not supported) or no Allxon agent.

---

## Phase 2 — prepare Base BSP on host PC (~10 min)

Download the L4T Driver Package (BSP) and Sample Root Filesystem matching the
CURRENT version on the Jetson device from:
https://developer.nvidia.com/embedded/linux-tegra-archive

```bash
sudo tar -vxjf <Base_BSP>.tbz2
cd <Base_BSP>/Linux_for_Tegra/rootfs
sudo tar -jxpf ../../<rootfs>.tbz2
cd ..
sudo ./apply_binaries.sh
```

`[OK]` when `apply_binaries.sh` completes without errors.

---

## Phase 3 — prepare Target BSP on host PC (~15 min)

Repeat Phase 2 steps for the TARGET JetPack version.

Then add the auto-install Allxon agent mechanism to the Target BSP:

1. Create `/etc/init.d/install_allxon_dms.sh` in Target BSP rootfs
   (script content in `references/source.body.md`)
2. Create `/etc/systemd/system/dms-install.service` in Target BSP rootfs
   (service content in `references/source.body.md`)
3. Set permissions and create symlink:
```bash
sudo chmod 644 ./etc/systemd/system/dms-install.service
sudo chmod 777 ./etc/init.d/install_allxon_dms.sh
sudo ln -s /etc/systemd/system/dms-install.service \
  ./etc/systemd/system/multi-user.target.wants/dms-install.service
```

`[OK]` when Target BSP is prepared with auto-install scripts.

---

## Phase 4 — generate OTA payload package (~20 min)

Download "Jetson Platform Over-The-Air Update Tools" from the Target BSP L4T release page.

Create and run `generate_ota_payload.sh` (template in `references/source.body.md`):
- Set `BASE_BSP_PATH`, `TOT_BSP_PATH`, `OTA_TOOL`, `JETSON_MODEL`, `BSP_VERSION`, `TARGET_FOLDER`

```bash
chmod 777 generate_ota_payload.sh
sudo ./generate_ota_payload.sh
```

Output: `ota_payload_package.tar.gz` in TARGET_FOLDER.

`[OK]` when payload package is generated.

---

## Phase 5 — package & upload to Allxon (~5 min)

Create supporting files in TARGET_FOLDER:
- `run_ota_payload.sh` (template in `references/source.body.md`)
- `dms-backup.service`
- `backup_agent_cache.sh`

Package everything:
```bash
cd <TARGET_FOLDER>
zip ota_payload.zip *
```

Upload to Allxon DMS Portal:
1. Login → Applications → Register → fill in name/GUID/platform
2. Add version → set installation command → upload `ota_payload.zip`
3. Release the version

`[OK]` when application is released on Allxon DMS Portal.

---

## Phase 6 — distribute OTA update (~5 min + reboot time)

1. In Allxon DMS Portal: Applications → select the OTA package → Distribute
2. Select target device groups → Schedule distribution time

The Jetson device will:
1. Download and apply the OTA payload
2. Display "Restart in 5 mins" message
3. Reboot twice (OTA apply + initial OS setup)

After reboot, verify:
```bash
cat /etc/nv_tegra_release
```

`[OK]` when new L4T version is confirmed.

---

## Uninstall Allxon DMS

```bash
sudo systemctl disable dms-install.service
sudo wget -qO - "https://get.allxon.net/linux/uninstall" | sudo bash -s
```

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `apply_binaries.sh` fails | Verify BSP and rootfs versions match. Re-extract and retry. |
| OTA payload generation fails | Check JETSON_MODEL matches device. Verify both BSPs are correctly prepared. |
| Upload to Allxon fails | Check file size. Contact Allxon for verification if needed. |
| OTA update fails on device | Check `/ota_log` on device. Ensure Ethernet was connected throughout. |
| Device stuck after reboot | Connect HDMI display. Complete initial OS configuration manually. |
| Allxon agent missing after OTA | Verify `install_allxon_dms.sh` was correctly placed in Target BSP. |
| Insufficient disk space | eMMC needs free space ≥ OTA Payload Package × 2.5. |

---

## Reference files

- `references/source.body.md` — Full Seeed wiki with script templates, screenshots, and detailed workflow
