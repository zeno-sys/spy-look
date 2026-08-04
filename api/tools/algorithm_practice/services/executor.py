from __future__ import annotations

import ast
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

TIMEOUT_SECONDS = 10


def check_syntax(code: str) -> list[dict[str, Any]]:
    """Check Python syntax via ast.parse.

    Returns a list of error dicts:
        {line, col, end_line, end_col, message}
    line/col are 1-based (matching Python's SyntaxError offset convention).
    """
    try:
        ast.parse(code)
        return []
    except SyntaxError as exc:
        return [
            {
                "line": exc.lineno or 1,
                "col": exc.offset or 1,
                "end_line": exc.end_lineno,
                "end_col": exc.end_offset,
                "message": exc.msg or "语法错误",
            }
        ]
    except (ValueError, MemoryError, RecursionError) as exc:
        # e.g. null bytes in source, or pathological nesting depth
        return [
            {
                "line": 1,
                "col": 1,
                "end_line": None,
                "end_col": None,
                "message": f"{type(exc).__name__}: {exc}",
            }
        ]


async def execute_python(code: str, stdin: str = "") -> dict[str, Any]:
    """Execute Python code in a subprocess with timeout.

    Uses subprocess.run in a thread pool (asyncio.to_thread) to remain
    compatible with SelectorEventLoop, which uvicorn uses in reload/subprocess
    mode on Windows and does not support asyncio.create_subprocess_exec.

    Returns dict with stdout, stderr, exit_code, duration_ms, timed_out.
    """
    tmp_dir = tempfile.mkdtemp(prefix="algo_run_")
    tmp_file = os.path.join(tmp_dir, "solution.py")

    with open(tmp_file, "w", encoding="utf-8") as f:
        f.write(code)

    start = time.monotonic()
    try:
        return await asyncio.to_thread(
            _run_subprocess, tmp_file, tmp_dir, stdin, start
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _run_subprocess(
    tmp_file: str,
    cwd: str,
    stdin: str,
    start: float,
) -> dict[str, Any]:
    """Blocking subprocess execution — called from a worker thread."""
    stdin_bytes = stdin.encode("utf-8") if stdin else None
    try:
        result = subprocess.run(
            [sys.executable, "-I", tmp_file],
            input=stdin_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            timeout=TIMEOUT_SECONDS,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "stdout": result.stdout.decode("utf-8", errors="replace"),
            "stderr": result.stderr.decode("utf-8", errors="replace"),
            "exit_code": result.returncode,
            "duration_ms": duration_ms,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        stderr += f"\n执行超时（{TIMEOUT_SECONDS}秒限制）\n"
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": -1,
            "duration_ms": duration_ms,
            "timed_out": True,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "stdout": "",
            "stderr": f"启动子进程失败: {type(exc).__name__}: {exc}",
            "exit_code": -1,
            "duration_ms": duration_ms,
            "timed_out": False,
        }
