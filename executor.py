import subprocess
import time
from dataclasses import dataclass
from typing import Optional
import settings

@dataclass
class ExecutionResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def output(self) -> str:
        combined = []
        if self.stdout:
            combined.append(self.stdout)
        if self.stderr:
            combined.append(f"[STDERR]\n{self.stderr}")
        return "\n".join(combined).strip() or "(no output)"


def execute_command(cmd: str, timeout: Optional[int] = None) -> ExecutionResult:
    """
    Executes a shell command in the system terminal and captures the output.
    Does NOT execute 'quit' commands.
    """
    cmd_clean = cmd.strip()
    if cmd_clean.lower() == "quit":
        return ExecutionResult(
            command=cmd_clean,
            returncode=0,
            stdout="Quit command detected. Subprocess execution bypassed.",
            stderr="",
            duration_seconds=0.0
        )

    timeout = timeout or settings.COMMAND_TIMEOUT_SECONDS
    start_time = time.time()

    try:
        process = subprocess.run(
            cmd_clean,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(settings.BASE_DIR)
        )
        duration = round(time.time() - start_time, 3)
        return ExecutionResult(
            command=cmd_clean,
            returncode=process.returncode,
            stdout=process.stdout.strip(),
            stderr=process.stderr.strip(),
            duration_seconds=duration,
            timed_out=False
        )
    except subprocess.TimeoutExpired as e:
        duration = round(time.time() - start_time, 3)
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        return ExecutionResult(
            command=cmd_clean,
            returncode=-1,
            stdout=stdout.strip(),
            stderr=f"Command timed out after {timeout}s. {stderr}".strip(),
            duration_seconds=duration,
            timed_out=True
        )
    except Exception as e:
        duration = round(time.time() - start_time, 3)
        return ExecutionResult(
            command=cmd_clean,
            returncode=-1,
            stdout="",
            stderr=f"Execution error: {str(e)}",
            duration_seconds=duration,
            timed_out=False
        )

