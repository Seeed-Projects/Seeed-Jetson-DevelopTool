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
        """运行可取消的子进程。"""
        self._check_cancel()
        process = subprocess.Popen(args, cwd=cwd)
        try:
            while True:
                retcode = process.poll()
                if retcode is not None:
                    if retcode != 0:
                        raise subprocess.CalledProcessError(retcode, args)
                    return
                self._check_cancel()
                time.sleep(0.25)
        except InterruptedError:
            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                process.kill()
            raise

    def _download_from_url(self, url, filepath, filename):
        """从指定 URL 下载到目标文件。"""
        self._check_cancel()
        tmp_path = filepath.with_suffix(filepath.suffix + ".part")
        if tmp_path.exists():
            tmp_path.unlink()

        response = requests.get(url, stream=True, timeout=(15, 600), allow_redirects=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        content_type = response.headers.get("content-type", "")
        chunks = response.iter_content(chunk_size=8192)

        first_chunk = b""
        for chunk in chunks:
            if chunk:
                first_chunk = chunk
                break

        if not first_chunk:
            raise ValueError("下载内容为空")

        if self._looks_like_html(content_type, first_chunk):
            raise ValueError("下载链接返回网页内容，非固件文件")

        written = len(first_chunk)
        with open(tmp_path, "wb") as f, tqdm(
            desc=filename,
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
    
    def download_firmware(self):
        """下载固件"""
        filename = self.firmware_info['filename']
        filepath = self.download_dir / filename
        
        if filepath.exists():
            size = filepath.stat().st_size
            if size > 1024 * 1024:
                print(f"固件已存在: {filepath}")
                return True
            print(f"检测到已有文件异常偏小({size} bytes)，将重新下载: {filepath}")
            filepath.unlink()
        
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
                part_path = filepath.with_suffix(filepath.suffix + ".part")
                if part_path.exists():
                    part_path.unlink()

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
            print(f"解压完成: {extract_dir}")
            return True
        
        except InterruptedError:
            raise
        except subprocess.CalledProcessError as e:
            print(f"解压失败: {e}")
            return False
    
    def flash_firmware(self):
        """刷写固件"""
        self._check_cancel()
        foldername = self.firmware_info['foldername']
        extract_dir = self.download_dir / "extracted" / foldername
        
        if not extract_dir.exists():
            print(f"未找到解压目录: {extract_dir}")
            return False
        
        print(f"正在刷写固件...")
        print(f"工作目录: {extract_dir}")
        
        # 检查设备是否在 recovery 模式
        try:
            result = subprocess.run("lsusb | grep -i nvidia", shell=True, capture_output=True, text=True)
            if not result.stdout:
                print("警告: 未检测到 Jetson 设备，请确保设备已进入 Recovery 模式")
                print("使用 'seeed-jetson-flash recovery -p <product>' 查看进入 Recovery 模式的教程")
                return False
        except Exception as e:
            print(f"检查设备失败: {e}")
        
        # 执行刷写脚本
        flash_script = extract_dir / "tools" / "kernel_flash" / "l4t_initrd_flash.sh"
        
        if not flash_script.exists():
            print(f"未找到刷写脚本: {flash_script}")
            return False
        
        print(f"执行刷写脚本: {flash_script}")
        print("注意: 刷写过程可能需要 2-10 分钟，请耐心等待...")
        
        try:
            args = ["sudo", "./tools/kernel_flash/l4t_initrd_flash.sh", "--flash-only"]
            self._run_cancelable_process(args, cwd=str(extract_dir))
            print("✓ 刷写完成")
            return True
        
        except InterruptedError:
            raise
        except subprocess.CalledProcessError as e:
            print(f"✗ 刷写失败: {e}")
            return False
