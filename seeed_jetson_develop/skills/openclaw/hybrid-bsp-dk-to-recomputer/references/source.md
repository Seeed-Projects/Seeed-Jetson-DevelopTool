# 从 Orin Nano DevKit 制作 DIY BSP 并适配 reComputer Classic / Super

> Source: https://wiki.seeedstudio.com/cn/make_diy_bsp_from_orin_nano_devkit_to_recomputer_classic_and_super/
>
> This file is an archived copy of the Seeed wiki page for reference.

本 Wiki 演示如何从 **NVIDIA Jetson Orin Nano Developer Kit** 克隆完整开发环境，换用 **Seeed reComputer** 的板级启动固件，制作 Hybrid BSP 并完成刷写。

本流程支持两个目标板型：

- **reComputer Classic**（J4011/J4012，板级配置 `recomputer-orin-j401`）
- **reComputer Super**（板级配置 `recomputer-orin-super-j401`）

两者核心思路一致——**保留 DevKit 的整盘 APP，重新生成目标板的 QSPI**——但在 pinmux、摄像头 overlay 和磁盘布局等细节上有所不同。

本流程已在 JetPack 6.2 / L4T 36.4.3、Orin Nano 8GB（SKU 0005）上完成实机刷写与启动验收。

## 你要达成什么

| 目标 | 产物 | 用途 |
|---|---|---|
| A. 同载板克隆 | `mfi_jetson-orin-nano-devkit-nvme.tar.gz` | 再刷回 DevKit，完整环境克隆 |
| B. 目标板 Bundle | `mfi_recomputer-orin-j401.tar.gz`（Classic）/ `mfi_recomputer-orin-super-j401.tar.gz`（Super） | 刷到目标板：目标板级 QSPI + DevKit 整盘 APP（含 `/home`） |
| C. 稳妥回退 | 官方 BSP + 只迁 `/home` | Hybrid 异常时用 |

> **DANGER:** 不要把 DevKit 的 `mfi_jetson-orin-nano-devkit-nvme` 直接刷到目标板。不要只改 mfi 目录里某个 `.dtb` 就当适配完成。不要把 Classic 的 Hybrid 包刷到 Super，反之亦然——两者 pinmux 和摄像头 overlay 不同。

## 前提条件

### 硬件

- 源机：Orin Nano **Developer Kit**（本例模块 **SKU 0005** = Orin Nano 8GB，NVMe 启动）
- 目标机：Seeed **reComputer Classic J4011/J4012** 或 **reComputer Super**（模块建议同为 0005）
- 主机：Ubuntu 22.04 x86_64，USB Type-C 数据线（刷写口）
- 磁盘：建议预留 **≥ 100GB** 空闲（备份 + 双 mfi + 快照）

> reComputer Classic 系列的散热不足以支持 MAXN 超级模式。如果您在 Classic 设备上刷写了 JetPack 6.2，请不要启用 MAXN 模式。

### 主机依赖

```bash
sudo apt-get update -y
sudo apt-get install -y \
  build-essential flex bison libssl-dev \
  sshpass abootimg nfs-kernel-server \
  libxml2-utils qemu-user-static
```

备份/刷写前：

```bash
sudo systemctl stop udisks2.service
sudo service nfs-kernel-server start
lsusb | grep 0955:7523 # 必须看到 NVIDIA Corp. APX
```

### 板型对照

| 项目 | DevKit | reComputer Classic | reComputer Super |
|---|---|---|---|
| board-name | `jetson-orin-nano-devkit-nvme` | `recomputer-orin-j401` | `recomputer-orin-super-j401` |
| 配置文件 | `p3768-0000-p3767-0000-a0-nvme.conf` | `recomputer-orin-j401.conf` | `recomputer-orin-super-j401.conf` |
| Pinmux | NVIDIA DevKit（DP） | Classic HDMI | Super HDMI |
| 摄像头 overlay | NVIDIA dynamic | Seeed dual IMX219 | Seeed quad IMX219 |
| SKU0005 主 DTB | `...-0005-nv(-super).dtb` | 仍用 `tegra234-p3768-0000+p3767-0005-nv-super.dtb` |  |
| 最终 mfi | DevKit 专用 | Classic 专用 | Super 专用 |

