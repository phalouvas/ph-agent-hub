# =============================================================================
# PH Agent Hub — Calculator Tool Factory
# =============================================================================
# Builds a MAF @tool-decorated async function that safely evaluates
# mathematical expressions using Python's ast module (no eval/exec).
# =============================================================================

import ast
import logging
import math
import operator

from agent_framework import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safe AST evaluator
# ---------------------------------------------------------------------------

# Allowed binary operators
_BINOPS: dict[type, callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.BitAnd: operator.and_,
}

# Allowed unary operators
_UNOPS: dict[type, callable] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Invert: operator.invert,
    ast.Not: operator.not_,
}

# Allowed function names mapped to math module functions
_ALLOWED_FUNCTIONS: dict[str, callable] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": pow,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "degrees": math.degrees,
    "radians": math.radians,
    "ceil": math.ceil,
    "floor": math.floor,
    "trunc": math.trunc,
    "factorial": math.factorial,
    "gcd": math.gcd,
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
    "nan": math.nan,
}


def _safe_eval(node: ast.AST) -> float | int:
    """Recursively evaluate an AST node using only allowed operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)

    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, (int, float)):
            return value
        raise ValueError(f"Unsupported constant type: {type(value).__name__}")

    # Python < 3.8 compat: ast.Num
    if hasattr(ast, "Num") and isinstance(node, ast.Num):
        return node.n

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in _UNOPS:
            return _UNOPS[op_type](_safe_eval(node.operand))
        raise ValueError(f"Unary operator {op_type.__name__} not allowed")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in _BINOPS:
            return _BINOPS[op_type](
                _safe_eval(node.left), _safe_eval(node.right)
            )
        raise ValueError(f"Binary operator {op_type.__name__} not allowed")

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_FUNCTIONS:
            fn = _ALLOWED_FUNCTIONS[node.func.id]
            args = [_safe_eval(a) for a in node.args]
            return fn(*args)
        raise ValueError(f"Function {getattr(node.func, 'id', '?')} not allowed")

    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_FUNCTIONS:
            val = _ALLOWED_FUNCTIONS[node.id]
            if callable(val):
                raise ValueError(f"Function '{node.id}' used without parentheses")
            return val
        raise ValueError(f"Variable '{node.id}' not allowed")

    if isinstance(node, ast.List):
        return [_safe_eval(e) for e in node.elts]

    if isinstance(node, ast.Tuple):
        return tuple(_safe_eval(e) for e in node.elts)

    raise ValueError(f"AST node type {type(node).__name__} not allowed")


def evaluate_expression(expression: str) -> float | int:
    """Parse and safely evaluate a mathematical expression string.

    Args:
        expression: A math expression like ``2 + 3 * 4`` or
            ``sqrt(16) * sin(pi/2)``.

    Returns:
        The numeric result.

    Raises:
        ValueError: If the expression contains disallowed operations
            or cannot be parsed.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression syntax: {exc}") from exc

    return _safe_eval(tree)


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_calculator_tools(tool_config: dict | None = None) -> list:
    """Return a list containing the MAF @tool-decorated calculate function.

    Args:
        tool_config: Optional ``Tool.config`` JSON dict.  Currently unused.

    Returns:
        A list with a single callable ready to pass to ``Agent(tools=...)``.
    """
    _ = tool_config  # no config needed

    @tool
    async def calculate(expression: str) -> dict:
        """Safely evaluate a mathematical expression.

        Supports basic arithmetic (+, -, *, /, //, %, **), bitwise ops,
        and common math functions: sqrt, sin, cos, tan, log, log10, log2,
        exp, abs, round, ceil, floor, min, max, sum, pow, factorial, gcd,
        degrees, radians, and constants pi, e, tau, inf, nan.

        Args:
            expression: The mathematical expression to evaluate.
                Examples: ``"2 + 3 * 4"``, ``"sqrt(25)"``,
                ``"sin(pi/2)"``, ``"log10(1000)"``.

        Returns:
            A dict with:
            - ``expression``: the original expression
            - ``result``: the numeric result (int or float)
            - ``result_type``: "int" or "float"
        """
        logger.info("calculate: %s", expression)
        try:
            result = evaluate_expression(expression)
        except ValueError as exc:
            logger.warning("calculate error for '%s': %s", expression, exc)
            return {"expression": expression, "error": str(exc)}
        except Exception as exc:
            logger.exception("calculate unexpected error for '%s'", expression)
            return {"expression": expression, "error": str(exc)}

        return {
            "expression": expression,
            "result": result,
            "result_type": "int" if isinstance(result, int) else "float",
        }

    return [calculate]
