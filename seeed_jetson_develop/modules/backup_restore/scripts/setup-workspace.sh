#!/usr/bin/env bash
# setup-workspace.sh
# =============================================================================
# 从 git clone 的干净状态一键重建 Jetson BSP 工作区素材。
#
# bsp-workspace 的 GitHub 仓库只含脚本/web/文档(~134 文件)。以下素材不在
# git 里，clone 后必须重建:
#   Downloads/<ver>/      —— NVIDIA 官方 BSP 包 (public_sources/rootfs/Jetson_Linux)
#   Source/<ver>/kernel/  —— 内核源码
#   toolchain/            —— 交叉编译工具链
#   repos/Linux_for_Tegra —— Seeed BSP git 仓库
#   bsp/<ver>/Linux_for_Tegra —— 完整可刷机包 (NVIDIA base + Seeed 覆盖 + rootfs)
#
# 用法:
#   ./setup-workspace.sh [R36.4.3] [--skip-download] [--no-proxy] [--root DIR] [--minimal]
#
# 环境变量:
#   SEED_BRANCH    Seeed 仓库分支 (默认 r36.4.3)
#   TOOLCHAIN_URL  工具链下载地址 (默认 NVIDIA 官方 aarch64--glibc--stable-2022.08-1)
#   BSP_ROOT       工作区根目录 (等效 --root; 打包进应用后脚本目录只读)
#   SUDO_PASS      sudo 密码 (可选, 无则用普通 sudo)
#
# --minimal: 跳过内核源码与工具链 (备份/恢复不需要, 可省约 1GB 下载)。
# =============================================================================
set -euo pipefail

trap 'err "命令失败: $BASH_COMMAND (行号 $LINENO)"' ERR

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSD_ROOT="$(dirname "${WORKSPACE}")"          # /media/seeed/bsp-ssd1

VERSION="${1:-R36.4.3}"
VERSION="R${VERSION#R}"
ROOT="${BSP_ROOT:-}"
SKIP_DOWNLOAD=0
USE_PROXY=1
DO_MINIMAL=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-download) SKIP_DOWNLOAD=1; shift ;;
        --no-proxy)      USE_PROXY=0; shift ;;
        --root)          ROOT="$2"; shift 2 ;;
        --minimal)       DO_MINIMAL=1; shift ;;
        *)               shift ;;   # 位置参数 [R<ver>] 已在上面消费
    esac
done

if [[ -n "$ROOT" ]]; then
    # 打包进应用后脚本目录 (site-packages) 只读, 把整个工作区重定向到用户可写目录。
    # repos/bsp 挂 ROOT 下, Downloads/Source/toolchain 也挂 ROOT 下。
    WORKSPACE="$ROOT"
    SSD_ROOT="$ROOT"
fi

REPOS_DIR="${SSD_ROOT}/repos"
BSP_DIR="${SSD_ROOT}/bsp"
DOWNLOADS="${WORKSPACE}/Downloads"
SOURCE_DIR="${WORKSPACE}/Source"
TOOLCHAIN_DIR="${WORKSPACE}/toolchain"

# ---------- 代理 ----------
detect_proxy() {
    (( USE_PROXY )) || return 0
    local p
    for p in "http://127.0.0.1:7897" "http://127.0.0.1:7890" "http://127.0.0.1:1080"; do
        if timeout 3 curl -sI -x "$p" https://github.com >/dev/null 2>&1; then
            echo "$p"
            return 0
        fi
    done
    echo ""
}

C_GREEN=$'\e[32m'; C_YELLOW=$'\e[33m'; C_RED=$'\e[31m'; C_RESET=$'\e[0m'
ok()   { printf '%s✓%s %s\n' "${C_GREEN}" "${C_RESET}" "$1"; }
warn() { printf '%s!%s %s\n' "${C_YELLOW}" "${C_RESET}" "$1"; }
err()  { printf '%s✗%s %s\n' "${C_RED}" "${C_RESET}" "$1"; }
section() { printf '\n========== %s ==========\n' "$1"; }
progress() { echo "[PROGRESS] $1 $2 $3"; }

sudorun() {
    # 用本地固定 sudo 密码执行 (环境无交互); 无密码则走普通 sudo
    if [ -n "${SUDO_PASS:-}" ]; then
        echo "${SUDO_PASS}" | sudo -S -p '' "$@"
    else
        sudo "$@"
    fi
}