## 1. 准备 Linux_for_Tegra 工作区

从 Seeed wiki 下载 L4T 工作包（本例为 JetPack 6.2 / L4T 36.4.3 plus）。

```bash
sudo tar xpf L4T_36.4.3_plus.tar.gz
cd Linux_for_Tegra/
sudo ./apply_binaries.sh
cd ..

export ARCH=arm64
export CROSS_COMPILE="$PWD/aarch64--glibc--stable-2022.08-1/bin/aarch64-buildroot-linux-gnu-"
export PATH="$PWD/aarch64--glibc--stable-2022.08-1/bin:$PATH"
export INSTALL_MOD_PATH="$PWD/Linux_for_Tegra/rootfs/"

cd Linux_for_Tegra/source
./nvbuild.sh
./do_copy.sh
./nvbuild.sh -i
```

验收：

**reComputer Classic:**
```bash
test -f Linux_for_Tegra/recomputer-orin-j401.conf
test -f Linux_for_Tegra/jetson-orin-nano-devkit-nvme.conf
ls Linux_for_Tegra/kernel/dtb/tegra234-j401-*-recomputer.dtb
ls Linux_for_Tegra/kernel/dtb/tegra234-dcb-p3767-0000-hdmi.dtbo
```

**reComputer Super:**
```bash
cd Linux_for_Tegra
test -f recomputer-orin-super-j401.conf
test -f jetson-orin-nano-devkit-nvme.conf
test -f kernel/dtb/tegra234-dcb-p3767-0000-hdmi.dtbo
test -f kernel/dtb/tegra234-p3767-camera-p3768-imx219-quad-seeed.dtbo
```

## 2. 从 DevKit 备份完整环境

### 2.1 源机进恢复模式

用 USB Type-C 数据线将 DevKit 刷写口连接到主机，并进入恢复模式。主机执行 `lsusb` 应看到 `0955:7523` APX。

备份过程中设备可能短暂变成 `0955:7035`（Linux for Tegra / initrd），属正常。

### 2.2 备份命令

```bash
cd Linux_for_Tegra
sudo ./tools/backup_restore/l4t_backup_restore.sh \
  -e nvme0n1 -b -c jetson-orin-nano-devkit-nvme
```

> 源机是 DevKit 时，不要用目标板 board-name 做第一次备份，否则 `board_spec` / 后续基线会乱。

### 2.3 验收

```bash
ls -lah tools/backup_restore/images/
head -5 tools/backup_restore/images/nvpartitionmap.txt
```

应看到：
- `board_spec` 含 `jetson-orin-nano-devkit-nvme`
- `nvme0n1p1.tar.zst`（或后续转换的大 APP）体积为 GB 级
- 存在 `QSPI0.img`（这是 DevKit 的 QSPI，后面 Hybrid 不能直接当目标板用）

建议立刻打快照：
```bash
sudo cp -a tools/backup_restore/images ~/backup_images_dk_sku0005
```

## 3. 打出 DevKit 同载板 DIY BSP（可选）

设备再次进入 APX。主机执行 `lsusb` 应看到 `0955:7523 APX`：

```bash
cd Linux_for_Tegra
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --use-backup-image --no-flash --network usb0 --massflash 5 \
  jetson-orin-nano-devkit-nvme internal
```

产物：
- `mfi_jetson-orin-nano-devkit-nvme/`
- `mfi_jetson-orin-nano-devkit-nvme.tar.gz`

> 仅用于再刷 DevKit。禁止刷目标板。这个包的 APP 可作为后续 Hybrid Bundle 的数据源，但它的 QSPI 不能复用。

