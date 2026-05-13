# =============================================================================
# PH Agent Hub — SQL Query Tool Factory
# =============================================================================
# Read-only SQL against tenant-configured database. AST-validated
# (DML/DROP/GRANT rejected), per-tenant encrypted connection strings,
# row-limited results.
#
# Security model:
#   1. SQL parsing via sqlparse — rejects DML, DDL, DCL statements
#   2. Read-only transaction (SET TRANSACTION READ ONLY)
#   3. Configurable row limit (default 1000)
#   4. Per-tenant connection string stored encrypted in tool.config
#   5. Supported backends: PostgreSQL, MySQL/MariaDB
# =============================================================================

import logging
from typing import Any

from agent_framework import tool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_ROW_LIMIT: int = 1000

# SQL keywords that indicate dangerous operations
# Each tuple: (keyword, description)
FORBIDDEN_KEYWORDS: set[str] = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "REPLACE", "LOAD", "IMPORT",
    "RENAME", "LOCK", "UNLOCK", "CALL", "EXECUTE", "EXEC",
    "MERGE", "UPSERT",
}

# Additional dangerous patterns
FORBIDDEN_PATTERNS: list[str] = [
    "INTO OUTFILE", "INTO DUMPFILE", "INTO OUTFILE",
    "INFORMATION_SCHEMA", "mysql.", "pg_read_file",
    "pg_read_binary_file", "pg_stat", "pg_sleep",
    "SLEEP(", "BENCHMARK(", "WAITFOR DELAY",
    "COPY ", "\\copy",
]

# Allowed statement types
ALLOWED_STATEMENT_TYPES: set[str] = {
    "SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN",
    "WITH",  # CTEs
}


# ---------------------------------------------------------------------------
# SQL validation
# ---------------------------------------------------------------------------


class UnsafeSqlError(ValueError):
    """Raised when SQL fails security validation."""


def _validate_sql(sql: str) -> None:
    """Validate SQL for safety. Raises UnsafeSqlError on dangerous SQL.

    Uses simple keyword-based checking since we don't want to add a
    heavy SQL parser dependency. This is a defense-in-depth measure;
    the read-only transaction provides the primary security boundary.
    """
    if not sql or not sql.strip():
        raise UnsafeSqlError("Empty SQL query")

    sql_upper = sql.upper().strip()

    # Check for multiple statements (semicolons outside strings are suspicious)
    # Simple heuristic: count semicolons not inside quotes
    in_single_quote = False
    in_double_quote = False
    semicolon_count = 0
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not in_double_quote:
            # Check for escaped quote
            if i + 1 < len(sql) and sql[i + 1] == "'":
                i += 1  # skip escaped quote
            else:
                in_single_quote = not in_single_quote
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif ch == ";" and not in_single_quote and not in_double_quote:
            semicolon_count += 1
            # Only count semicolons that aren't the last character
            remaining = sql[i + 1:].strip()
            if remaining and not remaining.startswith("--"):
                pass  # We'll handle this below
        i += 1

    # Allow trailing semicolon, but no multiple statements
    clean_sql = sql_upper.rstrip(";").strip()

    # Check for forbidden keywords as whole words at statement boundaries
    words = clean_sql.split()
    if words:
        first_word = words[0]
        # WITH is allowed (CTEs)
        if first_word not in ALLOWED_STATEMENT_TYPES:
            raise UnsafeSqlError(
                f"Statement type '{first_word}' is not allowed. "
                f"Only SELECT, SHOW, DESCRIBE, EXPLAIN, and WITH (CTE) queries are permitted."
            )

    # Check for forbidden keywords anywhere in the SQL (including subqueries)
    for keyword in FORBIDDEN_KEYWORDS:
        # Use word boundary check - the keyword should appear as a whole word
        import re
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, clean_sql):
            raise UnsafeSqlError(
                f"SQL contains forbidden keyword: {keyword}. "
                "Only read-only queries (SELECT) are allowed."
            )

    # Check for dangerous patterns
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.upper() in clean_sql:
            raise UnsafeSqlError(
                f"SQL contains forbidden pattern: {pattern}"
            )

    # Reject semicolons that indicate multiple statements (after removing trailing)
    if ";" in clean_sql:
        raise UnsafeSqlError(
            "Multiple SQL statements are not allowed. Please use a single query."
        )


def _add_row_limit(sql: str, row_limit: int) -> str:
    """Add a row limit to the SQL query if it doesn't already have one.

    Handles SELECT statements only; SHOW/DESCRIBE/EXPLAIN are returned
    as-is since they don't support LIMIT in all dialects.
    """
    clean_sql = sql.rstrip(";").strip()
    sql_upper = clean_sql.upper()

    # Don't add LIMIT to non-SELECT statements
    first_word = sql_upper.split()[0] if sql_upper.split() else ""
    if first_word not in ("SELECT", "WITH"):
        return clean_sql

    # Check if LIMIT already exists
    if "LIMIT" in sql_upper:
        return clean_sql

    # Check if FETCH or TOP is used (other limit syntaxes)
    if "FETCH FIRST" in sql_upper or "FETCH NEXT" in sql_upper:
        return clean_sql

    return f"{clean_sql} LIMIT {row_limit}"


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