PROXY="$(detect_proxy)"
[[ -n "$PROXY" ]] && ok "检测到代理: $PROXY" || warn "无可用代理 (需要访问 github.com / developer.nvidia.com)"

# ---------- 1. 目录骨架 ----------
section "创建目录骨架"
mkdir -p "${REPOS_DIR}" "${BSP_DIR}" "${DOWNLOADS}/${VERSION}" "${SOURCE_DIR}/${VERSION}"
ok "repos/ bsp/ Downloads/${VERSION} Source/${VERSION} 就绪"
[[ -d "${SSD_ROOT}/builds" ]] || mkdir -p "${SSD_ROOT}/builds"

# ---------- 2. NVIDIA 官方包 ----------
if (( SKIP_DOWNLOAD )); then
    warn "跳过下载 (--skip-download)"
    echo "[PHASE] download"
    progress 2 5 "NVIDIA 底包已存在"
    progress 3 5 "rootfs 包已存在"
else
    section "下载 NVIDIA 官方包: ${VERSION}"
    echo "[PHASE] download"
    rel="${VERSION#R}"                            # 36.4.3
    rel_minor="${rel#*.}"                         # 4.3 (release 目录 vX.Y)
    # NVIDIA 统一了 JetPack 5/6/7 的下载路径: rXX_Release_vX.X + 文件名带 R
    release_dir="r${rel%%.*}_Release_v${rel_minor}"  # r36_Release_v4.3

    if (( DO_MINIMAL )); then
        warn "极简模式: 跳过 public_sources.tbz2 (备份/恢复不需要内核源码)"
    fi
    dl() { # name url
        local name
        local url
        local dest
        name="$1"
        url="$2"
        dest="${DOWNLOADS}/${VERSION}/${name}"
        if [[ -f "${dest}" ]]; then
            ok "已存在: ${name}"
            echo "[DOWNLOAD_DONE] ${name}"
            return
        fi
        echo "[DOWNLOAD_START] ${name}"
        curl --progress-bar -fL --retry 3 --retry-delay 5 \
            -o "${dest}.part" "${url}" 2>&1 >/dev/null \
          | tr '\r' '\n' \
          | awk -v n="${name}" '
              /[0-9]+(\.[0-9]+)?%/ {
                  match($0, /[0-9]+(\.[0-9]+)?%/);
                  p = substr($0, RSTART, RLENGTH);
                  if (p != last) { printf "[DOWNLOAD_PROGRESS] %s %s\n", n, p; last = p }
              }
            '
        mv "${dest}.part" "${dest}"
        echo "[DOWNLOAD_DONE] ${name}"
        ok "${name} 完成"
    }
    # 先统一报告本次要下载哪些文件
    download_list=""
    if (( ! DO_MINIMAL )); then
        download_list="${download_list}public_sources.tbz2;"
    fi
    download_list="${download_list}Jetson_Linux_R${rel}_aarch64.tbz2;Tegra_Linux_Sample-Root-Filesystem_R${rel}_aarch64.tbz2;"
    echo "[DOWNLOADS] ${download_list}"

    if (( ! DO_MINIMAL )); then
        dl "public_sources.tbz2" "https://developer.nvidia.com/downloads/embedded/l4t/${release_dir}/sources/public_sources.tbz2"
    fi
    # Jetson_Linux 与 rootfs 互不依赖，并发下载
    dl "Jetson_Linux_R${rel}_aarch64.tbz2" "https://developer.nvidia.com/downloads/embedded/l4t/${release_dir}/release/Jetson_Linux_R${rel}_aarch64.tbz2" &
    PID1=$!
    dl "Tegra_Linux_Sample-Root-Filesystem_R${rel}_aarch64.tbz2" "https://developer.nvidia.com/downloads/embedded/l4t/${release_dir}/release/Tegra_Linux_Sample-Root-Filesystem_R${rel}_aarch64.tbz2" &
    PID2=$!
    wait ${PID1}
    progress 2 5 "NVIDIA 底包就绪"
    wait ${PID2}
    progress 3 5 "rootfs 包就绪"
fi

# ---------- 3. 工具链 ----------
if (( DO_MINIMAL )); then
    warn "极简模式: 跳过工具链 (备份/恢复不需要交叉编译)"
