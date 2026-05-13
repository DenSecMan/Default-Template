"""Subprocess sandbox for running untrusted Python snippets."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


class SandboxTimeout(RuntimeError):
    """Raised when a sandboxed run exceeds its timeout."""


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    returncode: int


def run_python(code: str, timeout_s: float = 5.0) -> SandboxResult:
    """Execute `code` in an isolated Python interpreter (`-I`) with a temp cwd."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        script = tmp_path / "_run.py"
        script.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(script)],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            raise SandboxTimeout(
                f"Sandbox exceeded {timeout_s}s timeout"
            ) from e
        return SandboxResult(
            stdout=proc.stdout, stderr=proc.stderr, returncode=proc.returncode
        )


__all__ = ["SandboxResult", "SandboxTimeout", "run_python"]
