#!/usr/bin/env python3
"""
MCP tools for cache management operations.

This module provides MCP tool wrappers around the core cache functionality.
"""

from pathlib import Path
from typing import List

import aiofiles
from fastmcp import FastMCP, Context

from src.core import list_cached_documentation_impl, get_cached_doc_content_impl
from src.logger import setup_logging

# Configuration
DOCS_CACHE_DIR = Path("./rust_docs_cache")
LOGS_DIR = Path("./logs")
DOCS_CACHE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

logger = setup_logging(LOGS_DIR)


def register_cache_tools(mcp: FastMCP):
    """Register cache management related MCP tools and resources."""
    
    @mcp.tool
    async def list_cached_documentation(ctx: Context) -> List[str]:
        """
        Lists the names of all crate documentations currently stored in the local cache.

        Each entry in the list corresponds to a directory in the cache, typically
        in the format 'crate-name-version'.

        Args:
            ctx: The FastMCP context object.

        Returns:
            A list of strings, where each string is the name of a cached documentation directory.
        """
        await ctx.info("Listing cached documentation...")
        
        try:
            cached_dirs = await list_cached_documentation_impl(DOCS_CACHE_DIR, logger)
            
            if cached_dirs:
                await ctx.info(f"Found {len(cached_dirs)} cached documentations.")
            else:
                await ctx.info("No documentation found in the cache.")

            return cached_dirs
        except Exception as e:
            await ctx.error(f"An error occurred while listing cached docs: {e}")
            return []

    @mcp.resource("docs://cache")
    async def list_cached_docs() -> str:
        """List all cached documentation directories."""
        logger.info("Listing cached documentation")
        try:
            cached_dirs = await list_cached_documentation_impl(DOCS_CACHE_DIR, logger)
            
            if cached_dirs:
                return f"Cached documentation:\n" + "\n".join(f"- {name}" for name in sorted(cached_dirs))
            else:
                return "No cached documentation found."
        
        except Exception as e:
            logger.error("Error listing cached docs", exc_info=True)
            return f"Error listing cached docs: {str(e)}"

    @mcp.resource("docs://cache/{crate_name}")
    async def get_cached_doc_content(crate_name: str) -> str:
        """Get the content of a cached documentation directory."""
        return await get_cached_doc_content_impl(crate_name, DOCS_CACHE_DIR, logger)