else
    section "工具链"
    TC_TARGET="${TOOLCHAIN_DIR}/aarch64--glibc--stable-2022.08-1"
    if [[ -x "${TC_TARGET}/bin/aarch64-buildroot-linux-gnu-gcc" ]]; then
        ok "已存在: toolchain/${TC_TARGET##*/}"
    else
        TC_SRC="${DOWNLOADS}/${VERSION}/aarch64--glibc--stable-2022.08-1.tar.bz2"
        if [[ ! -f "${TC_SRC}" ]]; then
            TC_URL="${TOOLCHAIN_URL:-https://developer.nvidia.com/downloads/embedded/l4t/r36_release_v3.0/toolchain/aarch64--glibc--stable-2022.08-1.tar.bz2}"
            echo "下载工具链 ..."
            curl -fL --retry 3 -o "${TC_SRC}.part" "${TC_URL}"
            mv "${TC_SRC}.part" "${TC_SRC}"
        fi
        mkdir -p "${TOOLCHAIN_DIR}"
        tar -xjf "${TC_SRC}" -C "${TOOLCHAIN_DIR}/"
        ok "工具链就绪: ${TC_TARGET}"
    fi
fi

# ---------- 4. 内核源码 (Source/<ver>/kernel) ----------
if (( DO_MINIMAL )); then
    warn "极简模式: 跳过内核源码 (备份/恢复不需要)"
else
    section "内核源码"
    KSRC="${SOURCE_DIR}/${VERSION}/kernel"
    if [[ -f "${KSRC}/kernel-jammy-src/Makefile" ]]; then
        ok "已存在: ${KSRC}/kernel-jammy-src"
    else
        ARCHIVE="${DOWNLOADS}/${VERSION}/public_sources.tbz2"
        mkdir -p "${KSRC}"
        echo "解压 public_sources.tbz2 中的 kernel_src.tbz2 ..."
        tar -xjf "${ARCHIVE}" -C "${KSRC}" Linux_for_Tegra/source/kernel_src.tbz2
        tar -xjf "${KSRC}/Linux_for_Tegra/source/kernel_src.tbz2" -C "${KSRC}/"
        rm -rf "${KSRC}/Linux_for_Tegra"
        # kernel_src.tbz2 解出顶层可能是 kernel/ 或 kernel-jammy-src/
        if [[ -d "${KSRC}/kernel/kernel-jammy-src" ]]; then
            : # 已是 kernel/kernel-jammy-src 布局
        elif [[ -d "${KSRC}/kernel-jammy-src" ]]; then
            mv "${KSRC}/kernel-jammy-src" "${KSRC}/kernel/"
        fi
        ok "内核源码就绪: ${KSRC}"
    fi
fi

# ---------- 5. Seeed 仓库 (repos/Linux_for_Tegra) ----------
section "Seeed BSP 仓库"
BRANCH="${SEED_BRANCH:-${VERSION,,}}"
if [[ -d "${REPOS_DIR}/Linux_for_Tegra/.git" ]] && git -C "${REPOS_DIR}/Linux_for_Tegra" rev-parse --verify HEAD >/dev/null 2>&1; then
    ok "已存在: repos/Linux_for_Tegra"
    git -C "${REPOS_DIR}/Linux_for_Tegra" config http.proxy "${PROXY}" 2>/dev/null || true
else
    if [[ -d "${REPOS_DIR}/Linux_for_Tegra" ]] && [[ -z "$(ls -A "${REPOS_DIR}/Linux_for_Tegra" 2>/dev/null)" ]]; then
        rmdir "${REPOS_DIR}/Linux_for_Tegra"
    fi
    echo "克隆 Seeed-Studio/Linux_for_Tegra (分支 ${BRANCH}) ..."
    git_clone() {
        git clone --depth=1 --filter=blob:none -b "${BRANCH}" \
            https://github.com/Seeed-Studio/Linux_for_Tegra.git "$1"
    }
    if [[ -n "${PROXY}" ]] && ! git_clone "${REPOS_DIR}/Linux_for_Tegra" 2>/dev/null; then
        echo "直连失败，走代理 ..."
        git -c http.proxy="${PROXY}" clone --depth=1 --filter=blob:none -b "${BRANCH}" \
            https://github.com/Seeed-Studio/Linux_for_Tegra.git "${REPOS_DIR}/Linux_for_Tegra"
    elif [[ -z "${PROXY}" ]]; then
        git_clone "${REPOS_DIR}/Linux_for_Tegra"
    fi
    git -C "${REPOS_DIR}/Linux_for_Tegra" config http.proxy "${PROXY}" 2>/dev/null || true
    ok "Seeed 仓库就绪"
fi
progress 1 5 "BSP 仓库就绪"

