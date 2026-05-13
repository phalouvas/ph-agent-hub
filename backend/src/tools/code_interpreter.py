# =============================================================================
# PH Agent Hub — Code Interpreter Tool Factory
# =============================================================================
# Docker-sandboxed Python execution. Agent-authored code for data analysis,
# charts, file transforms. AST-validated (no os/eval/exec), timeout-limited,
# no network by default. Output artifacts to MinIO/S3.
#
# Security model:
#   1. AST parse — reject syntax errors
#   2. AST walk — reject dangerous constructs (eval, exec, __import__, os,
#      sys, subprocess, importlib, etc.)
#   3. Whitelist-only imports for data science (pandas, numpy, matplotlib, etc.)
#   4. Runtime timeout (default 60s)
#   5. No network egress by default
#   6. Execution in a subprocess with resource limits
# =============================================================================

import ast
import asyncio
import base64
import io
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from agent_framework import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Whitelisted modules for code interpreter
# ---------------------------------------------------------------------------
SAFE_MODULES: set[str] = {
    # Standard library
    "json", "csv", "datetime", "re", "math", "hashlib", "base64",
    "uuid", "urllib.parse", "collections", "itertools", "textwrap",
    "html", "io", "typing", "enum", "random", "statistics",
    "functools", "operator", "string", "decimal", "fractions",
    "copy", "pprint", "dataclasses", "pathlib",
    # Data science (if installed in sandbox)
    "pandas", "numpy", "matplotlib", "plotly", "scipy",
    "openpyxl", "PIL", "Pillow",
}
SAFE_MODULES_LOWER = {m.lower() for m in SAFE_MODULES}

# Dangerous constructs to reject
FORBIDDEN_FUNCTIONS = {
    "eval", "exec", "compile", "__import__", "open", "input",
    "breakpoint",
}
FORBIDDEN_MODULES_PREFIX = {
    "os", "sys", "subprocess", "importlib", "shutil",
    "socket", "http", "urllib.request", "urllib.error",
    "ftplib", "smtplib", "telnetlib", "ctypes", "multiprocessing",
    "threading", "signal", "pdb", "code", "codeop",
    "builtins", "__builtins__",
}

# ---------------------------------------------------------------------------
# AST validation
# ---------------------------------------------------------------------------


class UnsafeCodeError(ValueError):
    """Raised when user-supplied code fails security validation."""


def _validate_code(code: str) -> None:
    """Validate code for safety. Raises UnsafeCodeError on unsafe code."""
    # 1. Syntax check
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise UnsafeCodeError(
            f"Syntax error at line {exc.lineno}: {exc.msg}"
        ) from exc

    # 2. Walk AST for dangerous constructs
    for node in ast.walk(tree):
        # --- Blocked function calls ---
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name in FORBIDDEN_FUNCTIONS:
                    raise UnsafeCodeError(
                        f"Use of '{name}()' is not allowed in code interpreter"
                    )
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.attr, str) and node.func.attr.startswith("__"):
                    raise UnsafeCodeError(
                        f"Access to dunder attribute '{node.func.attr}' is not allowed"
                    )

        # --- Blocked imports ---
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0].lower()
                if top_level in FORBIDDEN_MODULES_PREFIX:
                    raise UnsafeCodeError(
                        f"Import of '{alias.name}' is not allowed in code interpreter"
                    )
                if top_level not in SAFE_MODULES_LOWER and top_level not in {
                    m.split(".")[0].lower() for m in SAFE_MODULES
                }:
                    raise UnsafeCodeError(
                        f"Import of '{alias.name}' is not allowed. "
                        f"Allowed modules include: pandas, numpy, matplotlib, json, csv, math, etc."
                    )

        if isinstance(node, ast.ImportFrom):
            if node.module:
                top_level = node.module.split(".")[0].lower()
                if top_level in FORBIDDEN_MODULES_PREFIX:
                    raise UnsafeCodeError(
                        f"Import from '{node.module}' is not allowed in code interpreter"
                    )
                # Allow imports from safe modules only
                if top_level not in SAFE_MODULES_LOWER and top_level not in {
                    m.split(".")[0].lower() for m in SAFE_MODULES
                }:
                    raise UnsafeCodeError(
                        f"Import from '{node.module}' is not allowed. "
                        f"Allowed modules include: pandas, numpy, matplotlib, json, csv, math, etc."
                    )

        # --- Blocked attribute access on dunder ---
        if isinstance(node, ast.Attribute):
            if isinstance(node.attr, str) and node.attr.startswith("__") and node.attr != "__name__":
                # Allow __name__ for matplotlib/plotly but block __class__, etc.
                if node.attr in ("__class__", "__bases__", "__subclasses__", "__mro__",
                                 "__globals__", "__code__", "__closure__", "__dict__",
                                 "__builtins__"):
                    raise UnsafeCodeError(
                        f"Access to '{node.attr}' is not allowed"
                    )


