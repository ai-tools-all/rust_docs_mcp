#!/usr/bin/env python3
"""
FastMCP server for Rust documentation management.

This server provides tools to:
1. Read Cargo.lock files and extract dependency versions
2. Fetch documentation from docs.rs by scraping content
3. Store scraped documentation as markdown files locally

Usage:
    python rust_docs_server.py
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import aiofiles
import aiohttp
from bs4 import BeautifulSoup
from fastmcp import FastMCP, Context

# Initialize the FastMCP server
mcp = FastMCP("Rust Docs Server 🦀")

# Configuration
DOCS_CACHE_DIR = Path("./rust_docs_cache")
DOCS_CACHE_DIR.mkdir(exist_ok=True)


class CargoLockParser:
    """Parser for Cargo.lock files to extract dependency information."""
    
    @staticmethod
    def parse_cargo_lock(content: str) -> Dict[str, str]:
        """Parse Cargo.lock content and return a dict of package -> version."""
        dependencies = {}
        
        # Split into package sections
        sections = content.split('\n\n')
        
        for section in sections:
            if section.strip().startswith('[[package]]'):
                lines = section.strip().split('\n')
                name = None
                version = None
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('name = '):
                        name = line.split(' = ')[1].strip('"')
                    elif line.startswith('version = '):
                        version = line.split(' = ')[1].strip('"')
                
                if name and version:
                    dependencies[name] = version
        
        return dependencies


class DocsRsScraper:
    """Scraper for fetching documentation from docs.rs."""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'FastMCP-RustDocs/1.0 (Educational Tool)'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_crate_docs(self, crate_name: str, version: str, ctx: Optional[Context] = None) -> Dict[str, str]:
        """
        Fetch documentation for a specific crate and version.
        Returns a dict of module_path -> markdown_content.
        """
        if ctx:
            await ctx.info(f"Fetching docs for {crate_name} v{version}")
        
        docs = {}
        base_url = f"https://docs.rs/{crate_name}/{version}/{crate_name}/"
        
        try:
            # First, get the main crate page to find all modules
            async with self.session.get(base_url) as response:
                if response.status != 200:
                    if ctx:
                        await ctx.error(f"Failed to fetch {base_url}: HTTP {response.status}")
                    return docs
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Extract main crate documentation
                main_doc = self._extract_documentation(soup, f"{crate_name} (main)")
                if main_doc:
                    docs["index"] = main_doc
                
                # Find all module links
                module_links = self._find_module_links(soup, base_url)
                
                # Fetch documentation for each module
                for module_path, module_url in module_links[:10]:  # Limit to first 10 modules
                    if ctx:
                        await ctx.info(f"Fetching module: {module_path}")
                    
                    try:
                        async with self.session.get(module_url) as mod_response:
                            if mod_response.status == 200:
                                mod_content = await mod_response.text()
                                mod_soup = BeautifulSoup(mod_content, 'html.parser')
                                mod_doc = self._extract_documentation(mod_soup, module_path)
                                if mod_doc:
                                    docs[module_path] = mod_doc
                    except Exception as e:
                        if ctx:
                            await ctx.error(f"Error fetching module {module_path}: {str(e)}")
                        continue
                    
                    # Small delay to be respectful
                    await asyncio.sleep(0.5)
        
        except Exception as e:
            if ctx:
                await ctx.error(f"Error fetching docs for {crate_name}: {str(e)}")
        
        return docs
    
    def _find_module_links(self, soup: BeautifulSoup, base_url: str) -> List[Tuple[str, str]]:
        """Find all module links in the documentation page."""
        links = []
        
        # Look for module links in the sidebar or main content
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if href and ('/' in href or href.endswith('.html')):
                # Convert relative URLs to absolute
                full_url = urljoin(base_url, href)
                
                # Extract module name from the link text or URL
                module_name = link.get_text(strip=True) or href.split('/')[-1].replace('.html', '')
                
                if module_name and not module_name.startswith('http'):
                    links.append((module_name, full_url))
        
        return links
    
    def _extract_documentation(self, soup: BeautifulSoup, title: str) -> str:
        """Extract and convert documentation content to markdown."""
        markdown_parts = [f"# {title}\n"]
        
        # Find the main documentation content div
        main_content = soup.find('main') or soup.find('div', class_='docblock') or soup.find('div', id='main')
        
        if not main_content:
            return ""
        
        # Extract and convert different elements
        for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'pre', 'code', 'ul', 'ol', 'li']):
            if element.name.startswith('h'):
                level = int(element.name[1])
                markdown_parts.append(f"\n{'#' * level} {element.get_text(strip=True)}\n")
            
            elif element.name == 'p':
                text = element.get_text(strip=True)
                if text:
                    markdown_parts.append(f"{text}\n")
            
            elif element.name == 'pre':
                code_text = element.get_text()
                markdown_parts.append(f"```rust\n{code_text}\n```\n")
            
            elif element.name == 'code' and element.parent.name != 'pre':
                code_text = element.get_text()
                markdown_parts.append(f"`{code_text}`")
            
            elif element.name in ['ul', 'ol']:
                for li in element.find_all('li', recursive=False):
                    li_text = li.get_text(strip=True)
                    if li_text:
                        marker = '-' if element.name == 'ul' else '1.'
                        markdown_parts.append(f"{marker} {li_text}\n")
                markdown_parts.append("")
        
        return "\n".join(markdown_parts)


# Core logic functions (not decorated with @mcp.tool)
async def _read_cargo_lock_impl(file_path: str, ctx: Optional[Context] = None) -> Dict[str, str]:
    """
    Core implementation for reading and parsing a Cargo.lock file.
    """
    if ctx:
        await ctx.info(f"Reading Cargo.lock file: {file_path}")
    
    try:
        path = Path(file_path).expanduser().resolve()
        
        if not path.exists():
            if ctx:
                await ctx.error(f"Cargo.lock file not found: {path}")
            return {}
        
        if not path.name == "Cargo.lock":
            if ctx:
                await ctx.error(f"File must be named Cargo.lock, got: {path.name}")
            return {}
        
        async with aiofiles.open(path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        parser = CargoLockParser()
        dependencies = parser.parse_cargo_lock(content)
        
        if ctx:
            await ctx.info(f"Found {len(dependencies)} dependencies")
        return dependencies
    
    except Exception as e:
        if ctx:
            await ctx.error(f"Error reading Cargo.lock: {str(e)}")
        return {}


async def _fetch_crate_docs_impl(crate_name: str, version: str, ctx: Optional[Context] = None) -> Dict[str, str]:
    """
    Core implementation for fetching documentation for a specific Rust crate.
    """
    if ctx:
        await ctx.info(f"Fetching documentation for {crate_name} v{version}")
    
    try:
        async with DocsRsScraper() as scraper:
            docs = await scraper.fetch_crate_docs(crate_name, version, ctx)
        
        if docs:
            if ctx:
                await ctx.info(f"Successfully fetched {len(docs)} documentation sections")
        else:
            if ctx:
                await ctx.error(f"No documentation found for {crate_name} v{version}")
        
        return docs
    
    except Exception as e:
        if ctx:
            await ctx.error(f"Error fetching docs: {str(e)}")
        return {}


async def _save_docs_to_disk_impl(crate_name: str, version: str, docs: Dict[str, str], ctx: Optional[Context] = None) -> str:
    """
    Core implementation for saving fetched documentation to local disk.
    """
    if ctx:
        await ctx.info(f"Saving documentation for {crate_name} v{version} to disk")
    
    try:
        # Create directory structure
        crate_dir = DOCS_CACHE_DIR / f"{crate_name}-{version}"
        crate_dir.mkdir(exist_ok=True)
        
        saved_files = []
        
        for module_path, content in docs.items():
            # Create safe filename
            safe_filename = re.sub(r'[<>:"/\\|?*]', '_', module_path)
            file_path = crate_dir / f"{safe_filename}.md"
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            saved_files.append(str(file_path))
        
        # Create an index file with metadata
        index_content = f"""# {crate_name} v{version} Documentation

