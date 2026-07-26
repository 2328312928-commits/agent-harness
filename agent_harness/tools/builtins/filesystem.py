from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_harness.domain.errors import ValidationError
from agent_harness.domain.models import ToolPermission, ToolSpec
from agent_harness.tools.base import Tool, ToolContext


def _safe_path(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    target = (root / relative_path).resolve()
    if target != root and root not in target.parents:
        raise ValidationError("Path escapes the configured workspace root")
    return target


class FileReadTool(Tool):
    spec = ToolSpec(
        name="filesystem.read_file",
        description="Read a UTF-8 text file inside the configured workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path relative to the workspace root.",
                },
                "max_bytes": {"type": "integer", "minimum": 1, "maximum": 1_000_000},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        permissions=[ToolPermission.READ],
        idempotent=True,
    )

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        path = _safe_path(context.workspace_root, arguments["path"])
        if not path.is_file():
            raise ValidationError(f"File not found: {arguments['path']}")
        max_bytes = arguments.get("max_bytes", 256_000)
        content = path.read_bytes()[:max_bytes]
        return {
            "path": str(path.relative_to(context.workspace_root.resolve())),
            "content": content.decode("utf-8", errors="replace"),
            "truncated": path.stat().st_size > max_bytes,
        }


class FileWriteTool(Tool):
    spec = ToolSpec(
        name="filesystem.write_file",
        description="Write a UTF-8 text file inside the configured workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string", "maxLength": 1_000_000},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        permissions=[ToolPermission.WRITE],
        idempotent=True,
    )

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        path = _safe_path(context.workspace_root, arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(arguments["content"], encoding="utf-8")
        return {
            "path": str(path.relative_to(context.workspace_root.resolve())),
            "bytes": path.stat().st_size,
        }


class ListDirectoryTool(Tool):
    spec = ToolSpec(
        name="filesystem.list",
        description="List files and directories under a workspace-relative path.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."},
                "depth": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1},
            },
            "additionalProperties": False,
        },
        permissions=[ToolPermission.READ],
        idempotent=True,
    )

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        root = context.workspace_root.resolve()
        path = _safe_path(root, arguments.get("path", "."))
        if not path.is_dir():
            raise ValidationError(f"Directory not found: {arguments.get('path', '.')}")
        depth = min(arguments.get("depth", 1), 3)
        entries: list[dict[str, Any]] = []
        for item in sorted(path.iterdir(), key=lambda value: (value.is_file(), value.name.lower())):
            relative = item.relative_to(root).as_posix()
            entries.append(
                {
                    "path": relative,
                    "type": "file" if item.is_file() else "directory",
                    "size": item.stat().st_size if item.is_file() else None,
                }
            )
            if item.is_dir() and depth > 1:
                for child in sorted(item.rglob("*")):
                    if child.is_file() and len(child.relative_to(item).parts) < depth:
                        entries.append(
                            {
                                "path": child.relative_to(root).as_posix(),
                                "type": "file",
                                "size": child.stat().st_size,
                            }
                        )
        return {"path": str(path.relative_to(root)), "entries": entries}
