---
name: fix-browser-snap-jetson
description: Fix browsers (Chromium, Firefox, etc.) that fail to launch on Jetson devices due to an outdated or broken snapd. Downloads a pinned snapd revision offline, installs it, and holds automatic updates to prevent regression. Use when the user reports that a browser installed via snap cannot open, crashes silently, or shows snap-related errors on Jetson (Ubuntu/L4T).
---

# Fix Browser Not Opening on Jetson (snapd Repair)

Browsers distributed as snap packages (Chromium, Firefox) fail to launch on Jetson
when the installed snapd is too old or incompatible with the snap's confinement requirements.
The fix is to install a known-good snapd revision offline and hold it from auto-updating.

Root cause: Jetson ships with an older snapd that lacks support for newer snap security profiles.
The browser snap starts, hits a permission or mount-namespace error, and exits silently.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all `[install]` lines to the user.
- If output contains `[STOP]` → stop immediately and consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and run the next phase.

The script is idempotent and safe to rerun.

---

## Parameters

| Flag | Default | Notes |
|------|---------|-------|
| `--snapd-revision` | `24724` | snapd snap revision to install (change only if advised) |
| `--phase` | `all` | `preflight` / `download` / `install` / `hold` / `verify` / `all` |
| `--work-dir` | `$HOME/snapd-fix` | directory for downloaded snap and assert files |

---

## Phase commands

### Phase 1 — preflight (fast, ~5 s)
Checks snapd status, current version, and whether a browser snap is present.
```bash
bash ~/.agents/skills/fix-browser-snap-jetson/scripts/fix_browser_snap.sh \
  --phase preflight
```

### Phase 2 — download (medium, ~1–3 min depending on network)
Downloads the pinned snapd snap and its assertion file from the Snap Store.
```bash
bash ~/.agents/skills/fix-browser-snap-jetson/scripts/fix_browser_snap.sh \
  --phase download --snapd-revision 24724
```

### Phase 3 — install (fast, ~30 s)
Acknowledges the assertion and installs the downloaded snapd snap.
```bash
bash ~/.agents/skills/fix-browser-snap-jetson/scripts/fix_browser_snap.sh \
  --phase install --snapd-revision 24724
```

### Phase 4 — hold (fast, ~5 s)
Holds snapd at the installed revision so automatic refreshes cannot break it again.
```bash
bash ~/.agents/skills/fix-browser-snap-jetson/scripts/fix_browser_snap.sh \
  --phase hold
```

### Phase 5 — verify (fast, ~10 s)
Confirms snapd version, hold status, and attempts to launch the browser snap in dry-run mode.
```bash
bash ~/.agents/skills/fix-browser-snap-jetson/scripts/fix_browser_snap.sh \
  --phase verify
```

### Run all phases in one command
```bash
bash ~/.agents/skills/fix-browser-snap-jetson/scripts/fix_browser_snap.sh \
  --phase all --snapd-revision 24724
```

---

## Failure decision tree

| Output | Action |
|--------|--------|
| `[STOP] snap command not found` | snapd is not installed at all. Run: `sudo apt install snapd` then rerun phase preflight. |
| `[STOP] snapd service not running` | Run: `sudo systemctl enable --now snapd` then rerun phase preflight. |
| `[STOP] snap download failed` | Network issue or revision unavailable. Check connectivity; see `references/browser_snap_troubleshooting.md` section T1. |
| `[STOP] snap ack failed` | Assert file corrupt or mismatched. Delete `--work-dir` contents and rerun phase download. |
| `[STOP] snap install failed` | See `references/browser_snap_troubleshooting.md` section T2 for common install errors. |
| `[STOP] snap refresh --hold failed` | snapd version may not support hold. See section T3. |
| `[FAIL] browser still not launching` | snapd is fixed but browser snap itself may be broken. See `references/browser_snap_troubleshooting.md` section T4. |

---

## After verify passes — launch the browser

```bash
# Chromium
snap run chromium

# Firefox
snap run firefox
```

If the browser still does not open, check `journalctl -xe | grep snap` for confinement errors
and refer to `references/browser_snap_troubleshooting.md` section T4.

---

## Reference files

- `references/browser_snap_troubleshooting.md` — T1–T4 recovery playbook
- `scripts/fix_browser_snap.sh`                — main phase-driven repair script