## 4. 必读：QSPI 陷阱

`--use-backup-image` 经 `convert_backup_image_to_initrd_flash` 会把：

| 备份内容 | 放到 |
|---|---|
| NVMe / APP | `tools/kernel_flash/images/external/` |
| 源机 `QSPI0.img` | `tools/kernel_flash/images/internal/` |

因此：

| 错误做法 | 结果 |
|---|---|
| 只改 `mfi/.../rootfs` 或某个 `.dtb` | 无效（真正刷的是 bak / QSPI） |
| 备份来自 DevKit，却直接换目标板 board-name + `--use-backup-image` | 仍刷 DevKit QSPI（DP pinmux），HDMI/USB 可能异常 |
| 改 conf 后再 `--flash-only` | `--flash-only` 不会按 conf 重算镜像 |

目标板真正差在 conf 里的 HDMI pinmux + DCB/camera overlay：

**reComputer Classic** `recomputer-orin-j401.conf` 关键内容：
```
PINMUX_CONFIG="tegra234-mb1-bct-pinmux-p3767-hdmi-a03.dtsi"
PMC_CONFIG="tegra234-mb1-bct-padvoltage-p3767-hdmi-a03.dtsi"
OVERLAY_DTB_FILE+=",tegra234-dcb-p3767-0000-hdmi.dtbo,tegra234-p3767-camera-p3768-imx219-dual-seeed.dtbo"
DCE_OVERLAY_DTB_FILE="tegra234-dcb-p3767-0000-hdmi.dtbo"
```

**reComputer Super** `recomputer-orin-super-j401.conf` 关键内容：
```
PINMUX_CONFIG="recomputer-super-orin-j401-pinmux-p3767-hdmi-a03.dtsi";
PMC_CONFIG="recomputer-super-orin-j401-padvoltage-p3767-hdmi-a03.dtsi";
OVERLAY_DTB_FILE+=",tegra234-dcb-p3767-0000-hdmi.dtbo,tegra234-p3767-camera-p3768-imx219-quad-seeed.dtbo";
DCE_OVERLAY_DTB_FILE="tegra234-dcb-p3767-0000-hdmi.dtbo";
```

对 SKU 0005，主 DTB 文件名仍是 NVIDIA 的 `*-0005-nv-super.dtb`，不是强行换成 `*-0000-recomputer.dtb`（那是 NX 16GB 路径）。

## 5. Hybrid BSP：做目标板 Bundle

核心思路：
1. APP：继续用 DevKit 备份（整盘用户环境）
2. QSPI：用目标板 conf 重新生成（不要 `--use-backup-image`）
3. 组装成目标板 mfi

### 5.1 准备 APP-only（去掉 DevKit QSPI）

```bash
cd Linux_for_Tegra
sudo cp -a ~/backup_images_dk_sku0005 \
  tools/backup_restore/images_app_only
sudo rm -f tools/backup_restore/images_app_only/QSPI0.img
sudo sed -i '/qspi/Id' tools/backup_restore/images_app_only/nvpartitionmap.txt
```

将 APP-only 转成 initrd flash 的 `external` 镜像（可用备份工具的 convert，或复用 DevKit 打包步骤已有的 `tools/kernel_flash/images/external/` 大 APP）。

### 5.2 生成目标板 QSPI

设备须处于 APX。模块参数与备份一致（本例 3767 / 0005 / 300 / V.2）：

**reComputer Classic:**
```bash
cd Linux_for_Tegra
sudo BOARDID=3767 BOARDSKU=0005 FAB=300 BOARDREV=V.2 CHIP_SKU=00:00:00:D5 \
  ./tools/kernel_flash/l4t_initrd_flash.sh \
  --external-device nvme0n1p1 \
  -c tools/kernel_flash/flash_l4t_t234_nvme.xml \
  -p "-c bootloader/generic/cfg/flash_t234_qspi.xml --no-systemimg" \
  --no-flash --massflash 5 --showlogs --network usb0 \
  recomputer-orin-j401 internal
```

