---
name: jetson-faq
description: Comprehensive FAQ for Seeed Jetson devices — troubleshooting installation, eMMC space, camera compatibility, USB timeouts, apt upgrade warnings, SPI, SSD boot, ko module building, exFAT mounting, disk encryption, EtherCAT, and UUID errors.
---

# FAQs for Jetson Usage

This is a knowledge-base skill. Use it to answer frequently asked questions
about Seeed Jetson products. Match the user's issue to the relevant Q&A below.

---

## Execution model

This skill is primarily informational. Some answers include commands.
Present the relevant Q&A to the user based on their question.

---

## Phase 1 — identify the user's issue

Match the user's question to one of the FAQ entries below, then provide
the answer and any relevant commands.

`[OK]` when the matching FAQ is identified.

---

## FAQ entries

### Q1: Troubleshooting installation issues
→ See skill: `claude/jetpack-flash-wsl2` or Seeed wiki troubleshooting guide

### Q2: eMMC only has ~2 GB free space
→ See: https://wiki.seeedstudio.com/solution_of_insufficient_space

### Q3: VEYE camera compatibility with reComputer
→ See: https://wiki.seeedstudio.com/Solution_for_the_Compatibility_Issue_between_reComputer_and_VEYE_Camera

### Q4: IMX477 camera + A603 carrier board compatibility
→ See: https://wiki.seeedstudio.com/Use_IMX477_Camera_with_A603_Jetson_Carrier_Board

### Q5: How to get system log of reComputer J30/J40
→ See: https://wiki.seeedstudio.com/get_the_system_log_of_recomputer_j30_and_j40

### Q6: USB timeout during JetPack flash
→ See skill: `claude/usb-timeout-during-flashing`

### Q7: USB-A / Ethernet / HDMI not working after flash
Check file integrity (SHA256 checksums). For A60X carrier boards, ensure the
driver patch was applied to `Linux_for_Tegra/` with `sudo` and `-r` flag:
```bash
sudo cp -r <patch_dir>/* Linux_for_Tegra/
```

### Q8: System crash / black screen after `apt upgrade`
**Do NOT run `apt upgrade` on custom/third-party carrier boards.** Debian
packages from NVIDIA's server don't account for Seeed's custom board design.
This can brick the device. Solution: re-flash JetPack using Seeed's guide.

### Q9: How to upgrade packages safely without `apt upgrade`
→ See: https://wiki.seeedstudio.com/upgrade_software_packages_for_jetson

### Q11: What modifications does Seeed make to NVIDIA's BSP
→ See: https://wiki.seeedstudio.com/differences_of_l4t_between_seeed_and_nvidia

### Q12: How to enable SPI on Jetson Nano
→ See: https://wiki.seeedstudio.com/enable_spi_interface_on_jetsonnano

### Q13: JetPack 5 fails to boot from SSD after flash
→ See skill: `claude/jetpack5-ssd-boot-fix`

### Q14: How to build Seeed's Jetson BSP from source
→ See skill: `claude/bsp-source-build`

### Q15: Why can't `apt upgrade` be run on reComputer/reServer
Kernels and drivers are customized. Running `apt upgrade` replaces them with
NVIDIA's generic packages, causing compatibility issues. Lock critical packages:
```bash
sudo apt-mark hold nvidia-l4t-core
```

### Q16: How to compile a missing .ko driver module
→ See skill: `claude/ko-module-build`

### Q17: How to mount exFAT external drive on JetPack 6

Install dependencies and build exFAT driver:
```bash
sudo apt install -y build-essential autoconf automake libtool pkg-config git libfuse-dev
git clone https://github.com/relan/exfat
cd exfat
autoreconf --install
./configure
make
sudo make install
```

Mount the drive:
```bash
lsblk
sudo mkdir -p /media/seeed/tmp-exfat
sudo mount.exfat /dev/sdX1 /media/seeed/tmp-exfat/
```

### Q18a: How to encrypt Jetson disk before flashing
→ See: https://wiki.seeedstudio.com/how_to_encrypt_the_disk_for_jetson

### Q18b: How to establish EtherCAT communication on Jetson
→ See skill: `claude/ethercat-communication`

### Q18c: UUID error during boot (enters recovery terminal)
→ See: https://wiki.seeedstudio.com/deal_the_issue_of_UUID

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| User's issue doesn't match any FAQ | Search the Seeed forum: https://forum.seeedstudio.com/ |
| Wiki link is broken | Check https://wiki.seeedstudio.com/ for updated URLs |
| User ran `apt upgrade` and bricked device | Must re-flash JetPack. See Seeed flash guide for their board. |
| User unsure which JetPack version they have | Run `cat /etc/nv_tegra_release` |

---

## Reference files

- `references/source.body.md` — Full FAQ document with all questions and cross-reference links
