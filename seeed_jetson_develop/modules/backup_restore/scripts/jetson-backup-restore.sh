#!/usr/bin/env bash
# jetson-backup-restore.sh — Seeed reComputer / reServer 全机型备份与恢复
# =============================================================================
# 包装官方 l4t_backup_restore.sh, 自动发现板型 conf (全机型, 无需硬编码白名单),
# 并固化实战踩坑修复:
#   - NFS mountd/rpc-statd 预检 (R39 上 mountd 未注册会导致设备 mount 卡死)
#   - 磁盘空间预检 (备份 rootfs tar.zst 可达 18G+, Summary: 100% 满盘会中断)
#   - 备份完成后逐项 sha256 校验 nvpartitionmap.txt
#
# 用法:
#   ./jetson-backup-restore.sh -l | --list                 # 列出全部可用板型
#   ./jetson-backup-restore.sh -b <board> [--wait-apx]     # 备份
#   ./jetson-backup-restore.sh -r <board> [--wait-apx]     # 恢复(覆盖目标盘)
#   ./jetson-backup-restore.sh -h                          # 帮助
#
# 环境变量:
#   L4T_DIR           host 树根 (默认自动找 bsp/*_build/Linux_for_Tegra)
#   EXTERNAL_DEVICE   备份/恢复目标设备 (默认 nvme0n1)
#   BAUDRATE          未用(保留兼容)
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSD_ROOT="$(dirname "${SCRIPT_DIR}")"

# ---- 着色 ----
C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_CYAN=$'\033[36m'; C_RESET=$'\033[0m'
ok()   { printf '%s✓%s %s\n' "${C_GREEN}" "${C_RESET}" "$1"; }
warn() { printf '%s!%s %s\n' "${C_YELLOW}" "${C_RESET}" "$1"; }
err()  { printf '%s✗%s %s\n' "${C_RED}" "${C_RESET}" "$1"; }
info() { printf '%s·%s %s\n' "${C_CYAN}" "${C_RESET}" "$1"; }
die()  { err "$1"; exit 1; }

sudorun() {
    # 用本地固定 sudo 密码执行 (环境无交互); 无密码则走普通 sudo
    if [ -n "${SUDO_PASS:-}" ]; then
        echo "${SUDO_PASS}" | sudo -S -p '' "$@"
    else
        sudo "$@"
    fi
}

# ---- 默认参数 ----
EXTERNAL_DEVICE="${EXTERNAL_DEVICE:-nvme0n1}"
MODE=""
BOARD=""
WAIT_APX=0
SOURCE_DIR=""
L4T_DIR="${L4T_DIR:-}"

# ---- 自动定位 L4T_DIR ----
auto_l4t_dir() {
    local cand root
    # 1) 原始布局: 脚本所在盘的 bsp 构建树 (向后兼容)
    for cand in \
        "${SSD_ROOT}/bsp/R39.2.0_build/Linux_for_Tegra" \
        "${SSD_ROOT}"/bsp/*_build/Linux_for_Tegra; do
        [ -d "${cand}" ] && [ -x "${cand}/tools/backup_restore/l4t_backup_restore.sh" ] \
            && { echo "${cand}"; return; }
    done
    # 2) 常见主机位置: 挂载盘与用户主目录 (适配打包进 DevTool 后的位置)
    for root in /media/* /media/*/* "${HOME}"; do
        [ -d "${root}" ] || continue
        # shellcheck disable=SC2086
        for cand in "${root}"/bsp/*_build/Linux_for_Tegra \
                    "${root}"/bsp/*/Linux_for_Tegra; do
            [ -d "${cand}" ] && [ -x "${cand}/tools/backup_restore/l4t_backup_restore.sh" ] \
                && { echo "${cand}"; return; }
        done
    done
    return 1
}

