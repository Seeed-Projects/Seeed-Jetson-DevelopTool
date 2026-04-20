---
name: cochl-sense-setup
description: "Deploy Cochl.Sense sound recognition on Jetson (37 sounds, 94% F1 score). Requires a trial license from Cochl and a USB microphone. Supports JetPack 4.6+."
---

# Cochl.Sense Sound Recognition — Jetson Setup

Cochl.Sense is a machine listening SDK that recognises 37 target sounds at 94% F1 score.
It runs on Jetson via a pre-built AArch64 C++ SDK. A trial license is required before
any code can execute — **ask the user if they have one before starting Phase 2.**

Hardware: Jetson with JetPack 4.6+, USB microphone (16-bit, 22050 Hz)

Reference: `references/source.body.md` (Cochl docs, SDK download links, tutorial repo)

---

## Execution model

Run **one phase at a time**. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase

---

## Phase 1 — license & project (~5 min, human action required)

**Ask the user:** "Do you already have a Cochl.Sense trial license and a project API key?"

If **no**:
1. Request a trial license: https://forms.gle/Pa2iYWirLJVNS7Pp6
2. After approval, create a project at: https://dashboard.cochl.ai
3. Copy the **API key** from the project dashboard

If **yes**: ask the user to provide the API key now — it is needed in Phase 3.

`[OK]` when the user has confirmed they have an API key.

---

## Phase 2 — download SDK & tutorials (~5 min)

Check JetPack version:
```bash
cat /etc/nv_tegra_release
```

Confirm JetPack 4.6 or later (L4T R32.7+). If earlier → `[STOP] unsupported JetPack`.

Download the AArch64 SDK from Cochl Docs → Resources section.
(Exact download URL is in `references/source.body.md`.)

Clone the tutorials repository:
```bash
git clone https://github.com/cochlearai/sense-sdk-cpp-tutorials
```

Verify both are present:
```bash
ls sense-sdk-cpp-tutorials-main/
ls sense/   # the downloaded SDK folder
```

`[OK]` if both directories exist.

---

## Phase 3 — setup: move SDK into tutorials (~1 min)

Move the `sense/` SDK folder into the tutorials directory:
```bash
mv sense/ sense-sdk-cpp-tutorials-main/
```

Verify the layout:
```bash
ls sense-sdk-cpp-tutorials-main/sense/
```

Expected: `include/`, `lib/`, and related SDK files.

Insert the API key into the sample config (path may vary — check `references/source.body.md`):
```bash
# Edit the config file and replace YOUR_API_KEY with the actual key
sed -i 's/YOUR_API_KEY/<API_KEY>/' sense-sdk-cpp-tutorials-main/config.json
```

`[OK]` when SDK is in place and API key is set.

---

## Phase 4 — build & run (~3–5 min)

Check USB microphone is detected:
```bash
arecord -l
```

Expected: at least one capture device listed. If none → `[STOP] no microphone detected`.

Build the sample application:
```bash
cd sense-sdk-cpp-tutorials-main
mkdir -p build && cd build
cmake ..
make -j$(nproc)
```

Run the sample:
```bash
./sense_sample
```

Expected output: a stream of recognised sound labels printed to stdout (e.g. `Speech`, `Silence`).

`[OK]` if sound labels appear in the output.

---

## Failure decision tree

| Symptom | Action |
|---|---|
| `[STOP] unsupported JetPack` | Cochl.Sense requires JetPack 4.6+. Flash a supported version before continuing |
| User does not have a license | Direct them to https://forms.gle/Pa2iYWirLJVNS7Pp6 — cannot proceed without it |
| SDK download fails | Check Cochl Docs → Resources for updated link; see `references/source.body.md` |
| `git clone` fails | Check network connectivity: `ping github.com`. Retry or download ZIP manually |
| `cmake` not found | `sudo apt install cmake` |
| Build fails — missing headers | Confirm `sense/` is inside `sense-sdk-cpp-tutorials-main/` and re-run cmake |
| `[STOP] no microphone detected` | Run `lsusb` to confirm USB mic is connected. Try a different USB port. Check `dmesg | tail -20` |
| `sense_sample` exits with auth error | API key is wrong or expired. Re-check the key in the dashboard at https://dashboard.cochl.ai |
| Output shows only `Silence` | Microphone gain too low. Run `alsamixer` and increase capture volume |
