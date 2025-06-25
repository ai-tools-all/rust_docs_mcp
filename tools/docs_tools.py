#!/usr/bin/env python3
"""
MCP tools for documentation fetching and management operations.

This module provides MCP tool wrappers around the core documentation functionality.
"""

from pathlib import Path
from typing import Dict

from fastmcp import FastMCP, Context

from src.core import fetch_crate_docs_impl, save_docs_to_disk_impl, fetch_and_save_project_docs_impl
from src.logger import setup_logging

# Configuration
DOCS_CACHE_DIR = Path("./rust_docs_cache")
LOGS_DIR = Path("./logs")
DOCS_CACHE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

logger = setup_logging(LOGS_DIR)


def register_docs_tools(mcp: FastMCP):
    """Register documentation related MCP tools."""
    
    @mcp.tool
    async def fetch_crate_docs(crate_name: str, version: str, ctx: Context) -> Dict[str, str]:
        """
        Fetch documentation for a specific Rust crate from docs.rs.
        
        Args:
            crate_name: Name of the crate
            version: Version of the crate
            
        Returns:
            Dictionary mapping module paths to their documentation content as markdown
        """
        return await fetch_crate_docs_impl(crate_name, version, DOCS_CACHE_DIR, logger, ctx)

    @mcp.tool
    async def save_docs_to_disk(crate_name: str, version: str, docs: Dict[str, str], ctx: Context) -> str:
        """
        Save fetched documentation to local disk as markdown files.
        
        Args:
            crate_name: Name of the crate
            version: Version of the crate  
            docs: Dictionary of module_path -> markdown_content
            
        Returns:
            Path to the saved documentation directory
        """
        return await save_docs_to_disk_impl(crate_name, version, docs, DOCS_CACHE_DIR, logger, ctx)

    @mcp.tool
    async def fetch_and_save_project_docs(cargo_lock_path: str, ctx: Context) -> Dict[str, str]:
        """
        Complete workflow: Read Cargo.lock, fetch docs for all dependencies, and save to disk.
        
        Args:
            cargo_lock_path: Path to the Cargo.lock file
            
        Returns:
            Dictionary mapping crate names to their saved documentation directory paths
        """
        return await fetch_and_save_project_docs_impl(cargo_lock_path, DOCS_CACHE_DIR, logger, ctx)