usage() {
    cat <<EOF
用法:
  $(basename "$0") -l | --list                  列出全部可用板型 (从 conf 动态发现)
  $(basename "$0") -b <board> [--wait-apx]      备份 (设备进 Recovery 后执行)
  $(basename "$0") -r <board> [--wait-apx]      恢复/覆盖 (目标盘将被覆盖!)
  $(basename "$0") -h                           帮助

选项:
  -b <board>   备份: 调用 l4t_backup_restore.sh -e <dev> -b <board>
  -r <board>   恢复: 调用 l4t_backup_restore.sh -e <dev> -r <board>
  --wait-apx   先轮询 lsusb 等待设备进入 Recovery (Orin NX 16GB=0955:7323,
               NX 8GB=7423, Nano 8GB=7523, Nano 4GB=7623, AGX=7023)
  -l --list    仅列出板型后退出
  -h           帮助

环境变量:
  L4T_DIR           host 树根 (默认自动探测)
  EXTERNAL_DEVICE   备份/恢复目标设备 (默认 nvme0n1)
  SUDO_PASS         sudo 密码 (可选, 无则用普通 sudo)

示例:
  ./$(basename "$0") -l
  ./$(basename "$0") -b reserver-industrial-orin-j401 --wait-apx
  ./$(basename "$0") -r recomputer-orin-j401
EOF
}

