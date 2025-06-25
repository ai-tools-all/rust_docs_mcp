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

import asyncio
from pathlib import Path
from typing import Dict, List, Optional

import aiofiles
from fastmcp import FastMCP, Context

from logger import setup_logging
from parser import CargoLockParser
from scraper import DocsRsScraper, load_cached_docs, save_docs_to_disk

# Initialize the FastMCP server
mcp = FastMCP("Rust Docs Server 🦀")

# Configuration
DOCS_CACHE_DIR = Path("./rust_docs_cache")
LOGS_DIR = Path("./logs")
DOCS_CACHE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


logger = setup_logging(LOGS_DIR)






# Core logic functions (not decorated with @mcp.tool)
async def _read_cargo_lock_impl(file_path: str, ctx: Optional[Context] = None) -> Dict[str, str]:
    """
    Core implementation for reading and parsing a Cargo.lock file.
    """
    if ctx:
        await ctx.info(f"Reading Cargo.lock file: {file_path}")
    logger.info("Attempting to read Cargo.lock", extra={'extra_data': {'path': file_path}})
    
    try:
        path = Path(file_path).expanduser().resolve()
        
        if not path.exists():
            if ctx:
                await ctx.error(f"Cargo.lock file not found: {path}")
            logger.error("Cargo.lock file not found", extra={'extra_data': {'resolved_path': str(path)}})
            return {}
        
        if not path.name == "Cargo.lock":
            if ctx:
                await ctx.error(f"File must be named Cargo.lock, got: {path.name}")
            logger.error("File is not Cargo.lock", extra={'extra_data': {'path': str(path), 'filename': path.name}})
            return {}
        
        async with aiofiles.open(path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        parser = CargoLockParser()
        dependencies = parser.parse_cargo_lock(content)
        
        if ctx:
            await ctx.info(f"Found {len(dependencies)} dependencies")
        logger.info(
            "Successfully parsed Cargo.lock", 
            extra={'extra_data': {'path': file_path, 'dependency_count': len(dependencies)}}
        )
        return dependencies
    
    except Exception as e:
        if ctx:
            await ctx.error(f"Error reading Cargo.lock: {str(e)}")
        logger.error("Failed to read or parse Cargo.lock", exc_info=True, extra={'extra_data': {'path': file_path}})
        return {}




async def _fetch_crate_docs_impl(crate_name: str, version: str, ctx: Optional[Context] = None) -> Dict[str, str]:
    """
    Core implementation for fetching documentation for a specific Rust crate.
    First checks local cache, then fetches from docs.rs if not cached.
    """
    if ctx:
        await ctx.info(f"Fetching documentation for {crate_name} v{version}")
    
    # First, try to load from cache
    cached_docs = await load_cached_docs(crate_name, version, DOCS_CACHE_DIR, logger, ctx)
    if cached_docs:
        return cached_docs
    
    # If not cached, fetch from docs.rs
    try:
        async with DocsRsScraper() as scraper:
            docs = await scraper.fetch_crate_docs(crate_name, version, logger, ctx)
        
        if docs:
            if ctx:
                await ctx.info(f"Successfully fetched {len(docs)} documentation sections")
            logger.info(
                "Successfully fetched documentation sections",
                extra={'extra_data': {'crate': crate_name, 'version': version, 'section_count': len(docs)}}
            )
            
            # Automatically save to cache
            await _save_docs_to_disk_impl(crate_name, version, docs, ctx)
        else:
            if ctx:
                await ctx.error(f"No documentation found for {crate_name} v{version}")
            logger.warning(
                "No documentation found for crate",
                extra={'extra_data': {'crate': crate_name, 'version': version}}
            )
        
        return docs
    
    except Exception as e:
        if ctx:
            await ctx.error(f"Error fetching docs: {str(e)}")
        logger.error("Error fetching docs", exc_info=True, extra={'extra_data': {'crate': crate_name, 'version': version}})
        return {}


async def _save_docs_to_disk_impl(crate_name: str, version: str, docs: Dict[str, str], ctx: Optional[Context] = None) -> str:
    """
    Core implementation for saving fetched documentation to local disk.
    """
    return await save_docs_to_disk(crate_name, version, docs, DOCS_CACHE_DIR, logger, ctx)


async def _fetch_and_save_project_docs_impl(cargo_lock_path: str, ctx: Optional[Context] = None) -> Dict[str, str]:
    """
    Core implementation for the complete workflow: Read Cargo.lock, fetch docs for all dependencies, and save to disk.
    """
    if ctx:
        await ctx.info("Starting complete documentation fetch workflow")
    logger.info(
        "Starting complete documentation fetch workflow",
        extra={'extra_data': {'cargo_lock_path': cargo_lock_path}}
    )
    
    # Step 1: Read Cargo.lock
    dependencies = await _read_cargo_lock_impl(cargo_lock_path, ctx)
    if not dependencies:
        return {}
    
    # Step 2: Fetch and save docs for each dependency
    saved_paths = {}
    
    for crate_name, version in list(dependencies.items())[:5]:  # Limit to first 5 for demo
        if ctx:
            await ctx.info(f"Processing {crate_name} v{version}")
        logger.info(
            "Processing crate from dependency list",
            extra={'extra_data': {'crate': crate_name, 'version': version}}
        )
        
        # Fetch docs
        docs = await _fetch_crate_docs_impl(crate_name, version, ctx)
        
        if docs:
            # Save to disk
            saved_path = await _save_docs_to_disk_impl(crate_name, version, docs, ctx)
            if saved_path:
                saved_paths[crate_name] = saved_path
        
        # Small delay between crates
        await asyncio.sleep(1)
    
    if ctx:
        await ctx.info(f"Completed workflow. Processed {len(saved_paths)} crates.")
    logger.info(
        "Completed documentation fetch workflow",
        extra={'extra_data': {'processed_count': len(saved_paths), 'total_dependencies': len(dependencies)}}
    )
    return saved_paths


# MCP tool wrappers
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
    logger.info("Executing list_cached_documentation tool.")

    cached_dirs = []
    if not DOCS_CACHE_DIR.exists():
        await ctx.info("Cache directory does not exist. No cached docs found.")
        logger.warning("Cache directory not found.", extra={'extra_data': {'path': str(DOCS_CACHE_DIR)}})
        return []

    try:
        for item in DOCS_CACHE_DIR.iterdir():
            if item.is_dir():
                cached_dirs.append(item.name)
        
        cached_dirs.sort() # Sort for consistent output

        if cached_dirs:
            await ctx.info(f"Found {len(cached_dirs)} cached documentations.")
            logger.info(f"Found {len(cached_dirs)} cached documentations.", extra={'extra_data': {'count': len(cached_dirs), 'dirs': cached_dirs}})
        else:
            await ctx.info("No documentation found in the cache.")
            logger.info("No cached documentation directories found.")

        return cached_dirs
    except Exception as e:
        await ctx.error(f"An error occurred while listing cached docs: {e}")
        logger.error("Failed to list cached documentation.", exc_info=True)
        return []

@mcp.tool
async def read_cargo_lock(file_path: str, ctx: Context) -> Dict[str, str]:
    """
    Read and parse a Cargo.lock file to extract dependency versions.
    
    Args:
        file_path: Path to the Cargo.lock file
        
    Returns:
        Dictionary mapping package names to their versions
    """
    return await _read_cargo_lock_impl(file_path, ctx)


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
    return await _fetch_crate_docs_impl(crate_name, version, ctx)


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
    return await save_docs_to_disk(crate_name, version, docs, DOCS_CACHE_DIR, logger, ctx)


@mcp.tool
async def fetch_and_save_project_docs(cargo_lock_path: str, ctx: Context) -> Dict[str, str]:
    """
    Complete workflow: Read Cargo.lock, fetch docs for all dependencies, and save to disk.
    
    Args:
        cargo_lock_path: Path to the Cargo.lock file
        
    Returns:
        Dictionary mapping crate names to their saved documentation directory paths
    """
    return await _fetch_and_save_project_docs_impl(cargo_lock_path, ctx)


@mcp.resource("docs://cache")
async def list_cached_docs() -> str:
    """List all cached documentation directories."""
    logger.info("Listing cached documentation")
    try:
        cached_dirs = []
        if DOCS_CACHE_DIR.exists():
            for item in DOCS_CACHE_DIR.iterdir():
                if item.is_dir():
                    cached_dirs.append(item.name)
        
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
    logger.info("Getting cached doc content", extra={'extra_data': {'crate_name_query': crate_name}})
    try:
        # Find the directory (may have version suffix)
        matching_dirs = []
        if DOCS_CACHE_DIR.exists():
            for item in DOCS_CACHE_DIR.iterdir():
                if item.is_dir() and item.name.startswith(crate_name):
                    matching_dirs.append(item)
        
        if not matching_dirs:
            logger.warning("No cached doc found for crate", extra={'extra_data': {'crate_name_query': crate_name}})
            return f"No cached documentation found for {crate_name}"
        
        # Use the first matching directory
        doc_dir = matching_dirs[0]
        
        # Read the README.md if it exists
        readme_path = doc_dir / "README.md"
        if readme_path.exists():
            async with aiofiles.open(readme_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            return content
        else:
            # List available files
            files = [f.name for f in doc_dir.iterdir() if f.is_file()]
            return f"Documentation files in {doc_dir.name}:\n" + "\n".join(f"- {name}" for name in sorted(files))
    
    except Exception as e:
        logger.error(
            "Error reading cached docs", exc_info=True,
            extra={'extra_data': {'crate_name_query': crate_name}}
        )
        return f"Error reading cached docs: {str(e)}"


if __name__ == "__main__":
    import sys
    
    logger.info("Rust Docs Server starting up")
    
    # Check command line arguments for transport type
    if len(sys.argv) > 1:
        transport = sys.argv[1].lower()
        
        if transport == "sse":
            # Run with SSE transport
            logger.info("Running with SSE transport on http://127.0.0.1:8000")
            mcp.run(transport="sse", host="127.0.0.1", port=8000)
        elif transport == "http":
            # Run with HTTP transport
            logger.info("Running with HTTP transport on http://127.0.0.1:8000/mcp")
            mcp.run(transport="http", host="127.0.0.1", port=8000, path="/mcp")
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