日志中应出现 HDMI pinmux，例如：`tegra234-mb1-bct-pinmux-p3767-hdmi-a03`。

**reComputer Super:**

先创建继承 Super 板级配置、但明确以 NVMe 为根设备的别名：
```bash
cd Linux_for_Tegra
cat > recomputer-orin-super-j401-nvme.conf <<'EOF'
source "${LDK_DIR}/recomputer-orin-super-j401.conf";
EOF
```

```bash
cd Linux_for_Tegra
sudo BOARDID=3767 BOARDSKU=0005 FAB=300 BOARDREV=V.2 \
  CHIP_SKU=00:00:00:D5 \
  ./tools/kernel_flash/l4t_initrd_flash.sh \
  --external-device nvme0n1p1 \
  -c tools/kernel_flash/flash_l4t_t234_nvme.xml \
  -p "-c bootloader/generic/cfg/flash_t234_qspi.xml --no-systemimg" \
  --no-flash --massflash 5 --showlogs --network usb0 \
  recomputer-orin-super-j401-nvme external
```

> 不要在本场景中以 `internal` 作为最后的 rootdev。实测这样生成的 MB2 会把 secondary storage 配成 `SDCARD instance: 0`，没有 SD 卡时启动停在 `Busy Spin`。

日志应包含：
```
recomputer-super-orin-j401-pinmux-p3767-hdmi-a03.dtsi
tegra234-p3767-camera-p3768-imx219-quad-seeed.dtbo
```

保存新 QSPI internal：
```bash
# Classic:
sudo cp -a tools/kernel_flash/images/internal ~/j401_qspi_internal_save
# Super:
sudo cp -a tools/kernel_flash/images/internal ~/super_j401_qspi_internal_save
```

确认 Super mfi 的 `internal/flash.idx` 存在，并且没有源 DevKit 的单体 `QSPI0.img`：
```bash
test -f mfi_recomputer-orin-super-j401/tools/kernel_flash/images/internal/flash.idx
test ! -f mfi_recomputer-orin-super-j401/tools/kernel_flash/images/internal/QSPI0.img
```

#### 预制 QSPI 下载（快捷路径）

本指南实测生成的 QSPI internal（SKU 0005 / L4T 36.4.3）已上传，可直接下载使用：

**Classic:**
```bash
wget -O j401_qspi_internal_save.tar.gz \
  https://files.seeedstudio.com/wiki/reComputer-Jetson/FAQ/dk-to-classic/j401_qspi_internal_save.tar.gz
mkdir -p Linux_for_Tegra/tools/kernel_flash/images/internal
tar xpf j401_qspi_internal_save.tar.gz -C Linux_for_Tegra/tools/kernel_flash/images/internal/
```

**Super:**
```bash
wget -O super_j401_qspi_internal_save.tar.gz \
  https://files.seeedstudio.com/wiki/reComputer-Jetson/FAQ/dk-to-super/super_j401_qspi_internal_save.tar.gz
mkdir -p Linux_for_Tegra/tools/kernel_flash/images/internal
tar xpf super_j401_qspi_internal_save.tar.gz -C Linux_for_Tegra/tools/kernel_flash/images/internal/
```

复用前提：目标板为 reComputer Classic J4011/J4012 或 Super、模块 SKU 0005、L4T 36.4.3。若任一条件不符，必须按本节重新生成。

### 5.3 组装 mfi

**reComputer Classic:**

最终目录应满足：

| 路径 | 内容 |
|---|---|
| `mfi_recomputer-orin-j401/recomputer-orin-j401.conf` | 存在 |
| `.../tools/kernel_flash/images/internal/` | J401 新 QSPI（无 DevKit 单体 `QSPI0.img`，或哈希与 DevKit 不同；`flash.idx` 常为多行分片） |
| `.../tools/kernel_flash/images/external/nvme0n1p1_bak.img` | GB 级 APP |

