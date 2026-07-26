from __future__ import annotations

import asyncio
import re
import sqlite3
from pathlib import Path
from typing import Any

from agent_harness.domain.errors import HarnessError, ToolPermissionError, ValidationError
from agent_harness.domain.models import ToolPermission, ToolSpec
from agent_harness.tools.base import Tool, ToolContext


class DatabaseQueryTool(Tool):
    spec = ToolSpec(
        name="database.query",
        description=(
            "Run a read-only SQL query against the configured SQLite or PostgreSQL database."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 20_000},
                "parameters": {"type": "object", "default": {}},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        permissions=[ToolPermission.DATABASE, ToolPermission.READ],
        idempotent=True,
        timeout_seconds=20,
    )

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        query = arguments["query"].strip()
        if not re.match(r"^(select|with|pragma|explain)\b", query, flags=re.IGNORECASE):
            raise ToolPermissionError(
                "Only read-only SELECT, WITH, PRAGMA, and EXPLAIN queries are allowed"
            )
        if ";" in query.rstrip(";"):
            raise ValidationError("Multiple SQL statements are not allowed")
        if not self.database_url:
            raise ValidationError("DATABASE_READONLY_URL is not configured")

        if self.database_url.startswith("sqlite"):
            return await asyncio.to_thread(
                self._query_sqlite,
                query,
                arguments.get("parameters", {}),
                arguments.get("limit", 100),
            )
        if self.database_url.startswith(
            ("postgresql://", "postgres://", "postgresql+asyncpg://")
        ):
            return await self._query_postgres(
                query,
                arguments.get("parameters", {}),
                arguments.get("limit", 100),
            )
        raise ValidationError("Unsupported database URL")

    def _query_sqlite(
        self,
        query: str,
        parameters: dict[str, Any],
        limit: int,
    ) -> dict[str, Any]:
        path = self.database_url.split("///", 1)[-1]
        connection = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
        try:
            cursor = connection.execute(query, parameters)
            columns = [item[0] for item in cursor.description or []]
            rows = [dict(zip(columns, row, strict=False)) for row in cursor.fetchmany(limit)]
            return {"columns": columns, "rows": rows, "row_count": len(rows)}
        except sqlite3.Error as exc:
            raise HarnessError(f"SQLite query failed: {exc}") from exc
        finally:
            connection.close()

    async def _query_postgres(
        self,
        query: str,
        parameters: dict[str, Any],
        limit: int,
    ) -> dict[str, Any]:
        try:
            import asyncpg
        except ImportError as exc:
            raise HarnessError("asyncpg is required for PostgreSQL queries") from exc
        url = self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        connection = await asyncpg.connect(url)
        try:
            values = list(parameters.values())
            if values:
                parameter_names = list(parameters)
                rewritten = re.sub(
                    r":([A-Za-z_][A-Za-z0-9_]*)",
                    lambda match: f"${parameter_names.index(match.group(1)) + 1}",
                    query,
                )
                records = await connection.fetch(rewritten, *values)
            else:
                records = await connection.fetch(query)
            rows = [dict(record) for record in records[:limit]]
            return {
                "columns": list(records[0].keys()) if records else [],
                "rows": rows,
                "row_count": len(rows),
            }
        except asyncpg.PostgresError as exc:
            raise HarnessError(f"PostgreSQL query failed: {exc}") from exc
        finally:
            await connection.close()
