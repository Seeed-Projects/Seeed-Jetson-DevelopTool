---
name: spi-enable-jetsonnano
description: Enable SPI1 interface on Jetson Nano by modifying the device tree before flashing. Covers DTB decompilation, SPI pin patching, recompilation, flashing, and loopback testing. Must be applied before flashing the image.
---

# Enable SPI Interface on Jetson Nano

## Execution model

Run one phase at a time. After each phase, verify the expected result before continuing.
- If a phase succeeds → print `[OK]` and move to the next phase.
- If a phase fails → print `[STOP]`, consult the failure decision tree, and ask the user before retrying.

**Important:** This procedure must be performed on the host PC before flashing the Jetson Nano. SPI cannot be enabled via `jetson-io.py` on Nano.

## Phase 1 — Enter recovery mode and prepare BSP on host PC

Short the `REC` and `GND` pins on the Jetson Nano to enter recovery mode.

Download L4T BSP and Root Filesystem from [NVIDIA Jetson Linux Archive](https://developer.nvidia.com/embedded/jetson-linux-archive) (example uses L4T 32.7.2):

```bash
tar xf Jetson-210_Linux_R32.7.2_aarch64.tbz2
cd Linux_for_Tegra/rootfs/
sudo tar xpf ../../Tegra_Linux_Sample-Root-Filesystem_R32.7.2_aarch64.tbz2
cd ..
sudo ./apply_binaries.sh
```

Expected: BSP extracted and binaries applied without errors.

## Phase 2 — Create and run SPI modification script

Create `modify_spi.sh` in the `Linux_for_Tegra` directory with the following content, then run it:

```bash
cat << 'SCRIPT_EOF' > modify_spi.sh
#!/bin/bash
set -e

cd "$(dirname "$0")"
cd kernel/dtb

DTS=tegra210-p3448-0002-p3449-0000-b00.dts
DTB=tegra210-p3448-0002-p3449-0000-b00.dtb

echo "Decompiling $DTB to $DTS..."
sudo dtc -I dtb -O dts -o "$DTS" "$DTB"

fix_spi_node() {
    local node=$1
    if grep -A5 "$node {" "$DTS" | grep -q 'status'; then
        sudo sed -i "/$node {/,/spi-max-frequency/ s/status = \".*\";/status = \"okay\";/" "$DTS"
    else
        sudo sed -i "/$node {/,/spi-max-frequency/ s/compatible = \"tegra-spidev\";/&\n\t\tstatus = \"okay\";/" "$DTS"
    fi
}

echo "Enabling spi@0 and spi@1..."
fix_spi_node "spi@0"
fix_spi_node "spi@1"

patch_pin() {
    local pin=$1
    sudo sed -i "/${pin} {/,/nvidia,enable-input/ {
        s/nvidia,function = \"rsvd1\"/nvidia,function = \"spi1\"/
        s/nvidia,tristate = <0x01>/nvidia,tristate = <0x00>/
        s/nvidia,enable-input = <0x00>/nvidia,enable-input = <0x01>/
    }" "$DTS"
}

echo "Patching pinmux blocks..."
for pin in spi1_mosi_pc0 spi1_miso_pc1 spi1_sck_pc2 spi1_cs0_pc3 spi1_cs1_pc4; do
    patch_pin "$pin"
done

echo "Fixing tristate and input-enable for SPI1 pins..."

fix_pinmux_field() {
  local pin=$1
  awk -v pin="$pin" '
  BEGIN { in_block = 0 }
  {
    if ($0 ~ pin " {") { in_block = 1 }
    if (in_block && /nvidia,tristate =/) { sub(/<0x1>/, "<0x0>") }
    if (in_block && /nvidia,enable-input =/) { sub(/<0x0>/, "<0x1>") }
    print
    if (in_block && /}/) { in_block = 0 }
  }' "$DTS" | sudo tee "$DTS.fixed" > /dev/null && sudo mv "$DTS.fixed" "$DTS"
}

fix_pinmux_field "spi1_mosi_pc0"
fix_pinmux_field "spi1_miso_pc1"
fix_pinmux_field "spi1_sck_pc2"
fix_pinmux_field "spi1_cs0_pc3"
fix_pinmux_field "spi1_cs1_pc4"

echo "Recompiling DTS to $DTB..."
sudo dtc -I dts -O dtb -o "$DTB" "$DTS"

echo "SPI DTS patch applied and DTB regenerated successfully."
SCRIPT_EOF

sudo bash modify_spi.sh
```

To enable SPI2 instead, replace `spi1` with `spi2` in the script.

Expected: Script completes with "SPI DTS patch applied and DTB regenerated successfully."

## Phase 3 — Flash the Jetson Nano

```bash
sudo ./flash.sh jetson-nano-emmc mmcblk0p1
```

Expected: Flash completes successfully. After reboot, SPI pins are available on the 40-pin header.

## Phase 4 — Test SPI1 with loopback

On the Jetson Nano, short pin 19 (SPI0_MOSI) and pin 21 (SPI0_MISO) for loopback test.

```bash
sudo modprobe spidev
git clone https://github.com/rm-hull/spidev-test
cd spidev-test/
gcc spidev_test.c -o spidev_test
./spidev_test -v -D /dev/spidev0.0 -p "Test"
```

Verify available SPI devices:

```bash
ls /dev/spidev*
```

Expected: Loopback test shows transmitted data matches received data; `/dev/spidev0.0` exists.

## Failure decision tree

| Symptom | Likely cause | Suggested fix |
|---|---|---|
| `dtc` command not found | Device tree compiler not installed | `sudo apt-get install device-tree-compiler` |
| DTB file not found | Wrong L4T version or path | Verify the DTB filename matches your board revision |
| Flash fails | Device not in recovery mode | Re-short REC and GND pins; verify with `lsusb` on host |
| `/dev/spidev*` not found after boot | Script did not patch correctly | Re-run modify_spi.sh and reflash; check DTS changes |
| Loopback test fails | Pins not shorted properly | Verify pin 19 and pin 21 are connected; check wiring |
| SPI2 needed instead of SPI1 | Wrong SPI controller targeted | Replace `spi1` with `spi2` in modify_spi.sh and reflash |

## Reference files

- `references/source.body.md` — Full original wiki content (reference only)
