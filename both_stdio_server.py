#!/usr/bin/env python3
"""
FastMCP server for Rust documentation management.

This server provides tools to:
1. Read Cargo.lock files and extract dependency versions
2. Fetch documentation from docs.rs by scraping content
3. Store scraped documentation as markdown files locally
4. List cached documentation

Usage:
    python rust_docs_server.py
"""

from fastmcp import FastMCP

from tools.cargo_tools import register_cargo_tools
from tools.docs_tools import register_docs_tools
from tools.cache_tools import register_cache_tools
from src.logger import setup_logging

# Initialize the FastMCP server
mcp = FastMCP("Rust Docs Server 🦀")

# Setup logging
logger = setup_logging()

# Register all tool modules
register_cargo_tools(mcp)
register_docs_tools(mcp)
register_cache_tools(mcp)


if __name__ == "__main__":
    import sys
    
    logger.info("Rust Docs Server starting up")
    
    # Check command line arguments for transport type
    if len(sys.argv) > 1:
        transport = sys.argv[1].lower()
        
        if transport == "sse":
            # Run with SSE transport
            logger.info("Running with SSE transport on http://127.0.0.1:8604")
            mcp.run(transport="sse", host="127.0.0.1", port=8604)
        elif transport == "http":
            # Run with HTTP transport
            logger.info("Running with HTTP transport on http://127.0.0.1:8604/mcp")
            mcp.run(transport="http", host="127.0.0.1", port=8604, path="/mcp")
        elif transport == "stdio":
            # Run with STDIO transport (default)
            logger.info("Running with STDIO transport")
            mcp.run(transport="stdio")
        else:
            print("Usage: python rust_docs_server.py [stdio|sse|http]")
            print("Default: stdio")
            logger.info("Running with default STDIO transport")
            mcp.run()
    else:
        # Default to STDIO
        logger.info("Running with default STDIO transport")
        mcp.run()