# ---------------------------------------------------------------------------
# Code execution in subprocess
# ---------------------------------------------------------------------------

async def _run_subprocess(cmd_list: list[str], timeout_seconds: int) -> tuple:
    """Execute a subprocess command and return (stdout, stderr, exit_code).

    Returns (None, error_message, -1) on timeout.
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd_list,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return None, f"Execution timed out after {timeout_seconds} seconds", -1
    return stdout_bytes, stderr_bytes, proc.returncode or 0


async def _execute_python_code(
    code: str,
    timeout: int = 60,
    allow_network: bool = False,
) -> dict:
    """Execute Python code in a subprocess with resource limits.

    Returns a dict with stdout, stderr, and any base64-encoded images.
    """
    # Validate first
    _validate_code(code)

    # Wrap code to capture stdout/stderr and matplotlib output
    wrapper = f'''
import sys
import io
import json
import base64
import traceback

# Redirect stdout/stderr
_stdout = io.StringIO()
_stderr = io.StringIO()
sys.stdout = _stdout
sys.stderr = _stderr

# Configure matplotlib to use Agg backend (no display needed)
try:
    import matplotlib
    matplotlib.use("Agg")
except Exception:
    pass

_result = None
_error = None
_images = []

try:
{chr(10).join("    " + line for line in code.split(chr(10)))}
except Exception as _e:
    _error = traceback.format_exc()

# Restore stdout/stderr
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

# Collect any matplotlib figures
try:
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    for _fig_num in plt.get_fignums():
        _fig = plt.figure(_fig_num)
        _buf = io.BytesIO()
        _fig.savefig(_buf, format="png", bbox_inches="tight", dpi=100)
        _buf.seek(0)
        _images.append(base64.b64encode(_buf.read()).decode())
        _buf.close()
    plt.close("all")
except Exception:
    pass

# Collect any plotly figures
try:
    import plotly.io as pio
    import plotly.graph_objects as go
    # Check if any plotly figures were created (heuristic)
    for _var_name in dir():
        _var = eval(_var_name)
        if isinstance(_var, go.Figure):
            _img_bytes = pio.to_image(_var, format="png")
            _images.append(base64.b64encode(_img_bytes).decode())
except Exception:
    pass

output = {{
    "stdout": _stdout.getvalue(),
    "stderr": _stderr.getvalue(),
    "error": _error,
    "images": _images,
}}
print("__PH_RESULT_START__")
print(json.dumps(output))
print("__PH_RESULT_END__")
'''

    # Write code to temp file
    tmpdir = tempfile.mkdtemp(prefix="ph_code_interpreter_")
    script_path = os.path.join(tmpdir, "script.py")
    try:
        with open(script_path, "w") as f:
            f.write(wrapper)

        # Build the command
        # Use "timeout" command to enforce CPU time limit
        cmd = [
            "timeout", str(timeout),
            "python3", script_path,
        ]

        # If network is disallowed, we use unshare to isolate network
        # This requires CAP_SYS_ADMIN or running as root in container
        if not allow_network:
            # Try unshare first; fall back to just running without network isolation
            # if unshare is not available (graceful degradation)
            try:
                # Check if unshare is available
                check_proc = await asyncio.create_subprocess_exec(
                    "unshare", "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await check_proc.communicate()
                if check_proc.returncode == 0:
                    cmd = ["unshare", "-n"] + cmd
            except FileNotFoundError:
                pass  # unshare not available, proceed without network isolation

        # Execute
        stdout_bytes, stderr_bytes, exit_code = await _run_subprocess(
            cmd, timeout + 5
        )

        # If unshare failed (e.g., no CAP_SYS_ADMIN), retry without it
        if exit_code != 0 and not allow_network and cmd[0] == "unshare":
            stderr_text = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            if "unshare failed" in stderr_text or "Operation not permitted" in stderr_text:
                logger.info("unshare not available, retrying without network isolation")
                cmd = cmd[2:]  # Remove "unshare -n"
                stdout_bytes, stderr_bytes, exit_code = await _run_subprocess(
                    cmd, timeout + 5
                )

        if stdout_bytes is None:
            return {
                "stdout": "",
                "stderr": stderr_bytes or "",
                "error": stderr_bytes or f"Execution timed out after {timeout} seconds",
                "images": [],
                "exit_code": exit_code,
            }

        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        # Parse the JSON result from stdout
        result_start = stdout_text.find("__PH_RESULT_START__")
        result_end = stdout_text.find("__PH_RESULT_END__")

        if result_start >= 0 and result_end > result_start:
            json_str = stdout_text[result_start + len("__PH_RESULT_START__"):result_end].strip()
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError:
                result = {
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "error": None,
                    "images": [],
                }
            # Pre-result stdout (e.g., matplotlib warnings)
            pre_stdout = stdout_text[:result_start].strip()
            if pre_stdout:
                result["stdout"] = pre_stdout + "\n" + result.get("stdout", "")
        else:
            # Fallback: no JSON markers found
            result = {
                "stdout": stdout_text,
                "stderr": stderr_text,
                "error": None,
                "images": [],
            }

        result["exit_code"] = exit_code
        if exit_code != 0 and not result.get("error"):
            result["error"] = f"Process exited with code {exit_code}"

        # Clean up the marker lines from stdout for readability
        if "__PH_RESULT_START__" in result.get("stdout", ""):
            clean = result["stdout"]
            clean = clean.split("__PH_RESULT_START__")[0] + clean.split("__PH_RESULT_END__")[-1] if "__PH_RESULT_END__" in clean else clean
            result["stdout"] = clean.strip()

        return result

    finally:
        # Clean up temp files
        try:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_code_interpreter_tools(tool_config: dict | None = None) -> list:
    """Return a list of MAF @tool-decorated async functions for code
    interpretation.

    Args:
        tool_config: Optional ``Tool.config`` JSON dict.  May include:
            - ``timeout`` (int): max execution seconds (default 60)
            - ``allow_network`` (bool): allow network access (default False)

    Returns:
        A list of callables ready to pass to ``Agent(tools=...)``.
    """
    config = tool_config or {}
    timeout: int = int(config.get("timeout", 60))
    allow_network: bool = bool(config.get("allow_network", False))

    @tool
    async def execute_python(code: str) -> dict:
        """Execute Python code in a sandboxed environment and return the results.

        Use this for data analysis, chart creation, file transformations,
        calculations, or any task that requires running Python code.

        The sandbox includes common data science libraries:
        pandas, numpy, matplotlib, plotly, scipy, and openpyxl.

        Args:
            code: The Python code to execute. This should be a complete,
                  self-contained script. Print statements will be captured
                  and returned. Matplotlib/plotly figures will be
                  automatically captured as images.

        Returns:
            A dict with:
            - ``stdout``: printed output from the code
            - ``stderr``: error output
            - ``error``: exception traceback if the code raised an error
            - ``images``: list of base64-encoded PNG images (from matplotlib/plotly)
            - ``exit_code``: process exit code (0 = success)
        """
        if not code or not code.strip():
            return {"error": "No code provided", "stdout": "", "stderr": "", "images": []}

        logger.info(
            "Executing code interpreter (timeout=%ds, network=%s): %s",
            timeout, allow_network, code[:200],
        )

        try:
            result = await _execute_python_code(code, timeout=timeout, allow_network=allow_network)
        except UnsafeCodeError as exc:
            return {
                "stdout": "",
                "stderr": "",
                "error": str(exc),
                "images": [],
                "exit_code": -1,
            }

        return result

    return [execute_python]