# ---------- 6. 备份/恢复工作树 (bsp/<ver>/Linux_for_Tegra) ----------
section "备份/恢复工作树 bsp/${VERSION}/Linux_for_Tegra"
BSP_TREE="${BSP_DIR}/${VERSION}/Linux_for_Tegra"
rel="${VERSION#R}"   # 解压段也要用 (下载段可能被 --skip-download 跳过)
if [[ -f "${BSP_TREE}/flash.sh" ]]; then
    ok "已存在: ${BSP_TREE}"
    echo "[PHASE] assemble"
    echo "[PHASE] rootfs"
    # 树存在不代表就绪: 校验 rootfs 是否真的解压过 (曾出现 flash.sh
    # 已在而 rootfs 为空, UI 仍显示"环境就绪"的假成功)。缺失则补解压。
    if [[ ! -f "${BSP_TREE}/rootfs/etc/os-release" ]] || [[ ! -d "${BSP_TREE}/rootfs/bin" ]]; then
        warn "检测到 rootfs 未解压完整, 补解压 rootfs ..."
        if [[ ! -f "${DOWNLOADS}/${VERSION}/Tegra_Linux_Sample-Root-Filesystem_R${rel}_aarch64.tbz2" ]]; then
            die "rootfs 包缺失: ${DOWNLOADS}/${VERSION}/Tegra_Linux_Sample-Root-Filesystem_R${rel}_aarch64.tbz2 (请先完整下载)"
        fi
        sudorun mkdir -p "${BSP_TREE}/rootfs"
        sudorun tar -xpf "${DOWNLOADS}/${VERSION}/Tegra_Linux_Sample-Root-Filesystem_R${rel}_aarch64.tbz2" -C "${BSP_TREE}/rootfs/"
        ( cd "${BSP_TREE}" && sudorun -E ./apply_binaries.sh )
        ok "rootfs 补解压完成"
    fi
else
    echo "[PHASE] assemble"
    L4T_BASE="${DOWNLOADS}/${VERSION}/Linux_for_Tegra"
    if [[ ! -f "${L4T_BASE}/flash.sh" ]]; then
        echo "解压 NVIDIA 底包 ..."
        mkdir -p "${DOWNLOADS}/${VERSION}/l4t_tmp"
        tar -xjf "${DOWNLOADS}/${VERSION}/Jetson_Linux_R${rel}_aarch64.tbz2" -C "${DOWNLOADS}/${VERSION}/l4t_tmp/"
        mv "${DOWNLOADS}/${VERSION}/l4t_tmp/Linux_for_Tegra" "${L4T_BASE}"
        rmdir "${DOWNLOADS}/${VERSION}/l4t_tmp"
        ok "NVIDIA 底包: ${L4T_BASE}"
    fi
    echo "覆盖 Seeed 配置 ..."
    mkdir -p "${BSP_TREE}"
    shopt -s dotglob
    cp -a "${L4T_BASE}/". "${BSP_TREE}/"
    cp -a "${REPOS_DIR}/Linux_for_Tegra/". "${BSP_TREE}/"
    shopt -u dotglob
    # 备份/恢复依赖 NVIDIA 官方 tools/backup_restore/l4t_backup_restore.sh，
    # Seeed 仓库可能不带该目录，所以覆盖后显式恢复。
    if [[ -x "${L4T_BASE}/tools/backup_restore/l4t_backup_restore.sh" ]]; then
        cp -a "${L4T_BASE}/tools/backup_restore" "${BSP_TREE}/tools/"
        ok "恢复 backup_restore 工具: ${BSP_TREE}/tools/backup_restore"
    fi
    # 同时把 Seeed 备份/恢复 wrapper 脚本拷入树内，方便用户直接在 L4T 树下使用
    WRAPPER_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/jetson-backup-restore.sh"
    if [[ -f "${WRAPPER_SRC}" ]]; then
        cp -a "${WRAPPER_SRC}" "${BSP_TREE}/tools/backup_restore/"
        ok "拷入 wrapper 脚本: ${BSP_TREE}/tools/backup_restore/jetson-backup-restore.sh"
    fi
    echo "[PHASE] rootfs"
    echo "解压 rootfs ..."
    sudorun tar -xpf "${DOWNLOADS}/${VERSION}/Tegra_Linux_Sample-Root-Filesystem_R${rel}_aarch64.tbz2" -C "${BSP_TREE}/rootfs/"
    echo "运行 apply_binaries.sh ..."
    cd "${BSP_TREE}"
    sudorun -E ./apply_binaries.sh
    cd "${WORKSPACE}"
    progress 4 5 "备份/恢复工作树就绪"
    ok "备份/恢复工作树就绪: ${BSP_TREE}"
