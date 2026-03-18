"""
固件刷写模块
"""
import json
import os
import subprocess
import hashlib
import time
from pathlib import Path
import requests
from tqdm import tqdm


def sudo_authenticate(password: str) -> bool:
    """用给定密码刷新 sudo 凭证。返回 True 表示密码正确且 sudo 已授权。"""
    try:
        result = subprocess.run(
            ["sudo", "-S", "-v"],
            input=password + "\n",
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def sudo_check_cached() -> bool:
    """检查 sudo 凭证是否仍在缓存期内（无需密码）。"""
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


class JetsonFlasher:
    def __init__(self, product, l4t_version, progress_callback=None, should_cancel=None):
        self.product = product
        self.l4t_version = l4t_version
        self.progress_callback = progress_callback
        self.should_cancel = should_cancel
        self.data_path = Path(__file__).parent / "data" / "l4t_data.json"
        self.firmware_info = self._load_firmware_info()
        self.download_dir = Path.home() / "jetson_firmware"
        self.download_dir.mkdir(exist_ok=True)
    
    def _load_firmware_info(self):
        """加载固件信息"""
        with open(self.data_path, 'r') as f:
            data = json.load(f)
        
        for item in data:
            if item['product'] == self.product and item['l4t'] == self.l4t_version:
                return item
        
        raise ValueError(f"未找到 {self.product} L4T {self.l4t_version} 的固件信息")

    @staticmethod
    def _with_download_flag(url):
        """为 SharePoint 分享链接追加 download=1 参数。"""
        if not url:
            return None
        lower = url.lower()
        if ("sharepoint.com" not in lower and "sharepoint.cn" not in lower) or "download=" in lower:
            return url
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}download=1"

    @staticmethod
    def _looks_like_html(content_type, first_chunk):
        content_type = (content_type or "").lower()
        first = (first_chunk or b"").lstrip().lower()
        if "text/html" in content_type or "application/xhtml" in content_type:
            return True
        return first.startswith(b"<!doctype html") or first.startswith(b"<html")

    def _candidate_urls(self):
        """生成可尝试的下载地址（主链路 + 镜像 + download=1 变体）。"""
        urls = []
        for raw in [self.firmware_info.get("mainlink"), self.firmware_info.get("mirrorlink")]:
            if not raw:
                continue
            for url in [raw, self._with_download_flag(raw)]:
                if url and url not in urls:
                    urls.append(url)
        return urls

    def _emit_progress(self, stage, current, total):
        """向外部回调进度信息。"""
        if not self.progress_callback:
            return
        try:
            self.progress_callback(stage, current, total)
        except Exception:
            # GUI 回调失败不应中断下载流程
            pass

    def _check_cancel(self):
        if self.should_cancel and self.should_cancel():
            raise InterruptedError("cancel requested")

    def _run_cancelable_process(self, args, cwd=None):
        """运行可取消的子进程，实时输出每行日志。"""
        self._check_cancel()
        process = subprocess.Popen(
            args, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        try:
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    print(line)
                    self._emit_log(line)
                self._check_cancel()
            process.wait()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, args)
        except InterruptedError:
            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                process.kill()
            raise

    def _emit_log(self, line: str):
        """向外部回调发送日志行。"""
        if self.progress_callback:
            try:
                self.progress_callback("log", line, 0)
            except Exception:
                pass

    def _download_from_url(self, url, filepath, filename):
        """从指定 URL 下载到目标文件，支持断点续传。"""
        self._check_cancel()
        tmp_path = filepath.with_suffix(filepath.suffix + ".part")

        # 已下载的字节数（断点续传起点）
        resume_pos = tmp_path.stat().st_size if tmp_path.exists() else 0

        headers = {}
        if resume_pos > 0:
            headers["Range"] = f"bytes={resume_pos}-"
            print(f"断点续传: 从 {resume_pos} 字节继续")

        response = requests.get(url, stream=True, timeout=(15, 600),
                                allow_redirects=True, headers=headers)

        # 服务器不支持 Range 时返回 200，需要重头下载
        if resume_pos > 0 and response.status_code == 200:
            print("服务器不支持断点续传，重新下载")
            resume_pos = 0
            tmp_path.unlink(missing_ok=True)

        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        if total_size and resume_pos:
            total_size += resume_pos  # content-length 是剩余长度，换算为总长度

        content_type = response.headers.get("content-type", "")
        chunks = response.iter_content(chunk_size=65536)

        # 验证首个 chunk 不是 HTML（仅首次下载时检查）
        first_chunk = b""
        for chunk in chunks:
            if chunk:
                first_chunk = chunk
                break

        if not first_chunk:
            raise ValueError("下载内容为空")

        if resume_pos == 0 and self._looks_like_html(content_type, first_chunk):
            raise ValueError("下载链接返回网页内容，非固件文件")

        written = resume_pos + len(first_chunk)
        open_mode = "ab" if resume_pos > 0 else "wb"

        with open(tmp_path, open_mode) as f, tqdm(
            desc=filename,
            initial=resume_pos,
            total=total_size if total_size > 0 else None,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            self._check_cancel()
            f.write(first_chunk)
            pbar.update(len(first_chunk))
            self._emit_progress("download", written, total_size)
            for chunk in chunks:
                if chunk:
                    self._check_cancel()
                    f.write(chunk)
                    written += len(chunk)
                    pbar.update(len(chunk))
                    self._emit_progress("download", written, total_size)

        if written < 1024 * 1024:
            raise ValueError(f"下载文件异常偏小: {written} bytes")

        tmp_path.replace(filepath)
    
    def firmware_cached(self) -> bool:
        """检查固件压缩包是否已缓存（文件存在且大小正常）。"""
        filepath = self.download_dir / self.firmware_info['filename']
        return filepath.exists() and filepath.stat().st_size > 1024 * 1024

    def firmware_extracted(self) -> bool:
        """检查当前产品的固件是否已解压。
        匹配优先级：精确匹配 > foldername 前缀匹配 > 产品系列关键词匹配。
        """
        extract_dir = self.download_dir / "extracted"
        if not extract_dir.exists():
            return False
        try:
            subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
        except Exception:
            return False
        if not subdirs:
            return False

        foldername = self.firmware_info.get('foldername', '')
        if foldername:
            # 精确匹配
            if (extract_dir / foldername).is_dir():
                return True
            # 前缀匹配
            if any(d.name.startswith(foldername) for d in subdirs):
                return True

        # 产品系列关键词兜底：从 filename 提取系列特征词，避免跨产品误判
        # 例如 reserver 包的目录含 "reserver"，classic 包含 "recomputer-orin" 但不含 "reserver"
        filename = self.firmware_info.get('filename', '')
        series_keywords = []
        if 'reserver' in filename:
            series_keywords = ['reserver']
        elif 'recomputer-super' in filename or 'super' in filename:
            series_keywords = ['recomputer-super', 'recomputer-orin-super']
        elif 'recomputer-robo' in filename or 'robo' in filename:
            series_keywords = ['recomputer-robo']
        elif 'recomputer-industrial' in filename or 'industrial' in filename:
            series_keywords = ['recomputer-industrial']
        elif 'recomputer-mini' in filename or 'mini' in filename:
            series_keywords = ['recomputer-orin-j40mini', 'recomputer-orin-j30mini']
        elif 'recomputer' in filename:
            series_keywords = ['recomputer-orin']

        if series_keywords:
            for d in subdirs:
                if any(kw in d.name for kw in series_keywords):
                    return True

        return False

    def clear_cache(self, clear_archive=True, clear_extracted=True):
        """清除本地缓存。返回 (删了哪些路径) 列表。"""
        import shutil
        removed = []
        if clear_archive:
            filepath = self.download_dir / self.firmware_info['filename']
            if filepath.exists():
                filepath.unlink()
                removed.append(str(filepath))
            part = filepath.with_suffix(filepath.suffix + ".part")
            if part.exists():
                part.unlink()
                removed.append(str(part))
        if clear_extracted:
            extract_dir = self.download_dir / "extracted"
            actual = self._detect_extracted_dir(extract_dir)
            if actual and actual.exists():
                shutil.rmtree(actual)
                removed.append(str(actual))
        return removed

    def download_firmware(self, force_redownload: bool = False):
        """下载固件。force_redownload=True 时忽略缓存强制重新下载。"""
        filename = self.firmware_info['filename']
        filepath = self.download_dir / filename

        if not force_redownload and filepath.exists():
            size = filepath.stat().st_size
            if size > 1024 * 1024:
                print(f"固件已存在: {filepath}")
                return True
            print(f"检测到已有文件异常偏小({size} bytes)，将重新下载: {filepath}")
            filepath.unlink()

        if force_redownload and filepath.exists():
            print(f"强制重新下载，删除缓存: {filepath}")
            filepath.unlink()
            part_path = filepath.with_suffix(filepath.suffix + ".part")
            if part_path.exists():
                part_path.unlink()
        
        print(f"正在下载固件: {filename}")
        urls = self._candidate_urls()

        last_error = None
        for idx, url in enumerate(urls, start=1):
            print(f"下载链接({idx}/{len(urls)}): {url}")
            self._emit_progress("download", 0, 0)
            try:
                self._download_from_url(url, filepath, filename)
                print(f"下载完成: {filepath}")
                return True
            except InterruptedError:
                raise
            except Exception as e:
                last_error = e
                print(f"当前链接下载失败: {e}")
                # 保留 .part 文件，下次可断点续传

        print(f"下载失败: {last_error}")
        return False
    
    def verify_firmware(self):
        """校验固件 SHA256"""
        self._check_cancel()
        filename = self.firmware_info['filename']
        filepath = self.download_dir / filename
        expected_sha256 = self.firmware_info['sha256'].lower()
        
        print(f"正在校验固件: {filename}")
        
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                self._check_cancel()
                sha256_hash.update(byte_block)
        
        actual_sha256 = sha256_hash.hexdigest().lower()
        
        if actual_sha256 == expected_sha256:
            print("✓ SHA256 校验通过")
            return True
        else:
            print(f"✗ SHA256 校验失败")
            print(f"  期望: {expected_sha256}")
            print(f"  实际: {actual_sha256}")
            return False
    
    def _detect_extracted_dir(self, extract_dir: Path) -> Path | None:
        """探测解压后的实际顶层目录，优先匹配 foldername，否则取唯一子目录。"""
        foldername = self.firmware_info.get('foldername', '')
        # 优先：精确匹配
        candidate = extract_dir / foldername
        if candidate.is_dir():
            return candidate
        # 次选：前缀匹配（foldername 可能只是前缀）
        if foldername:
            matches = [d for d in extract_dir.iterdir() if d.is_dir() and d.name.startswith(foldername)]
            if len(matches) == 1:
                return matches[0]
        # 兜底：唯一子目录
        subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
        if len(subdirs) == 1:
            return subdirs[0]
        return None

    def extract_firmware(self):
        """解压固件"""
        self._check_cancel()
        filename = self.firmware_info['filename']
        filepath = self.download_dir / filename
        extract_dir = self.download_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)
        
        print(f"正在解压固件: {filename}")
        
        try:
            if filename.endswith('.tar.gz'):
                args = ["tar", "-xzf", str(filepath), "-C", str(extract_dir)]
            elif filename.endswith('.tar'):
                args = ["tar", "-xf", str(filepath), "-C", str(extract_dir)]
            else:
                print(f"不支持的文件格式: {filename}")
                return False
            
            self._run_cancelable_process(args)

            actual_dir = self._detect_extracted_dir(extract_dir)
            if actual_dir:
                self._extracted_dir = actual_dir
                print(f"解压完成: {actual_dir}")
            else:
                print(f"解压完成，但无法确定顶层目录: {extract_dir}")
                self._extracted_dir = None
            return True
        
        except InterruptedError:
            raise
        except subprocess.CalledProcessError as e:
            print(f"解压失败: {e}")
            return False
    
    def flash_firmware(self):
        """刷写固件（需已解压，设备已进入 Recovery 模式）。"""
        self._check_cancel()
        extract_dir = self.download_dir / "extracted"

        actual_dir = getattr(self, '_extracted_dir', None)
        if actual_dir is None:
            actual_dir = self._detect_extracted_dir(extract_dir)
        if actual_dir is None:
            print(f"未找到解压目录，请检查: {extract_dir}")
            return False

        flash_script = actual_dir / "tools" / "kernel_flash" / "l4t_initrd_flash.sh"
        if not flash_script.exists():
            print(f"未找到刷写脚本: {flash_script}")
            return False

        print(f"工作目录: {actual_dir}")
        print(f"刷写脚本: {flash_script}")
        print("开始刷写，过程约 2-10 分钟，请勿断开 USB 或断电...")

        try:
            args = ["sudo", "./tools/kernel_flash/l4t_initrd_flash.sh",
                    "--flash-only", "--massflash", "1",
                    "--network", "usb0", "--showlogs"]
            self._run_cancelable_process(args, cwd=str(actual_dir))
            print("✓ 刷写完成")
            return True
        except InterruptedError:
            raise
        except subprocess.CalledProcessError as e:
            print(f"✗ 刷写失败 (exit {e.returncode})")
            return False