Generated from docs.rs

## Modules

"""
        for module_path in docs.keys():
            safe_filename = re.sub(r'[<>:"/\\|?*]', '_', module_path)
            index_content += f"- [{module_path}](./{safe_filename}.md)\n"
        
        index_path = crate_dir / "README.md"
        async with aiofiles.open(index_path, 'w', encoding='utf-8') as f:
            await f.write(index_content)
        
        if ctx:
            await ctx.info(f"Saved {len(saved_files)} documentation files to {crate_dir}")
        return str(crate_dir)
    
    except Exception as e:
        if ctx:
            await ctx.error(f"Error saving docs to disk: {str(e)}")
        return ""


async def _fetch_and_save_project_docs_impl(cargo_lock_path: str, ctx: Optional[Context] = None) -> Dict[str, str]:
    """
    Core implementation for the complete workflow: Read Cargo.lock, fetch docs for all dependencies, and save to disk.
    """
    if ctx:
        await ctx.info("Starting complete documentation fetch workflow")
    
    # Step 1: Read Cargo.lock
    dependencies = await _read_cargo_lock_impl(cargo_lock_path, ctx)
    if not dependencies:
        return {}
    
    # Step 2: Fetch and save docs for each dependency
    saved_paths = {}
    
    for crate_name, version in list(dependencies.items())[:5]:  # Limit to first 5 for demo
        if ctx:
            await ctx.info(f"Processing {crate_name} v{version}")
        
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
    return saved_paths


# MCP tool wrappers
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
    return await _save_docs_to_disk_impl(crate_name, version, docs, ctx)


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
        return f"Error listing cached docs: {str(e)}"


@mcp.resource("docs://cache/{crate_name}")
async def get_cached_doc_content(crate_name: str) -> str:
    """Get the content of a cached documentation directory."""
    try:
        # Find the directory (may have version suffix)
        matching_dirs = []
        if DOCS_CACHE_DIR.exists():
            for item in DOCS_CACHE_DIR.iterdir():
                if item.is_dir() and item.name.startswith(crate_name):
                    matching_dirs.append(item)
        
        if not matching_dirs:
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
        return f"Error reading cached docs: {str(e)}"


if __name__ == "__main__":
    import sys
    
    # Check command line arguments for transport type
    if len(sys.argv) > 1:
        transport = sys.argv[1].lower()
        
        if transport == "sse":
            # Run with SSE transport
            mcp.run(transport="sse", host="127.0.0.1", port=8000)
        elif transport == "http":
            # Run with HTTP transport
            mcp.run(transport="http", host="127.0.0.1", port=8000, path="/mcp")
        elif transport == "stdio":
            # Run with STDIO transport (default)
            mcp.run(transport="stdio")
        else:
            print("Usage: python rust_docs_server.py [stdio|sse|http]")
            print("Default: stdio")
            mcp.run()
    else:
        # Default to STDIO
        mcp.run()