打包归档（可选）：
```bash
cd Linux_for_Tegra
sudo tar czf mfi_recomputer-orin-j401.tar.gz mfi_recomputer-orin-j401
```

**reComputer Super:**

> 不要无条件复制 DevKit mfi 的整个 `external/`。如果 DevKit 源盘为 256GB，而 Super 目标盘为 128GB，源 GPT 会在 `partprobe` 阶段报 "GPT is larger than device storage"。

本实测目标盘为 `128035676160` bytes。使用 `flash_l4t_t234_nvme.xml` 生成的标准 external 布局总长 `102400000000` bytes，然后只替换 APP 内容：

```bash
cd Linux_for_Tegra
# 使用 Super/当前工作区生成的标准 external：
sudo cp -a tools/kernel_flash/images/external/. \
  mfi_recomputer-orin-super-j401/tools/kernel_flash/images/external/
# 只复用 DevKit APP 内容：
sudo cp -a \
  mfi_jetson-orin-nano-devkit-nvme/tools/kernel_flash/images/external/nvme0n1p1_bak.img* \
  mfi_recomputer-orin-super-j401/tools/kernel_flash/images/external/
sudo tee \
  mfi_recomputer-orin-super-j401/tools/kernel_flash/images/external/flash.cfg \
  >/dev/null <<'EOF'
APP_ext=nvme0n1p1_bak.img
external_device=nvme0n1p1
EOF
```

验收：
```bash
test -f mfi_recomputer-orin-super-j401/recomputer-orin-super-j401.conf
test -f mfi_recomputer-orin-super-j401/tools/kernel_flash/images/external/nvme0n1p1_bak.img
test ! -f mfi_recomputer-orin-super-j401/tools/kernel_flash/images/internal/QSPI0.img
```

打包归档：
```bash
cd Linux_for_Tegra
sudo tar czf mfi_recomputer-orin-super-j401.tar.gz \
  mfi_recomputer-orin-super-j401
sudo gzip -t mfi_recomputer-orin-super-j401.tar.gz
sha256sum mfi_recomputer-orin-super-j401.tar.gz \
  > mfi_recomputer-orin-super-j401.tar.gz.sha256
```

## 6. 刷写到目标机

### 6.1 目标机进 APX

`lsusb` → `0955:7523 NVIDIA Corp. APX`

### 6.2 刷写命令

若本机已有解压目录，不要再 `tar xpf`：

**reComputer Classic:**
```bash
cd Linux_for_Tegra/mfi_recomputer-orin-j401
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --flash-only --massflash 1 --network usb0 --showlogs
```

**reComputer Super:**
```bash
cd Linux_for_Tegra/mfi_recomputer-orin-super-j401
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --flash-only --massflash 1 --network usb0 --showlogs
```

仅当另一台电脑只有 `.tar.gz` 时：

**reComputer Classic:**
```bash
sudo tar xpf mfi_recomputer-orin-j401.tar.gz
cd mfi_recomputer-orin-j401
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --flash-only --massflash 1 --network usb0 --showlogs
```

**reComputer Super:**
```bash
sudo tar xpf mfi_recomputer-orin-super-j401.tar.gz
cd mfi_recomputer-orin-super-j401
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --flash-only --massflash 1 --network usb0 --showlogs
```

> 如果刷到 recovery 或 APP 时出现 `/mnt/external/...: Permission denied`，这是 NFS 权限问题。

### 6.3 刷写过程中正常现象

| 日志 | 含义 |
|---|---|
| `p3768-0000-p3767-0000-a0.conf: 没有那个文件或目录` | `--flash-only` 下常见，镜像已预生成，可继续 |
| `rpcbind already running` | 可忽略 |
| `blockdev: cannot open /dev/mmcblk0boot0` | Orin Nano 无该分区，常见无害 |
