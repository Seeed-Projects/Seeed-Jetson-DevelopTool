"""命令执行引擎 — 本地或远程 SSH 执行，统一接口"""
import os
import re
import subprocess
from typing import Callable, Optional


class Runner:
    """
    本地命令执行器。
    后续可扩展 SSHRunner(Runner) 实现远程执行，接口保持一致。
    """

    def run(
        self,
        cmd: str,
        timeout: int = 30,
        on_output: Optional[Callable[[str], None]] = None,
    ) -> tuple[int, str]:
        """
        执行命令，返回 (returncode, output)。
        on_output: 实时输出回调，每行调用一次。
        同时处理 \\n 和 \\r 分隔（支持 pip 进度条等 \\r 刷新场景）。
        """
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        try:
            proc = subprocess.Popen(
                cmd, shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )
            fd    = proc.stdout.fileno()
            buf   = b""
            lines = []

            while True:
                try:
                    chunk = os.read(fd, 65536)   # 有多少读多少，立即返回
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                # 按 \n 或 \r 切割，保留最后未完成的片段
                parts = re.split(rb"[\n\r]+", buf)
                for part in parts[:-1]:
                    line = part.decode("utf-8", errors="replace").strip()
                    if line:
                        lines.append(line)
                        if on_output:
                            on_output(line)
                buf = parts[-1]

            # 冲刷剩余缓冲
            if buf.strip():
                line = buf.decode("utf-8", errors="replace").strip()
                lines.append(line)
                if on_output:
                    on_output(line)

            proc.wait(timeout=timeout)
            return proc.returncode, "\n".join(lines)
        except subprocess.TimeoutExpired:
            proc.kill()
            return -1, "timeout"
        except Exception as e:
            return -1, str(e)


class SSHRunner:
    """
    远程 SSH 命令执行器，接口与 Runner 一致。
    每次 run() 建立一条独立 SSH 连接，适合诊断类低频调用。
    """

    def __init__(self, host: str, username: str = "seeed",
                 password: str = "", port: int = 22):
        self.host     = host
        self.username = username
        self.password = password
        self.port     = port

    def run(
        self,
        cmd: str,
        timeout: int = 30,
        on_output: Optional[Callable[[str], None]] = None,
    ) -> tuple[int, str]:
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password or None,
                timeout=10,
                look_for_keys=True,
                allow_agent=True,
            )
            try:
                _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
                lines = []
                for raw in stdout:
                    line = raw.rstrip("\n")
                    lines.append(line)
                    if on_output:
                        on_output(line)
                rc  = stdout.channel.recv_exit_status()
                out = "\n".join(lines)
                if not out.strip():
                    out = stderr.read().decode("utf-8", errors="replace").strip()
                return rc, out
            finally:
                client.close()
        except Exception as e:
            return -1, str(e)


# ── 全局活跃 Runner 单例 ────────────────────────────────────────────────────
_active_runner: Optional[Runner] = None


def get_runner() -> Runner:
    """返回全局活跃 Runner（SSH 已连接则为 SSHRunner，否则为本地 Runner）。"""
    return _active_runner if _active_runner is not None else Runner()


def set_runner(runner: Optional[Runner]) -> None:
    """切换全局 Runner。传 None 恢复本地模式。"""
    global _active_runner
    _active_runner = runner