fi

# ---------- 6.5 确保 Seeed conf/DTB 覆盖在树内 (repos 为权威源, 缺则补齐) ----------
# 树只承担恢复引导 (DTB) 与板型发现 (conf); 业务驱动在设备系统备份镜像里,
# 不需要也不应整体拷入工作树。故这里仅幂等补齐 conf + 引导 DTB。
mkdir -p "${BSP_TREE}/kernel/dtb"
SEEED_CONF_BEFORE=$(ls "${BSP_TREE}"/recomputer-*.conf 2>/dev/null | wc -l)
for f in "${REPOS_DIR}/Linux_for_Tegra"/*.conf; do
    [ -f "${f}" ] || continue
    [[ -f "${BSP_TREE}/$(basename "${f}")" ]] || cp -n "${f}" "${BSP_TREE}/"
done
for f in "${REPOS_DIR}/Linux_for_Tegra"/kernel/dtb/*recomputer*.dtb \
         "${REPOS_DIR}/Linux_for_Tegra"/kernel/dtb/*j401*.dtb; do
    [ -f "${f}" ] || continue
    [[ -f "${BSP_TREE}/kernel/dtb/$(basename "${f}")" ]] || cp -n "${f}" "${BSP_TREE}/kernel/dtb/"
done
SEEED_CONF_AFTER=$(ls "${BSP_TREE}"/recomputer-*.conf 2>/dev/null | wc -l)
if [ "${SEEED_CONF_AFTER}" -gt "${SEEED_CONF_BEFORE}" ]; then
    ok "Seeed conf/DTB 已补齐 (recomputer-*/reserver-*)"
fi

# ---------- 6.6 确保 rootfs/dev 设备节点完整 (缺则 initrd SSH pty 失败) ----------
# 曾出现: tar 解压的 rootfs /dev 只有假 null, 缺 pts/ptmx/console, 设备端
# "Failed to get a pseudo terminal: No such device" → 备份/恢复执行不了。
sudorun bash -c "
set -e
D='${BSP_TREE}/rootfs/dev'
mkdir -p \"\$D/pts\" \"\$D/shm\" \"\$D/mqueue\"
# name major minor mode
for row in 'console 5 1 600' 'null 1 3 666' 'zero 1 5 666' 'full 1 7 666' \
           'random 1 8 666' 'urandom 1 9 666' 'tty 5 0 666' 'ptmx 5 2 666'; do
    set -- \$row
    name=\$1; maj=\$2; min=\$3; mode=\$4
    d=\"\$D/\$name\"
    if [ -L \"\$d\" ] || [ ! -e \"\$d\" ] || [ ! -c \"\$d\" ]; then
        rm -f \"\$d\"
        mknod \"\$d\" c \"\$maj\" \"\$min\"
        chmod \"\$mode\" \"\$d\"
    fi
done
" 2>/dev/null || warn "rootfs/dev 设备节点补齐失败(不影响已在盘上的树)"
ok "rootfs/dev 设备节点已校验"

# ---------- 7. 兼容软链接 ----------
section "兼容软链接"
if [[ ! -e "${DOWNLOADS}/${VERSION}/Linux_for_Tegra" ]]; then
    ln -s "${REPOS_DIR}/Linux_for_Tegra" "${DOWNLOADS}/${VERSION}/Linux_for_Tegra"
    ok "Downloads/${VERSION}/Linux_for_Tegra -> repos/"
fi
if [[ ! -e "${WORKSPACE}/Linux_for_Tegra" ]]; then
    ln -s "${REPOS_DIR}/Linux_for_Tegra" "${WORKSPACE}/Linux_for_Tegra"
    ok "bsp-workspace/Linux_for_Tegra -> repos/"
fi

progress 5 5 "工作区准备完成"
echo "[PHASE] done"
echo
section "完成"
echo "  工作区:   ${WORKSPACE}"
echo "  Seeed:    ${REPOS_DIR}/Linux_for_Tegra  (分支 ${BRANCH})"
echo "  工作树:   ${BSP_TREE}"
echo "  内核源码: ${KSRC:-未下载 (极简模式)}"
echo
echo "下一步:"
echo "  cd ${WORKSPACE}"
echo "  ./jetson-bsp-workflow.sh query iptable_raw"