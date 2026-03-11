---
name: software-package-upgrade
description: Guidance on safely upgrading software packages on Seeed Jetson devices, explaining why OTA/partial updates are risky and recommending full JetPack upgrades or targeted package installs instead.
---

# Upgrade Software Packages for Jetson

## Execution model

Run one phase at a time. After each phase, verify the expected result before continuing.
- If a phase succeeds → print `[OK]` and move to the next phase.
- If a phase fails → print `[STOP]`, consult the failure decision tree, and ask the user before retrying.

## Phase 1 — Understand the risks of partial upgrades

OTA/incremental/partial updates (`sudo apt upgrade`) can harm the Jetson OS by causing dependency mismatches, system instability, and missed security patches. Full JetPack updates are the recommended approach for Seeed Jetson devices.

Key points:
- Seeed releases JetPacks after NVIDIA releases theirs, ensuring stability.
- `sudo apt upgrade` is NOT recommended on Jetson devices.
- Full ROM/JetPack updates maintain system compatibility and security.

## Phase 2 — Upgrade a specific package (if safe)

If you are sure the package does not depend on system-level NVIDIA packages:

```bash
sudo apt-get update
sudo apt-get install <Your_Package>
```

Replace `<Your_Package>` with the specific package name.

```bash
# Verify the installed version
dpkg -l | grep <Your_Package>
```

Expected: Package installs/upgrades without breaking system dependencies.

## Phase 3 — Build from source (alternative)

For open-source software where apt packages are outdated:

```bash
# Download source and compile
# Example pattern:
git clone <source_repo_url>
cd <source_dir>
# Follow project-specific build instructions
make
sudo make install
```

Expected: Software built and installed from source.

## Phase 4 — Wait for new JetPack release (safest option)

Check for new JetPack releases at:
- [NVIDIA JetPack SDK](https://developer.nvidia.com/embedded/jetpack)
- [Seeed Jetson wiki](https://wiki.seeedstudio.com/NVIDIA_Jetson/)

```bash
# Check current JetPack version
cat /etc/nv_tegra_release
dpkg -l | grep nvidia-jetpack
```

Expected: Current version identified; user can plan upgrade to newer JetPack.

## Failure decision tree

| Symptom | Likely cause | Suggested fix |
|---|---|---|
| `apt upgrade` breaks CUDA/TensorRT | Partial upgrade overwrote NVIDIA packages | Reflash with full JetPack image |
| Package has unmet dependencies | Dependency conflict with system packages | Do not force install; build from source instead |
| `apt-get install` fails for specific package | Repository not available or version mismatch | Check `apt-cache policy <pkg>` and add correct repo if needed |
| System unstable after upgrade | Partial update caused mismatches | Reflash with matching JetPack version |

## Reference files

- `references/source.body.md` — Full original wiki content (reference only)
