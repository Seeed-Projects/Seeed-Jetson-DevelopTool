---
name: cvedia-setup
description: Install and run CVEDIA-RT AI inference engine on NVIDIA Jetson for pre-built computer vision applications (crowd estimation, drone detection, vehicle counting, etc.). Requires JetPack 5.1 and a CVEDIA account.
---

# CVEDIA-RT on NVIDIA Jetson

CVEDIA-RT is a modular, cross-platform AI inference engine with pre-loaded
applications: crowd estimation, drone detection, fall detection, lane occupancy,
vehicle type counter, package detection, and more.

Hardware: NVIDIA Jetson device (tested with reComputer J4012)
Software: JetPack 5.1 with all SDK components, internet connection
Account: CVEDIA (free sign-up at rt.cvedia.com)

---

## Execution model

Run one phase at a time. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed

---

## Phase 1 — prerequisites check (~30 s)

```bash
cat /etc/nv_tegra_release
# Expected: R35 (release) for JetPack 5.x
```

```bash
dpkg -l | grep nvidia-jetpack
```

`[OK]` when JetPack 5.1+ with SDK components confirmed.
`[STOP]` if JetPack version is incompatible.

---

## Phase 2 — download CVEDIA-RT (human action + ~5 min)

1. Visit https://rt.cvedia.com/ and sign in (or create account)
2. Click Download under "NVIDIA Jetson"
3. Select "Docker (Recommended)" to download the tar.gz installer

Transfer the file to the Jetson device.

`[OK]` when tar.gz file is on the Jetson.

---

## Phase 3 — install CVEDIA-RT (~3 min)

```bash
mkdir -p ~/cvedia && cd ~/cvedia
tar -xzvf <filename.tar.gz>
sudo ./install.sh
```

Respond to installer prompts as needed.

`[OK]` when installation completes without errors.

---

## Phase 4 — run CVEDIA-RT (~1 min)

With internet (first run, downloads models):
```bash
./run.sh
```

Without internet (after first online run):
```bash
./run.sh -U
```

Expected: CVEDIA-RT application opens with pre-loaded solutions.

`[OK]` when the application UI is visible.

---

## Phase 5 — explore applications (~5 min)

1. Click on a solution category (e.g. intelligent-transportation-systems)
2. Click the run button next to a solution (e.g. lane-occupancy)
3. Wait for model and video files to download
4. Configure video source: gear icon → Edit Source → select camera/file → Save Instance
5. Stop and restart the application for changes to take effect

`[OK]` when inference results are visible on the video feed.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `install.sh` fails | Verify Docker is installed with nvidia runtime. Check JetPack version. |
| `run.sh` hangs or crashes | Check Docker logs. Ensure sufficient disk space and memory. |
| Application won't start offline | Must run each solution at least once with internet first. |
| Video source not working | Stop application, reconfigure source, restart. Check camera connectivity. |
| Low FPS / poor performance | Ensure JetPack SDK components are installed. Check GPU utilization with `tegrastats`. |

---

## Reference files

- `references/source.body.md` — Original Seeed wiki with screenshots and application examples
