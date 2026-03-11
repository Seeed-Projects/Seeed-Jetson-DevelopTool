---
name: ko-module-build
description: Compile and load a custom .ko kernel driver module on Seeed Jetson devices (reComputer/reServer). Downloads BSP source, extracts driver code, builds with Makefile, and loads via modprobe. Example uses pl2303 on JetPack 6.2.
---

# Build a .ko Driver Module for Seeed Jetson

When a required `.ko` driver module is missing from reComputer/reServer,
compile it directly on the Jetson device. This guide uses the `pl2303`
USB-to-serial driver on JetPack 6.2 (L4T 36.4.3) as an example.

Hardware: Seeed Jetson device (reComputer/reServer)
Software: JetPack 6.x (L4T 36.x), internet connection

---

## Execution model

Run one phase at a time. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed

Replace `<driver_name>` with the actual driver (e.g. `pl2303`) throughout.

---

## Phase 1 — identify L4T version and target driver (~30 s)

```bash
cat /etc/nv_tegra_release
```

Determine the L4T version (e.g. 36.4.3 = JetPack 6.2). Find the JetPack ↔ L4T
mapping at: https://developer.nvidia.com/embedded/jetpack-archive

Ask the user which driver module they need (e.g. `pl2303`, `ch341`, etc.).

`[OK]` when L4T version and target driver are confirmed.

---

## Phase 2 — download and extract BSP source (~10 min)

Download `public_sources.tbz2` for the matching L4T version from NVIDIA's
L4T release page.

Extract all nested archives:
```bash
tar -xjf public_sources.tbz2
cd Linux_for_Tegra/source

find . -type f \( -name "*.tbz2" -o -name "*.tar.bz2" -o -name "*.tar.gz" -o -name "*.tgz" -o -name "*.tar.xz" \) -exec bash -c '
    dir=$(dirname "$1")
    filename=$(basename "$1")
    cd "$dir"
    if [[ "$filename" == *.tbz2 || "$filename" == *.tar.bz2 ]]; then
        tar -xjf "$filename"
    elif [[ "$filename" == *.tar.gz || "$filename" == *.tgz ]]; then
        tar -xzf "$filename"
    elif [[ "$filename" == *.tar.xz ]]; then
        tar -xJf "$filename"
    fi
    cd - > /dev/null
' _ {} \;
```

`[OK]` when extraction completes without errors.

---

## Phase 3 — locate driver source file (~1 min)

```bash
sudo find . -type f -name "*<driver_name>*"
# Example: sudo find . -type f -name "*pl2303*"
```

Note the path — it indicates both the source file and the target install path.

`[OK]` when driver source file (e.g. `pl2303.c`) is found.
`[STOP]` if not found — driver may not be in this BSP version.

---

## Phase 4 — create build workspace (~1 min)

```bash
mkdir -p ~/ko_build && cd ~/ko_build
cp <path_to_driver_source>/<driver_name>.c .
```

Create a `Makefile` in the workspace:
```makefile
obj-m += <driver_name>.o
all:
	make -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules
clean:
	make -C /lib/modules/$(shell uname -r)/build M=$(PWD) clean
```

Replace `<driver_name>` with the actual name (e.g. `pl2303`).

`[OK]` when workspace contains both the `.c` source and `Makefile`.

---

## Phase 5 — create kernel build symlink (~30 s)

```bash
sudo rm -rf /lib/modules/$(uname -r)/build
sudo ln -s /usr/src/linux-headers-$(uname -r)-ubuntu22.04_aarch64/3rdparty/canonical/linux-jammy/kernel-source \
  /lib/modules/$(uname -r)/build
```

`[OK]` when symlink is created without errors.
`[STOP]` if the headers path doesn't exist — install `linux-headers-$(uname -r)`.

---

## Phase 6 — compile the module (~1–5 min)

```bash
cd ~/ko_build
make
```

`[OK]` when `.ko` file is generated in the current directory.
`[STOP]` on compile errors — see failure decision tree.

---

## Phase 7 — install and load the module (~30 s)

Copy to the correct kernel module path. The target path prefix is always
`/lib/modules/$(uname -r)/kernel/` — the suffix matches the source tree structure.

```bash
# Example for pl2303 (USB serial driver):
sudo cp <driver_name>.ko /lib/modules/$(uname -r)/kernel/drivers/usb/serial/
```

Load the module:
```bash
sudo depmod -a
sudo modprobe <driver_name>
```

Verify:
```bash
modinfo <driver_name>
```

`[OK]` when `modinfo` shows the module details.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Driver source not found in BSP | Verify L4T version matches. Try searching with broader keywords. |
| Symlink target path doesn't exist | Install kernel headers: `sudo apt-get install -y linux-headers-$(uname -r)` |
| `make` fails with missing headers | Verify symlink in Phase 5. Check that kernel-source directory has `Makefile`. |
| `make` fails with undefined symbols | Driver may depend on other modules. Check `#include` directives in source. |
| `modprobe` fails | Check `dmesg` for errors. Ensure `.ko` is in the correct path. Run `sudo depmod -a` again. |
| Module loads but device not working | Check `dmesg` for hardware errors. Verify device is connected and recognized by `lsusb` or `lspci`. |

---

## Reference files

- `references/source.body.md` — Original Seeed wiki with screenshots and step-by-step walkthrough
