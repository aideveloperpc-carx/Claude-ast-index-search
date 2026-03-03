"""MCP server wrapping ast-index CLI for code search and navigation."""

import asyncio
import json
import os
import shutil
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

AST_INDEX_BIN = os.environ.get("AST_INDEX_BIN", "ast-index")
PROJECT_ROOT = os.environ.get("AST_INDEX_PROJECT_ROOT", os.getcwd())

server = Server("ast-index-mcp")


async def run_ast_index(args: list[str], timeout: int = 120) -> str:
    """Run ast-index CLI and return stdout."""
    cmd = [AST_INDEX_BIN, "--format", "json"] + args
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=PROJECT_ROOT,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return json.dumps({"error": "Command timed out"})
    except FileNotFoundError:
        return json.dumps({"error": f"ast-index binary not found at '{AST_INDEX_BIN}'"})

    output = stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        return json.dumps({"error": err or f"Exit code {proc.returncode}", "output": output})
    return output if output else json.dumps({"result": "ok"})


# ---------- Tool definitions ----------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "ast_rebuild",
        "description": "Rebuild the AST index for the project (full reindex). Run this first before any search. Options: type (files|symbols|modules|all), no_deps, no_ignore, project_type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "default": "all", "description": "Index type: files, symbols, modules, or all"},
                "no_deps": {"type": "boolean", "default": False, "description": "Skip module dependencies indexing"},
                "no_ignore": {"type": "boolean", "default": False, "description": "Include gitignored files"},
                "project_type": {"type": "string", "description": "Force project type (android, ios, python, go, rust, csharp, cpp, php, ruby, scala, bsl, frontend, perl, dart, bazel)"},
            },
        },
    },
    {
        "name": "ast_update",
        "description": "Incremental index update (only changed files).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ast_search",
        "description": "Universal search across files and symbols.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 20},
                "in_file": {"type": "string", "description": "Filter by file path"},
                "module": {"type": "string", "description": "Filter by module path"},
                "fuzzy": {"type": "boolean", "default": False},
            },
            "required": ["query"],
        },
    },
    {
        "name": "ast_symbol",
        "description": "Find symbols (classes, interfaces, functions, properties).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Symbol name"},
                "type": {"type": "string", "description": "Symbol type: class, interface, function, property"},
                "limit": {"type": "integer", "default": 20},
                "in_file": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "ast_class",
        "description": "Find class or interface by name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["name"],
        },
    },
    {
        "name": "ast_hierarchy",
        "description": "Show class hierarchy (parents and children).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "class_name": {"type": "string"},
                "depth": {"type": "integer", "default": 5},
            },
            "required": ["class_name"],
        },
    },
    {
        "name": "ast_implementations",
        "description": "Find implementations/subclasses of a class or interface.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "base": {"type": "string", "description": "Base class/interface name"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["base"],
        },
    },
    {
        "name": "ast_refs",
        "description": "Cross-references: definitions, imports, and usages of a symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "ast_usages",
        "description": "Find all usages of a symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "ast_outline",
        "description": "Show all symbols defined in a file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File path (relative to project root)"},
            },
            "required": ["file"],
        },
    },
    {
        "name": "ast_imports",
        "description": "Show imports in a file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
            },
            "required": ["file"],
        },
    },
    {
        "name": "ast_file",
        "description": "Find files by name pattern.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "exact": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "ast_module",
        "description": "Find modules by pattern.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "ast_deps",
        "description": "Show module dependencies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {"type": "string"},
            },
            "required": ["module"],
        },
    },
    {
        "name": "ast_dependents",
        "description": "Show reverse dependencies (who depends on this module).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {"type": "string"},
            },
            "required": ["module"],
        },
    },
    {
        "name": "ast_map",
        "description": "Show compact project map (key types per directory).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "Filter by module"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    {
        "name": "ast_conventions",
        "description": "Detect project conventions (architecture, frameworks, naming).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ast_stats",
        "description": "Show index statistics.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ast_callers",
        "description": "Find callers of a function (grep-based).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "function_name": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["function_name"],
        },
    },
    {
        "name": "ast_call_tree",
        "description": "Show call hierarchy tree for a function.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "function_name": {"type": "string"},
                "depth": {"type": "integer", "default": 3},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["function_name"],
        },
    },
    {
        "name": "ast_todo",
        "description": "Find TODO/FIXME/HACK comments.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "default": "TODO|FIXME|HACK"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    {
        "name": "ast_changed",
        "description": "Show changed symbols compared to a git base (e.g., main).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "base": {"type": "string", "default": "main", "description": "Git base branch"},
            },
        },
    },
    {
        "name": "ast_query",
        "description": "Execute raw SQL SELECT query against the AST index database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL query (SELECT only)"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "ast_unused_symbols",
        "description": "Find potentially unused symbols in the project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "Filter by module path"},
                "export_only": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    {
        "name": "ast_annotations",
        "description": "Find classes with a specific annotation (e.g., @Service, @Module).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "annotation": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["annotation"],
        },
    },
    {
        "name": "ast_api",
        "description": "Show public API of a module.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {"type": "string"},
            },
            "required": ["module"],
        },
    },
    {
        "name": "ast_schema",
        "description": "Show AST index database schema (tables and columns).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ast_db_path",
        "description": "Print path to the SQLite index database.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _build_args(tool_name: str, arguments: dict[str, Any]) -> list[str]:
    """Convert tool name + arguments dict to CLI args list."""
    # Map tool names to CLI subcommands
    cmd_map = {
        "ast_rebuild": "rebuild",
        "ast_update": "update",
        "ast_search": "search",
        "ast_symbol": "symbol",
        "ast_class": "class",
        "ast_hierarchy": "hierarchy",
        "ast_implementations": "implementations",
        "ast_refs": "refs",
        "ast_usages": "usages",
        "ast_outline": "outline",
        "ast_imports": "imports",
        "ast_file": "file",
        "ast_module": "module",
        "ast_deps": "deps",
        "ast_dependents": "dependents",
        "ast_map": "map",
        "ast_conventions": "conventions",
        "ast_stats": "stats",
        "ast_callers": "callers",
        "ast_call_tree": "call-tree",
        "ast_todo": "todo",
        "ast_changed": "changed",
        "ast_query": "query",
        "ast_unused_symbols": "unused-symbols",
        "ast_annotations": "annotations",
        "ast_api": "api",
        "ast_schema": "schema",
        "ast_db_path": "db-path",
    }

    subcmd = cmd_map[tool_name]
    args = [subcmd]

    # Positional argument mappings per command
    positional_map = {
        "search": "query",
        "symbol": "name",
        "class": "name",
        "hierarchy": "class_name",
        "implementations": "base",
        "refs": "symbol",
        "usages": "symbol",
        "outline": "file",
        "imports": "file",
        "file": "pattern",
        "module": "pattern",
        "deps": "module",
        "dependents": "module",
        "callers": "function_name",
        "call-tree": "function_name",
        "todo": "pattern",
        "query": "sql",
        "annotations": "annotation",
        "api": "module",
    }

    pos_key = positional_map.get(subcmd)
    if pos_key and pos_key in arguments:
        args.append(str(arguments[pos_key]))

    # Flag/option arguments
    for key, val in arguments.items():
        if key == pos_key:
            continue
        if val is None:
            continue
        if isinstance(val, bool):
            if val:
                flag = key.replace("_", "-")
                args.append(f"--{flag}")
        else:
            flag = key.replace("_", "-")
            args.extend([f"--{flag}", str(val)])

    return args


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [Tool(**t) for t in TOOLS]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    arguments = arguments or {}

    if name not in {t["name"] for t in TOOLS}:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    # Longer timeout for rebuild
    timeout = 600 if name == "ast_rebuild" else 120

    cli_args = _build_args(name, arguments)
    result = await run_ast_index(cli_args, timeout=timeout)
    return [TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
