# Browser Snap Troubleshooting on Jetson

## T1 — snap download failed

Possible causes and fixes:

1. No internet access on the Jetson:
   - Verify connectivity: `ping -c 3 snapcraft.io`
   - If behind a proxy, set: `export https_proxy=http://<host>:<port>`

2. Revision no longer available in the store:
   - Try the next closest revision. Check available revisions with:
     `snap info snapd | grep -A 20 channels`
   - Update `--snapd-revision` to a valid revision number.

3. Disk space too low:
   - Check: `df -h ~`
   - Free space or change `--work-dir` to a larger partition.

---

## T2 — snap install failed

Common errors:

- `error: cannot perform the following tasks: ... (snap "snapd" has "install-snap" change in progress)`
  - Another snap operation is running. Wait and retry, or: `sudo snap abort <change-id>`

- `error: cannot install snap file: unsupported snap type`
  - The downloaded file is corrupt. Delete `~/snapd-fix` and rerun phase download.

- `error: system does not support re-exec`
  - The Jetson kernel is too old for this snapd revision. Try a lower revision (e.g. `--snapd-revision 21759`).

---

## T3 — snap refresh --hold failed

Older snapd versions (pre-2.58) do not support `snap refresh --hold`.

Workaround — prevent snapd auto-refresh via config:
```bash
sudo snap set system refresh.hold="$(date --date='2 years' +%Y-%m-%dT%H:%M:%S%:z)"
```

Or disable the refresh timer entirely (not recommended for production):
```bash
sudo systemctl disable --now snapd.refresh.timer
```

---

## T4 — Browser still not launching after snapd fix

1. Check for confinement errors:
   ```bash
   journalctl -xe | grep -E "snap|apparmor|seccomp" | tail -30
   ```

2. Try running the browser with `--no-sandbox` (Chromium):
   ```bash
   snap run chromium --no-sandbox
   ```

3. Reinstall the browser snap:
   ```bash
   sudo snap remove chromium
   sudo snap install chromium
   ```

4. Check AppArmor status — some Jetson BSPs ship with AppArmor disabled:
   ```bash
   sudo aa-status
   ```
   If AppArmor is not loaded, the snap confinement may fail silently.
   Enable it by adding `apparmor=1 security=apparmor` to kernel cmdline in `/boot/extlinux/extlinux.conf`.

5. If using a display over VNC or headless, ensure `DISPLAY` is set:
   ```bash
   export DISPLAY=:0
   snap run chromium
   ```
