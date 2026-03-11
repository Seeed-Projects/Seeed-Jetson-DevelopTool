"""命令执行引擎 — 本地或远程 SSH 执行，统一接口"""
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
        """
        try:
            proc = subprocess.Popen(
                cmd, shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            lines = []
            for line in proc.stdout:
                line = line.rstrip()
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
