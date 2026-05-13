# =============================================================================
# PH Agent Hub — Custom Tool Executor
# =============================================================================
# AST-based code validation and dynamic MAF tool factory for user-supplied
# Python code stored in the ``tools.code`` column.
#
# Security model:
#   1. AST parse — reject syntax errors
#   2. AST walk — reject dangerous constructs (eval, exec, __import__, os, etc.)
#   3. Whitelist-only imports (httpx, json, datetime, etc.)
#   4. Require an ``async def execute(...)`` function
#   5. Runtime timeout (30s default)
# =============================================================================

import ast
import logging
from typing import Any

from agent_framework import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Whitelisted modules for user code
# ---------------------------------------------------------------------------
SAFE_MODULES: set[str] = {
    "httpx",
    "json",
    "datetime",
    "re",
    "math",
    "hashlib",
    "base64",
    "uuid",
    "urllib",
    "urllib.parse",
    "asyncio",
    "collections",
    "itertools",
    "textwrap",
    "html",
    "csv",
    "io",
    "typing",
    "enum",
    "random",
    "statistics",
}

# ---------------------------------------------------------------------------
# AST-based validation
# ---------------------------------------------------------------------------


class UnsafeCodeError(ValueError):
    """Raised when user-supplied code fails security validation."""


def validate_tool_code(code: str) -> None:
    """Validate user-supplied tool code for safety.

    Raises ``UnsafeCodeError`` with a human-readable message if the code
    is invalid or unsafe.
    """
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
                if name in {"eval", "exec", "compile", "__import__", "open"}:
                    raise UnsafeCodeError(
                        f"Use of '{name}()' is not allowed in custom tool code"
                    )
            elif isinstance(node.func, ast.Attribute):
                # Block dunder attribute access (e.g., obj.__class__)
                if isinstance(node.func.attr, str) and node.func.attr.startswith("__"):
                    raise UnsafeCodeError(
                        f"Access to dunder attribute '{node.func.attr}' is not allowed"
                    )

        # --- Blocked imports ---
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                if top_level not in SAFE_MODULES:
                    raise UnsafeCodeError(
                        f"Import of '{alias.name}' is not allowed. "
                        f"Allowed modules: {', '.join(sorted(SAFE_MODULES))}"
                    )

        if isinstance(node, ast.ImportFrom):
            if node.module:
                top_level = node.module.split(".")[0]
                if top_level not in SAFE_MODULES:
                    raise UnsafeCodeError(
                        f"Import from '{node.module}' is not allowed. "
                        f"Allowed modules: {', '.join(sorted(SAFE_MODULES))}"
                    )

        # --- Blocked builtins ---
        if isinstance(node, ast.Name):
            if node.id in {"eval", "exec", "compile", "__import__", "open"}:
                raise UnsafeCodeError(
                    f"Use of '{node.id}' is not allowed in custom tool code"
                )

    # 3. Require an async function named 'execute'
    has_execute = any(
        isinstance(node, ast.AsyncFunctionDef) and node.name == "execute"
        for node in ast.iter_child_nodes(tree)
    )
    if not has_execute:
        raise UnsafeCodeError(
            "Custom tool code must define an 'async def execute(...)' function"
        )


# ---------------------------------------------------------------------------
# Dynamic factory
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT: float = 30.0


def build_custom_tool_from_code(
    code: str,
    config: dict | None = None,
) -> list:
    """Validate and compile user code into a list of MAF tool callables.

    The user code must define an ``async def execute(...)`` function.
    The system wraps it in an ``@tool``-decorated function that the MAF
    agent can call.

    Args:
        code: The Python source code from ``tools.code``.
        config: Optional ``Tool.config`` dict. May include:
            - ``timeout`` (float): max execution seconds (default 30)

    Returns:
        A list with a single MAF tool callable, or an empty list if
        validation fails (error is logged).
    """
    # Validate first
    try:
        validate_tool_code(code)
    except UnsafeCodeError as exc:
        logger.error("Custom tool code validation failed: %s", exc)
        return []

    cfg = config or {}
    timeout: float = float(cfg.get("timeout", DEFAULT_TIMEOUT))

    # Build a restricted globals namespace with safe modules pre-imported
    safe_globals: dict[str, Any] = {
        "__builtins__": {
            "abs": abs,
            "all": all,
            "any": any,
            "ascii": ascii,
            "bin": bin,
            "bool": bool,
            "bytearray": bytearray,
            "bytes": bytes,
            "callable": callable,
            "chr": chr,
            "complex": complex,
            "dict": dict,
            "dir": dir,
            "divmod": divmod,
            "enumerate": enumerate,
            "filter": filter,
            "float": float,
            "format": format,
            "frozenset": frozenset,
            "getattr": getattr,
            "hasattr": hasattr,
            "hash": hash,
            "hex": hex,
            "id": id,
            "int": int,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "iter": iter,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "next": next,
            "object": object,
            "oct": oct,
            "ord": ord,
            "pow": pow,
            "print": print,
            "range": range,
            "repr": repr,
            "reversed": reversed,
            "round": round,
            "set": set,
            "slice": slice,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "type": type,
            "zip": zip,
            "__import__": __import__,
            "True": True,
            "False": False,
            "None": None,
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
            "IndexError": IndexError,
            "RuntimeError": RuntimeError,
            "StopIteration": StopIteration,
            "MemoryError": MemoryError,
            "ArithmeticError": ArithmeticError,
            "ZeroDivisionError": ZeroDivisionError,
        },
    }

    # Pre-import safe modules into the namespace
    _imports_code = "\n".join(
        f"import {mod}" for mod in sorted(SAFE_MODULES)
    )
    try:
        exec(_imports_code, safe_globals)  # nosec — safe_globals is restricted
    except Exception as exc:
        logger.error("Failed to pre-import safe modules: %s", exc)
        return []

    # Compile and exec the user code into the restricted namespace
    try:
        compiled = compile(code, "<custom_tool>", "exec")
        exec(compiled, safe_globals)  # nosec — safe_globals is restricted
    except Exception as exc:
        logger.error("Failed to compile/exec custom tool code: %s", exc)
        return []

    user_execute = safe_globals.get("execute")
    if user_execute is None:
        logger.error("Custom tool code did not define 'execute' function")
        return []

    # Build the docstring from the user's execute function
    _ = (user_execute.__doc__ or "").strip() or "Custom tool function."

    @tool
    async def custom_tool(**kwargs: Any) -> dict:
        """Execute user-defined custom tool code.

        Args:
            **kwargs: Passed directly to the user's ``execute()`` function.

        Returns:
            The dict returned by the user's ``execute()`` function.
        """
        logger.info("Executing custom tool with kwargs=%s", kwargs)
        try:
            result = await asyncio_wrapper(user_execute, timeout, **kwargs)
            return result
        except TimeoutError:
            logger.error("Custom tool execution timed out after %ss", timeout)
            return {"error": f"Execution timed out after {timeout} seconds"}
        except Exception as exc:
            logger.error("Custom tool execution error: %s", exc)
            return {"error": str(exc)}

    return [custom_tool]


async def asyncio_wrapper(func: Any, timeout: float, **kwargs: Any) -> Any:
    """Run the user's execute() with a timeout."""
    import asyncio as _asyncio

    return await _asyncio.wait_for(func(**kwargs), timeout=timeout)
