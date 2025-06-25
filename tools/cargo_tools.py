#!/usr/bin/env python3
"""
MCP tools for Cargo.lock file operations.

This module provides MCP tool wrappers around the core Cargo.lock functionality.
"""

from pathlib import Path
from typing import Dict

from fastmcp import FastMCP, Context

from src.core import read_cargo_lock_impl
from src.logger import setup_logging

# Configuration
DOCS_CACHE_DIR = Path("./rust_docs_cache")
LOGS_DIR = Path("./logs")
DOCS_CACHE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

logger = setup_logging(LOGS_DIR)


def register_cargo_tools(mcp: FastMCP):
    """Register Cargo.lock related MCP tools."""
    
    @mcp.tool
    async def read_cargo_lock(file_path: str, ctx: Context) -> Dict[str, str]:
        """
        Read and parse a Cargo.lock file to extract dependency versions.
        
        Args:
            file_path: Path to the Cargo.lock file
            
        Returns:
            Dictionary mapping package names to their versions
        """
        return await read_cargo_lock_impl(file_path, DOCS_CACHE_DIR, LOGS_DIR, logger, ctx)