# ---- 动态板型发现: 扫描 host 树 *.conf ----
discover_boards() {
    local dir="${1}"
    local f
    for f in "${dir}"/*.conf; do
        [ -f "${f}" ] || continue
        case "$(basename "${f}")" in
            recomputer-*|reserver-*|seeed-*) echo "$(basename "${f}" .conf)" ;;
        esac
    done | sort -u
}

# ---- 预检: NFS mountd/rpc-statd (R39 常挂) ----
ensure_nfs_services() {
    info "预检 NFS 服务 (mountd/rpc-statd/nfs-server)..."
    # 服务在 Ubuntu 上可能起过但 mountd 未注册, 显式拉起
    if command -v systemctl >/dev/null 2>&1; then
        sudorun systemctl start nfs-mountd 2>/dev/null || warn "nfs-mountd 启动失败"
        sudorun systemctl start rpc-statd 2>/dev/null || true
        # 只起 mountd 不够: 必须 nfs-server (nfsd) 起来, 否则设备 NFS 挂载被拒
        nfs_svc=$(systemctl list-unit-files 2>/dev/null | awk '$1 ~ /^nfs-(server|kernel-server)\.service$/ {print $1; exit}')
        if [ -n "${nfs_svc}" ]; then
            sudorun systemctl start "${nfs_svc}" 2>/dev/null || warn "nfs-server 启动失败"
        else
            sudorun sh -c 'service nfs-kernel-server start' 2>/dev/null || warn "nfs-kernel-server 启动失败"
        fi
        sudorun exportfs -ra 2>/dev/null || true
        sleep 1
    fi
    if rpcinfo -p 2>/dev/null | grep -qE '\s100005\s'; then
        ok "mountd 已注册 (rpcinfo 100005)"
    else
        warn "rpcinfo 未见 mountd; 备份引导时设备 mount 可能超时"
        warn "本次会话若卡 'Waiting for target to boot-up', 可 Ctrl-C 后重跑本脚本"
    fi
    if rpcinfo -p 2>/dev/null | grep -qE '\s100003\s'; then
        ok "nfsd 已注册 (rpcinfo 100003)"
    else
        die "NFS server 不可用 (nfsd 未注册) — 设备无法挂载备份目录。请先: sudo systemctl enable --now nfs-kernel-server"
    fi
}

# ---- 预检: 磁盘空间 (rootfs tar 可达 18G+) ----
check_disk() {
    local avail_kb free_gb
    avail_kb=$(df -Pk "${L4T_DIR}" | awk 'NR==2{print $4}')
    free_gb=$(( avail_kb / 1024 / 1024 ))
    if [ "${free_gb}" -lt 25 ]; then
        warn "SSD 剩余仅 ${free_gb}G。备份 rootfs tar.zst 可能达 18G+, 建议 >=25G 空闲"
        if [ "${free_gb}" -lt 8 ]; then
            die "磁盘空间不足 (<8G), 请先清理 (如删除 Downloads/*.tbz2) 再备份"
        fi
    else
        ok "磁盘剩余 ${free_gb}G"
    fi
}

# ---- 等待 APX ----
wait_apx() {
    local apx_ids=("7323" "7423" "7523" "7623" "7023")
    local found=0 i id
    info "等待设备进入 Recovery (APX) 模式..."
    for i in $(seq 1 60); do
        for id in "${apx_ids[@]}"; do
            if lsusb -d "0955:${id}" >/dev/null 2>&1; then
                ok "检测到 APX: 0955:${id}"
                found=1
                break 2
            fi
        done
        printf '.'
        sleep 2
    done
    echo
    [ "${found}" -eq 1 ] || die "超时未检测到 APX, 请确认设备已进 Recovery (FC REC + GND 跳线)"
}

# ---- 备份后校验 sha256 ----
verify_checksums() {
    local img_dir="${1}"
    local map="${img_dir}/nvpartitionmap.txt"
    [ -f "${map}" ] || { warn "无 nvpartitionmap.txt, 跳过校验"; return; }
    info "校验镜像 sha256 (对照 nvpartitionmap.txt)..."
    local bad=0 n=0 f rest sha mapsha
    # 计数器必须在主 shell 累加: 子 shell 里自增退出即丢 (曾导致 "全部 0 个镜像校验通过")
    pushd "${img_dir}" >/dev/null || return 1
    while IFS=, read -r f rest; do
        case "${f}" in board_spec|"") continue ;; esac
        [ -f "${f}" ] || { err "缺文件 ${f}"; bad=$((bad+1)); continue; }
        sha=$(sha256sum "${f}" | awk '{print $1}')
        mapsha=$(echo "${rest}" | awk -F, '{print $NF}')
        n=$((n+1))
        if [ "${sha}" = "${mapsha}" ]; then ok "${f}"; else err "校验不一致 ${f}"; bad=$((bad+1)); fi
    done < "${map}"
    popd >/dev/null
    echo
    if [ "${bad}" -eq 0 ]; then ok "全部 ${n} 个镜像校验通过"; else warn "${bad}/${n} 个异常"; fi
}

# ---- 解析参数 ----
while [ "$#" -gt 0 ]; do
    case "$1" in
        -b) MODE="backup"; BOARD="${2:-}"; shift 2 ;;
        -r) MODE="restore"; BOARD="${2:-}"; shift 2 ;;
        --source) SOURCE_DIR="${2:-}"; shift 2 ;;
        -l|--list) MODE="list"; shift ;;
        --wait-apx) WAIT_APX=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) err "未知参数: $1"; usage; exit 2 ;;
    esac
done

[ -n "${MODE}" ] || { usage; exit 2; }

# ---- 定位 L4T_DIR ----
if [ -z "${L4T_DIR}" ]; then
    L4T_DIR="$(auto_l4t_dir)" || die "未找到 Linux_for_Tegra 树, 请设 L4T_DIR 或用 build-plus-package.sh 先装配"
fi
[ -d "${L4T_DIR}" ] || die "L4T_DIR 不存在: ${L4T_DIR}"
[ -x "${L4T_DIR}/tools/backup_restore/l4t_backup_restore.sh" ] \
    || die "backup_restore 工具缺失: ${L4T_DIR}/tools/backup_restore/l4t_backup_restore.sh"

# ---- list 模式 ----
if [ "${MODE}" = "list" ]; then
    echo "可用板型 (来自 ${L4T_DIR}/*.conf):"
    discover_boards "${L4T_DIR}" | sed 's/^/  - /'
    exit 0
fi

# ---- 校验板型 ----
BOARDS="$(discover_boards "${L4T_DIR}")"
if ! grep -qx "${BOARD}" <<<"${BOARDS}"; then
    err "板型 '${BOARD}' 不在 conf 列表:"
    sed 's/^/    /' <<<"${BOARDS}"
    exit 2
fi
[ -f "${L4T_DIR}/${BOARD}.conf" ] || die "conf 缺失: ${L4T_DIR}/${BOARD}.conf"

# ---- 执行 ----
info "L4T_DIR        : ${L4T_DIR}"
info "BOARD          : ${BOARD}"
info "EXTERNAL_DEVICE: ${EXTERNAL_DEVICE}"

if [ "${WAIT_APX}" -eq 1 ]; then
    wait_apx
fi

check_disk
# ---- 预检: host pty (sshpass 依赖 /dev/ptmx; flash/chroot 类操作可能把 /dev/pts 挂坏) ----
# 症状: sshpass 报 "Failed to get a pseudo terminal: No such device" 但设备 ssh 已通
if [ ! -e /dev/pts/ptmx ]; then
    die "host /dev/pts 损坏 (无 /dev/pts/ptmx), sshpass 无法工作。修复: sudo mount -t devpts devpts /dev/pts -o gid=5,mode=620,ptmxmode=0666"
fi
ensure_nfs_services

# ---- 归档 images 根的现有备份集 (同盘 mv, 零拷贝零空间) ----
# 必须在下一次备份前做: 设备写镜像用就地截断 (dd of=/tar 重定向), 不归档会覆盖旧套。
archive_root_set() {
    local map="${IMAGES_DIR}/nvpartitionmap.txt"
    [ -f "${map}" ] || return 0
    local spec board="" b ts dest
    spec=$(sed -n 's/^board_spec,//p' "${map}" | head -1)
    for b in ${BOARDS}; do
        if [ -n "${b}" ] && grep -q "${b}" <<<"${spec}"; then board="${b}"; break; fi
    done
    board="${board:-unknown}"
    ts=$(date +%Y%m%d-%H%M%S)
    dest="${IMAGES_DIR}/${board}_${ts}"
    sudorun mkdir -p "${dest}"
    # 只移根层文件, 不动已有归档子目录
    find "${IMAGES_DIR}" -maxdepth 1 -type f -exec mv -f {} "${dest}/" \;
    ok "上次备份已归档 → ${board}_${ts}"
}

IMAGES_DIR="${L4T_DIR}/tools/backup_restore/images"
case "${MODE}" in
    backup)
        info "开始备份 ${BOARD} → ${IMAGES_DIR}"
        sudorun mkdir -p "${IMAGES_DIR}" 2>/dev/null || true
        archive_root_set
        ( cd "${L4T_DIR}" && sudorun ./tools/backup_restore/l4t_backup_restore.sh -e "${EXTERNAL_DEVICE}" -b "${BOARD}" )
        rc=$?
        echo
        if [ "${rc}" -ne 0 ]; then
            die "备份失败 (exit=${rc}), 设备侧命令未执行完成, 请查看上方日志后重试"
        fi
        # 完成标志: nvpartitionmap.txt + 至少一个镜像文件 (官方脚本只在全部完成后写 map)
        local_map="${IMAGES_DIR}/nvpartitionmap.txt"
        n_imgs=$(find "${IMAGES_DIR}" -maxdepth 1 -type f ! -name nvpartitionmap.txt 2>/dev/null | wc -l)
        if [ -f "${local_map}" ] && [ "${n_imgs}" -gt 0 ]; then
            ok "备份产物: ${IMAGES_DIR} (${n_imgs} 个镜像)"
            du -sh "${IMAGES_DIR}"
            verify_checksums "${IMAGES_DIR}"
        else
            die "备份未完成: 缺少 nvpartitionmap.txt 或镜像文件 (共 ${n_imgs} 个产物), 请查看上方日志后重试"
        fi
        ;;
    restore)
        [ -d "${IMAGES_DIR}" ] || die "恢复源不存在: ${IMAGES_DIR} (先备份)"
        # 允许选择历史备份集: --source <dir> 为一套含 nvpartitionmap.txt 的镜像目录,
        # 将其内容同步到标准 images 目录后再恢复 (恢复前覆盖设备, 覆盖 images 无副作用)
        if [ -n "${SOURCE_DIR}" ]; then
            [ -d "${SOURCE_DIR}" ] || die "备份集不存在: ${SOURCE_DIR}"
            [ -f "${SOURCE_DIR}/nvpartitionmap.txt" ] \
                || die "所选目录不是有效备份集 (缺 nvpartitionmap.txt): ${SOURCE_DIR}"
            info "使用备份集: ${SOURCE_DIR}"
            # 若 images 根还有未归档的新备份, 先归档 (会被下面的同步覆盖)
            archive_root_set
            # 真拷贝 (不能用 cp -al 硬链接): 归档与 images 根共享 inode 的话,
            # 下次备份就地截断根文件会把归档一起写坏
            sudorun cp -a "${SOURCE_DIR}/." "${IMAGES_DIR}/"
            sudorun chmod -R a+rX "${IMAGES_DIR}"
        fi
        info "警告: 目标盘将被覆盖, 设备须进 Recovery"
        ( cd "${L4T_DIR}" && sudorun ./tools/backup_restore/l4t_backup_restore.sh -e "${EXTERNAL_DEVICE}" -r "${BOARD}" )
        rc=$?
        echo
        if [ "${rc}" -ne 0 ]; then
            die "恢复失败 (exit=${rc}), 设备未恢复完成, 请查看上方日志后重试"
        fi
        ok "恢复流程结束。可断电重启设备验证启动"
        ;;
esac