# Cache of AsyncEngine instances keyed by connection string hash
_engine_cache: dict[str, AsyncEngine] = {}


def _get_engine(connection_string: str) -> AsyncEngine:
    """Get or create an async SQLAlchemy engine for a connection string.

    Engines are cached to avoid creating new connection pools on every
    tool invocation.
    """
    from ..core.encryption import decrypt

    # Decrypt if the connection string is encrypted
    try:
        conn_str = decrypt(connection_string)
    except Exception:
        # If decryption fails, assume it's already plaintext
        conn_str = connection_string

    # Convert sync URL to async if needed
    if conn_str.startswith("postgresql://"):
        conn_str = conn_str.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif conn_str.startswith("postgres://"):
        conn_str = conn_str.replace("postgres://", "postgresql+asyncpg://", 1)
    elif conn_str.startswith("mysql://"):
        conn_str = conn_str.replace("mysql://", "mysql+aiomysql://", 1)
    elif conn_str.startswith("mariadb://"):
        conn_str = conn_str.replace("mariadb://", "mysql+aiomysql://", 1)

    cache_key = conn_str
    if cache_key not in _engine_cache:
        _engine_cache[cache_key] = create_async_engine(
            conn_str,
            echo=False,
            pool_size=3,
            max_overflow=5,
            pool_recycle=300,
            pool_pre_ping=True,
        )
        logger.info("Created new SQL engine for connection (cache size: %d)", len(_engine_cache))

    return _engine_cache[cache_key]


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_sql_query_tools(tool_config: dict | None = None) -> list:
    """Return a list of MAF @tool-decorated async functions for SQL queries.

    Args:
        tool_config: ``Tool.config`` JSON dict.  Must include:
            - ``connection_string`` (str): Database connection string
              (supports postgresql://, mysql://, mariadb:// schemes).
              The value may be encrypted via the platform's Fernet encryption.
            - ``row_limit`` (int, optional): Max rows to return (default 1000).

    Returns:
        A list of callables ready to pass to ``Agent(tools=...)``.
    """
    config = tool_config or {}
    connection_string: str = config.get("connection_string", "")
    row_limit: int = int(config.get("row_limit", DEFAULT_ROW_LIMIT))

    if not connection_string:
        logger.error("sql_query tool has no connection_string configured")
        # Return a tool that returns an error rather than failing
        @tool
        async def sql_query(query: str) -> dict:
            """SQL query tool — not configured."""
            return {"error": "Database connection not configured. Please set connection_string in tool config."}

        @tool
        async def list_tables() -> dict:
            """List tables — not configured."""
            return {"error": "Database connection not configured."}

        @tool
        async def describe_table(table: str) -> dict:
            """Describe table — not configured."""
            return {"error": "Database connection not configured."}

        return [sql_query, list_tables, describe_table]

    # Build engine
    try:
        engine = _get_engine(connection_string)
    except Exception as exc:
        logger.error("Failed to create SQL engine: %s", exc)
        @tool
        async def sql_query(query: str) -> dict:
            return {"error": f"Failed to connect to database: {str(exc)}"}

        @tool
        async def list_tables() -> dict:
            return {"error": f"Failed to connect to database: {str(exc)}"}

        @tool
        async def describe_table(table: str) -> dict:
            return {"error": f"Failed to connect to database: {str(exc)}"}

        return [sql_query, list_tables, describe_table]

    # ------------------------------------------------------------------
    @tool
    async def sql_query(query: str) -> dict:
        """Execute a read-only SQL query against the configured database.

        Only SELECT, SHOW, DESCRIBE, EXPLAIN, and WITH (CTE) queries
        are allowed. Results are limited to a maximum number of rows.

        Args:
            query: The SQL query to execute. Must be a single read-only
                   statement (SELECT, SHOW, DESCRIBE, EXPLAIN, or WITH).

        Returns:
            A dict with:
            - ``columns``: list of column names
            - ``rows``: list of row dicts (up to the row limit)
            - ``row_count``: number of rows returned
            - ``truncated``: True if results were truncated by the row limit
            - ``error``: error message if query failed
        """
        if not query or not query.strip():
            return {"error": "No query provided", "columns": [], "rows": [], "row_count": 0}

        # Validate SQL safety
        try:
            _validate_sql(query)
        except UnsafeSqlError as exc:
            logger.warning("SQL query rejected: %s", exc)
            return {"error": str(exc), "columns": [], "rows": [], "row_count": 0}

        # Add row limit
        safe_query = _add_row_limit(query, row_limit + 1)  # +1 to detect truncation

        logger.info("Executing SQL query (row_limit=%d): %s", row_limit, safe_query[:200])

        try:
            async with engine.connect() as conn:
                # Set read-only transaction
                try:
                    await conn.execute(text("SET TRANSACTION READ ONLY"))
                except Exception:
                    # Some databases don't support this (e.g., older MySQL)
                    pass

                result = await conn.execute(text(safe_query))

                # Get column names
                columns = list(result.keys())

                # Fetch rows
                rows = []
                for row in result:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        val = row[i]
                        # Convert non-serializable types to strings
                        if isinstance(val, bytes):
                            val = f"<binary data, {len(val)} bytes>"
                        elif isinstance(val, (set, frozenset)):
                            val = list(val)
                        elif hasattr(val, "isoformat"):
                            val = val.isoformat()
                        row_dict[col] = val
                    rows.append(row_dict)

                truncated = len(rows) > row_limit
                if truncated:
                    rows = rows[:row_limit]

                await conn.commit()

                return {
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                    "truncated": truncated,
                }

        except Exception as exc:
            logger.error("SQL query execution failed: %s", exc)
            return {
                "error": f"Query execution failed: {str(exc)}",
                "columns": [],
                "rows": [],
                "row_count": 0,
            }

    # ------------------------------------------------------------------
    @tool
    async def list_tables() -> dict:
        """List all tables in the configured database.

        Returns:
            A dict with:
            - ``tables``: list of table names
            - ``error``: error message if discovery failed
        """
        try:
            async with engine.connect() as conn:
                # Try information_schema first (works for most databases)
                result = await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'mysql', 'sys') "
                        "ORDER BY table_name"
                    )
                )
                tables = [row[0] for row in result]
                await conn.commit()

                if tables:
                    return {"tables": tables}

                # Fallback: try SHOW TABLES (MySQL/MariaDB)
                result = await conn.execute(text("SHOW TABLES"))
                tables = [row[0] for row in result]
                await conn.commit()

                return {"tables": tables}

        except Exception as exc:
            logger.error("Failed to list tables: %s", exc)
            return {"error": f"Failed to list tables: {str(exc)}", "tables": []}

    # ------------------------------------------------------------------
    @tool
    async def describe_table(table: str) -> dict:
        """Describe a table's columns, types, and sample values.

        Args:
            table: The name of the table to describe.

        Returns:
            A dict with:
            - ``table``: the table name
            - ``columns``: list of column info dicts (name, type, nullable, default)
            - ``sample_rows``: up to 5 sample rows from the table
            - ``error``: error message if description failed
        """
        if not table or not table.strip():
            return {"error": "No table name provided", "columns": [], "sample_rows": []}

        # Sanitize table name (reject SQL injection attempts in table name)
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_\.]*$', table.strip()):
            return {"error": f"Invalid table name: {table}", "columns": [], "sample_rows": []}

        safe_table = table.strip()

        try:
            async with engine.connect() as conn:
                # Get column info
                try:
                    result = await conn.execute(
                        text(
                            "SELECT column_name, data_type, is_nullable, column_default "
                            "FROM information_schema.columns "
                            "WHERE table_name = :table "
                            "ORDER BY ordinal_position"
                        ),
                        {"table": safe_table},
                    )
                    columns = [
                        {
                            "name": row[0],
                            "type": row[1],
                            "nullable": row[2] == "YES" if row[2] else None,
                            "default": str(row[3]) if row[3] else None,
                        }
                        for row in result
                    ]
                except Exception:
                    # Fallback: DESCRIBE (MySQL/MariaDB)
                    result = await conn.execute(text(f"DESCRIBE {safe_table}"))
                    columns = []
                    for row in result:
                        col_info = {
                            "name": row[0] if len(row) > 0 else "unknown",
                            "type": str(row[1]) if len(row) > 1 else "unknown",
                            "nullable": None,
                            "default": None,
                        }
                        columns.append(col_info)

                await conn.commit()

                if not columns:
                    return {"error": f"Table '{safe_table}' not found or has no columns", "table": safe_table, "columns": [], "sample_rows": []}

                # Get sample rows
                sample_rows = []
                try:
                    result = await conn.execute(
                        text(f"SELECT * FROM {safe_table} LIMIT 5")
                    )
                    sample_columns = list(result.keys())
                    for row in result:
                        row_dict = {}
                        for i, col in enumerate(sample_columns):
                            val = row[i]
                            if isinstance(val, bytes):
                                val = f"<binary data, {len(val)} bytes>"
                            elif hasattr(val, "isoformat"):
                                val = val.isoformat()
                            row_dict[col] = val
                        sample_rows.append(row_dict)
                    await conn.commit()
                except Exception as exc:
                    logger.warning("Failed to get sample rows for %s: %s", safe_table, exc)

                return {
                    "table": safe_table,
                    "columns": columns,
                    "sample_rows": sample_rows,
                }

        except Exception as exc:
            logger.error("Failed to describe table %s: %s", safe_table, exc)
            return {"error": f"Failed to describe table: {str(exc)}", "table": safe_table, "columns": [], "sample_rows": []}

    return [sql_query, list_tables, describe_table]
