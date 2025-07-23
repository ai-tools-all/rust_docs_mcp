#!/usr/bin/env python3
"""
Core business logic for the Rust documentation MCP server.

This module contains all the core implementation functions that provide
the actual functionality. These functions are pure business logic and
have no MCP dependencies, making them reusable and testable.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional

import aiofiles
from fastmcp import Context

from .parser import CargoLockParser
from .scraper import DocsRsScraper, load_cached_docs, save_docs_to_disk


async def read_cargo_lock_impl(file_path: str, docs_cache_dir: Path, logs_dir: Path, logger, ctx: Optional[Context] = None) -> Dict[str, str]:
    """
    Core implementation for reading and parsing a Cargo.lock file.
    
    Args:
        file_path: Path to the Cargo.lock file
        docs_cache_dir: Directory for documentation cache
        logs_dir: Directory for logs
        logger: Logger instance
        ctx: Optional FastMCP context for user feedback
        
    Returns:
        Dictionary mapping package names to their versions
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


async def fetch_crate_docs_impl(crate_name: str, version: str, docs_cache_dir: Path, logger, ctx: Optional[Context] = None, include_features: bool = False) -> Dict[str, str]:
    """
    Core implementation for fetching documentation for a specific Rust crate.
    First checks local cache, then fetches from docs.rs if not cached.
    
    Args:
        crate_name: Name of the crate
        version: Version of the crate
        docs_cache_dir: Directory for documentation cache
        logger: Logger instance
        ctx: Optional FastMCP context for user feedback
        include_features: If True, also fetch feature flags information
        
    Returns:
        Dictionary mapping module paths to their documentation content as markdown
    """
    if ctx:
        await ctx.info(f"Fetching documentation for {crate_name} v{version}")
    
    # First, try to load from cache
    cached_docs = await load_cached_docs(crate_name, version, docs_cache_dir, logger, ctx)
    if cached_docs:
        return cached_docs
    
    # If not cached, fetch from docs.rs
    try:
        async with DocsRsScraper() as scraper:
            docs = await scraper.fetch_crate_docs(crate_name, version, logger, ctx, include_features)
        
        if docs:
            if ctx:
                await ctx.info(f"Successfully fetched {len(docs)} documentation sections")
            logger.info(
                "Successfully fetched documentation sections",
                extra={'extra_data': {'crate': crate_name, 'version': version, 'section_count': len(docs)}}
            )
            
            # Automatically save to cache
            await save_docs_to_disk_impl(crate_name, version, docs, docs_cache_dir, logger, ctx)
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


async def save_docs_to_disk_impl(crate_name: str, version: str, docs: Dict[str, str], docs_cache_dir: Path, logger, ctx: Optional[Context] = None) -> str:
    """
    Core implementation for saving fetched documentation to local disk.
    
    Args:
        crate_name: Name of the crate
        version: Version of the crate
        docs: Dictionary of module_path -> markdown_content
        docs_cache_dir: Directory for documentation cache
        logger: Logger instance
        ctx: Optional FastMCP context for user feedback
        
    Returns:
        Path to the saved documentation directory
    """
    return await save_docs_to_disk(crate_name, version, docs, docs_cache_dir, logger, ctx)


async def fetch_and_save_project_docs_impl(cargo_lock_path: str, docs_cache_dir: Path, logger, ctx: Optional[Context] = None) -> Dict[str, str]:
    """
    Core implementation for the complete workflow: Read Cargo.lock, fetch docs for all dependencies, and save to disk.
    
    Args:
        cargo_lock_path: Path to the Cargo.lock file
        docs_cache_dir: Directory for documentation cache
        logger: Logger instance
        ctx: Optional FastMCP context for user feedback
        
    Returns:
        Dictionary mapping crate names to their saved documentation directory paths
    """
    if ctx:
        await ctx.info("Starting complete documentation fetch workflow")
    logger.info(
        "Starting complete documentation fetch workflow",
        extra={'extra_data': {'cargo_lock_path': cargo_lock_path}}
    )
    
    # Step 1: Read Cargo.lock
    dependencies = await read_cargo_lock_impl(cargo_lock_path, docs_cache_dir, Path("./logs"), logger, ctx)
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
        docs = await fetch_crate_docs_impl(crate_name, version, docs_cache_dir, logger, ctx)
        
        if docs:
            # Save to disk
            saved_path = await save_docs_to_disk_impl(crate_name, version, docs, docs_cache_dir, logger, ctx)
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


async def list_cached_documentation_impl(docs_cache_dir: Path, logger) -> List[str]:
    """
    Core implementation for listing cached documentation directories.
    
    Args:
        docs_cache_dir: Directory for documentation cache
        logger: Logger instance
        
    Returns:
        List of cached documentation directory names
    """
    logger.info("Executing list_cached_documentation_impl")

    cached_dirs = []
    if not docs_cache_dir.exists():
        logger.warning("Cache directory not found.", extra={'extra_data': {'path': str(docs_cache_dir)}})
        return []

    try:
        for item in docs_cache_dir.iterdir():
            if item.is_dir():
                cached_dirs.append(item.name)
        
        cached_dirs.sort()  # Sort for consistent output

        if cached_dirs:
            logger.info(f"Found {len(cached_dirs)} cached documentations.", extra={'extra_data': {'count': len(cached_dirs), 'dirs': cached_dirs}})
        else:
            logger.info("No cached documentation directories found.")

        return cached_dirs
    except Exception as e:
        logger.error("Failed to list cached documentation.", exc_info=True)
        return []


async def get_cached_doc_content_impl(crate_name: str, docs_cache_dir: Path, logger) -> str:
    """
    Core implementation for getting cached documentation content.
    
    Args:
        crate_name: Name of the crate to search for
        docs_cache_dir: Directory for documentation cache
        logger: Logger instance
        
    Returns:
        Content of the cached documentation or error message
    """
    logger.info("Getting cached doc content", extra={'extra_data': {'crate_name_query': crate_name}})
    try:
        # Find the directory (may have version suffix)
        matching_dirs = []
        if docs_cache_dir.exists():
            for item in docs_cache_dir.iterdir():
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