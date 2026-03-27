"""命令执行引擎 — 本地或远程 SSH 执行，统一接口"""
import os
import re
import shlex
import subprocess
import time
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


class SSHRunner(Runner):
    """
    远程 SSH 命令执行器，接口与 Runner 一致。
    每次 run() 建立一条独立 SSH 连接，适合诊断类低频调用。
    """

    def __init__(self, host: str, username: str = "seeed",
                 password: str = "", port: int = 22, sudo_password: str = ""):
        self.host     = host
        self.username = username
        self.password = password
        self.sudo_password = sudo_password or password
        self.port     = port

    def _wrap_with_sudo_password(self, cmd: str) -> str:
        wrapper_parts = ["export TERM=${TERM:-xterm-256color};"]
        if self.sudo_password:
            wrapper_parts.extend([
                f"export SEEED_SUDO_PASSWORD={shlex.quote(self.sudo_password)};",
                "sudo() { printf '%s\\n' \"$SEEED_SUDO_PASSWORD\" | command sudo -S \"$@\"; };",
                "export -f sudo;",
            ])
        wrapper_parts.append(cmd)
        wrapper = " ".join(wrapper_parts)
        return f"bash -lc {shlex.quote(wrapper)}"

    def open_sftp(self):
        """建立 SSH 连接并返回 (client, sftp)，调用方负责 client.close()。"""
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
        client.get_transport().set_keepalive(30)
        sftp = client.open_sftp()
        return client, sftp

    def run(
        self,
        cmd: str,
        timeout: int = 30,
        on_output: Optional[Callable[[str], None]] = None,
    ) -> tuple[int, str]:
        import paramiko
        max_retries = 2
        last_exc = None
        for attempt in range(1 + max_retries):
            try:
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
                client.get_transport().set_keepalive(30)
                try:
                    _, stdout, stderr = client.exec_command(
                        self._wrap_with_sudo_password(cmd),
                        timeout=timeout,
                    )
                    lines = []
                    for raw in stdout:
                        line = raw.rstrip("\n")
                        lines.append(line)
                        if on_output:
                            on_output(line)
                    rc  = stdout.channel.recv_exit_status()
                    err = stderr.read().decode("utf-8", errors="replace").strip()
                    if err:
                        for line in err.splitlines():
                            if on_output:
                                on_output(line)
                        lines.extend(line for line in err.splitlines() if line)
                    out = "\n".join(lines)
                    return rc, out
                finally:
                    client.close()
            except (paramiko.SSHException, OSError) as e:
                # 连接级错误，可重试
                last_exc = e
                if attempt < max_retries:
                    delay = 1.5 * (attempt + 1)
                    print(f"[RUNNER] SSH retry {attempt + 1}/{max_retries} "
                          f"to {self.host} after {delay:.0f}s ({e})")
                    time.sleep(delay)
                continue
            except Exception as e:
                # 非连接错误，不重试
                _auto_disconnect_on_failure(self, e)
                return -1, str(e)
        # 所有重试用完
        _auto_disconnect_on_failure(self, last_exc)
        return -1, str(last_exc)


def _auto_disconnect_on_failure(runner, exc):
    """SSH 连接失败时自动断开：重置全局 runner + 发送 bus 事件。"""
    global _active_runner
    if _active_runner is not runner:
        return  # 已经被其他逻辑切换了
    ip = getattr(runner, "host", "")
    print(f"[RUNNER] SSH connection lost ({exc}), auto-disconnecting {ip}")
    _active_runner = None
    try:
        from seeed_jetson_develop.core.events import bus
        bus.device_disconnected.emit(ip)
    except Exception:
        pass


class SerialRunner(Runner):
    """
    通过串口登录 Jetson 并执行命令，接口与 SSHRunner 一致。
    每次 run() 建立一次串口会话，适合诊断类低频调用。
    """

    def __init__(self, port: str, username: str = "seeed", password: str = ""):
        self.port = port
        self.username = username
        self.password = password

    def run(
        self,
        cmd: str,
        timeout: int = 30,
        on_output: Optional[Callable[[str], None]] = None,
    ) -> tuple[int, str]:
        import re
        import time
        try:
            import serial
        except ImportError:
            return -1, "pyserial 未安装，请运行 pip install pyserial"

        lines: list[str] = []

        def _emit(text: str):
            if on_output:
                on_output(text)
            lines.append(text)

        try:
            ser = serial.Serial(
                self.port, baudrate=115200, timeout=0.1,
                bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            # 清空接收缓冲区，避免残留字符
            time.sleep(0.1)
            ser.reset_input_buffer()
        except Exception as exc:
            return -1, str(exc)

        def _read_until(patterns: list[str], wait: float) -> str:
            buf = ""
            deadline = time.time() + wait
            while time.time() < deadline:
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
                    if chunk:
                        buf += chunk
                else:
                    time.sleep(0.05)
                for p in patterns:
                    if re.search(p, buf):
                        return buf
            return buf

        try:
            for _ in range(3):
                ser.write(b"\r\n")
                time.sleep(0.3)
            buf = _read_until([r"login:", r"[$#]\s*"], 8.0)

            if re.search(r"login:", buf):
                time.sleep(0.2)
                ser.write((self.username + "\r\n").encode())
                buf = _read_until([r"[Pp]assword:", r"[$#]\s*"], 8.0)

            if re.search(r"[Pp]assword:", buf):
                time.sleep(0.2)
                ser.write((self.password + "\r\n").encode())
                buf = _read_until(
                    [r"[$#]\s*", r"[Ll]ogin incorrect", r"[Aa]uthentication failure"], 10.0)

            if not re.search(r"[$#]\s*", buf):
                if re.search(r"[Ll]ogin incorrect|[Aa]uthentication failure", buf):
                    return -1, "用户名或密码错误"
                return -1, "登录失败，未检测到 shell 提示符"

            time.sleep(0.2)
            ser.write(b"export TERM=xterm-256color\r\n")
            _read_until([r"[$#]\s*"], 3.0)
            ser.write((cmd + "\r\n").encode())
            result = _read_until([r"[$#]\s*"], float(timeout))

            # 去掉 ANSI 转义码，提取命令输出
            clean = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", result)
            clean = re.sub(r"\x1B[@-_]", "", clean)
            # 去掉回显的命令行和最后的提示符
            out_lines = []
            skip_first = True
            for line in clean.splitlines():
                stripped = line.strip()
                if skip_first and cmd.strip() in stripped:
                    skip_first = False
                    continue
                if re.search(r"[$#]\s*$", stripped) and not stripped.replace("$", "").replace("#", "").strip():
                    continue
                if stripped:
                    out_lines.append(stripped)
                    if on_output:
                        on_output(stripped)
            return 0, "\n".join(out_lines)
        except Exception as exc:
            return -1, str(exc)
        finally:
            try:
                ser.close()
            except Exception:
                pass


# ── 全局活跃 Runner 单例 ────────────────────────────────────────────────────
_active_runner: Optional[Runner] = None


def get_runner() -> Runner:
    """返回全局活跃 Runner（SSH 已连接则为 SSHRunner，否则为本地 Runner）。"""
    return _active_runner if _active_runner is not None else Runner()


def set_runner(runner: Optional[Runner]) -> None:
    """切换全局 Runner。传 None 恢复本地模式。"""
    global _active_runner
    _active_runner = runner
