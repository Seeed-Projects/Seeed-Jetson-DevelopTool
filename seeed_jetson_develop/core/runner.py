"""命令执行引擎 — 本地或远程 SSH 执行，统一接口"""
import os
import re
import shlex
import subprocess
import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger("seeed.core.runner")


_SHELL_META_RE = re.compile(r"[|&;<>()$`\\n]")


def _sanitize_cmd_for_log(cmd: str | list[str]) -> str:
    if isinstance(cmd, (list, tuple)):
        text = " ".join(shlex.quote(str(part)) for part in cmd)
    else:
        text = str(cmd or "")
    text = re.sub(r"echo\s+(['\"]).*?\1\s*\|\s*sudo\s+-S", "echo '***' | sudo -S", text, flags=re.IGNORECASE)
    text = re.sub(r"(--password\s+)(\S+)", r"\1***", text, flags=re.IGNORECASE)
    return text


def _prepare_local_command(cmd: str | list[str]) -> tuple[str | list[str], bool]:
    if isinstance(cmd, (list, tuple)):
        return [str(part) for part in cmd], False
    text = str(cmd or "").strip()
    if not text:
        return text, True
    if _SHELL_META_RE.search(text):
        return text, True
    try:
        parts = shlex.split(text, posix=True)
    except ValueError:
        return text, True
    if not parts:
        return text, True
    return parts, False


class Runner:
    """
    本地命令执行器。
    后续可扩展 SSHRunner(Runner) 实现远程执行，接口保持一致。
    """

    def run(
        self,
        cmd: str | list[str],
        timeout: int = 30,
        on_output: Optional[Callable[[str], None]] = None,
    ) -> tuple[int, str]:
        """
        执行命令，返回 (returncode, output)。
        on_output: 实时输出回调，每行调用一次。
        同时处理 \\n 和 \\r 分隔（支持 pip 进度条等 \\r 刷新场景）。
        """
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        popen_cmd, use_shell = _prepare_local_command(cmd)
        proc = None
        try:
            proc = subprocess.Popen(
                popen_cmd,
                shell=use_shell,
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
            if proc is not None:
                proc.kill()
            log.warning("Command timed out after %ss: %s", timeout, _sanitize_cmd_for_log(cmd))
            return -1, "timeout"
        except Exception as e:
            log.exception("Runner command failed: %s", _sanitize_cmd_for_log(cmd))
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

    def _build_remote_shell_command(self, cmd: str) -> str:
        wrapper_parts = ["export TERM=${TERM:-xterm-256color};"]
        if self.sudo_password:
            # Do not rely on SSH environment passthrough, which may be blocked by server policy.
            wrapper_parts.append(f"SEEED_SUDO_PASSWORD={shlex.quote(self.sudo_password)}; export SEEED_SUDO_PASSWORD;")
        wrapper_parts.extend([
            "if [ -n \"${SEEED_SUDO_PASSWORD:-}\" ]; then "
            "sudo() { printf '%s\\n' \"$SEEED_SUDO_PASSWORD\" | command sudo -S -p '' \"$@\"; }; "
            "export -f sudo; fi;",
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
        safe_cmd = self._build_remote_shell_command(cmd)
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
            client.get_transport().set_keepalive(30)
            try:
                try:
                    _, stdout, stderr = client.exec_command(
                        safe_cmd,
                        timeout=timeout,
                        get_pty=True,
                    )
                except TypeError:
                    log.error("Paramiko does not support exec_command(environment=...). Refusing insecure sudo-password fallback.")
                    return -1, (
                        "Paramiko version is too old for secure environment passthrough. "
                        "Please upgrade Paramiko to a version that supports exec_command(environment=...)."
                    )
                ch = stdout.channel
                out_buf = b""
                err_buf = b""
                lines: list[str] = []
                start_ts = time.time()
                deadline = start_ts + timeout if timeout and timeout > 0 else None

                def _emit_line(line: str):
                    s = (line or "").strip()
                    if not s:
                        return
                    if s.startswith("[sudo]") or "password for" in s.lower() or "的密码" in s:
                        return
                    lines.append(s)
                    if on_output:
                        on_output(s)

                def _drain_buf(buf: bytes) -> bytes:
                    parts = re.split(rb"[\r\n]+", buf)
                    for part in parts[:-1]:
                        _emit_line(part.decode("utf-8", errors="replace"))
                    return parts[-1]

                while True:
                    had_new_output = False
                    if ch.recv_ready():
                        out_buf += ch.recv(65536)
                        out_buf = _drain_buf(out_buf)
                        had_new_output = True
                    if ch.recv_stderr_ready():
                        err_buf += ch.recv_stderr(65536)
                        err_buf = _drain_buf(err_buf)
                        had_new_output = True

                    if ch.exit_status_ready() and not ch.recv_ready() and not ch.recv_stderr_ready():
                        break

                    if deadline and time.time() > deadline:
                        ch.close()
                        return -1, "timeout"
                    time.sleep(0.05)

                if out_buf.strip():
                    _emit_line(out_buf.decode("utf-8", errors="replace"))
                if err_buf.strip():
                    _emit_line(err_buf.decode("utf-8", errors="replace"))

                rc = ch.recv_exit_status()
                out = "\n".join(lines)
                return rc, out
            finally:
                client.close()
        except Exception as e:
            log.exception("SSHRunner command failed on %s: %s", self.host, _sanitize_cmd_for_log(cmd))
            return -1, str(e)


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
        except Exception as exc:
            log.exception("Serial open failed on %s", self.port)
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
            log.exception("Serial command failed on %s: %s", self.port, _sanitize_cmd_for_log(cmd))
            return -1, str(exc)
        finally:
            try:
                ser.close()
            except Exception:
                pass


# ── 全局活跃 Runner 单例 ────────────────────────────────────────────────────
_active_runner: Optional[Runner] = None
_runner_lock = threading.RLock()
_default_runner = Runner()


def get_runner() -> Runner:
    """返回全局活跃 Runner（SSH 已连接则为 SSHRunner，否则为本地 Runner）。"""
    with _runner_lock:
        return _active_runner if _active_runner is not None else _default_runner


def set_runner(runner: Optional[Runner]) -> None:
    """切换全局 Runner。传 None 恢复本地模式。"""
    global _active_runner
    with _runner_lock:
        _active_runner = runner
