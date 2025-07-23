#!/usr/bin/env python3
"""
Web scraping module for fetching Rust documentation from docs.rs.

Provides functionality to scrape, parse, and convert documentation content
to markdown format, as well as cache management.
"""

import asyncio
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import aiofiles
import aiohttp
from bs4 import BeautifulSoup
from fastmcp import Context


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
    
    async def fetch_crate_docs(self, crate_name: str, version: str, logger, ctx: Optional[Context] = None, include_features: bool = False) -> Dict[str, str]:
        """
        Fetch documentation for a specific crate and version.
        Returns a dict of module_path -> markdown_content.
        
        Args:
            crate_name: Name of the crate
            version: Version of the crate  
            logger: Logger instance
            ctx: Optional FastMCP context
            include_features: If True, also fetch feature flags information
        """
        if ctx:
            await ctx.info(f"Fetching docs for {crate_name} v{version}")
        logger.info(
            "Fetching docs for crate", 
            extra={'extra_data': {'crate': crate_name, 'version': version}}
        )
        
        docs = {}
        base_url = f"https://docs.rs/{crate_name}/{version}/{crate_name}/"
        logger.info("Constructed base URL", extra={'extra_data': {'url': base_url}})
        
        try:
            # First, get the main crate page to find all modules
            async with self.session.get(base_url) as response:
                if response.status != 200:
                    if ctx:
                        await ctx.error(f"Failed to fetch {base_url}: HTTP {response.status}")
                    logger.error(
                        "Failed to fetch main crate page", 
                        extra={'extra_data': {'url': base_url, 'status': response.status, 'crate': crate_name, 'version': version}}
                    )
                    return docs
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Extract main crate documentation
                main_doc = self._extract_documentation(soup, f"{crate_name} (main)")
                if main_doc:
                    docs["index"] = main_doc
                
                # Find all module links
                module_links = self._find_module_links(soup, base_url)
                if module_links:
                    logger.info(
                        f"Found {len(module_links)} potential module links",
                        extra={'extra_data': {'crate': crate_name, 'version': version, 'count': len(module_links)}}
                    )
                
                # Fetch documentation for each module
                for module_path, module_url in module_links[:10]:  # Limit to first 10 modules
                    if ctx:
                        await ctx.info(f"Fetching module: {module_path}")
                    logger.info(
                        "Fetching module documentation",
                        extra={'extra_data': {'crate': crate_name, 'module_path': module_path, 'url': module_url}}
                    )
                    
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
                        logger.error(
                            "Error fetching module", exc_info=True,
                            extra={'extra_data': {'crate': crate_name, 'module_path': module_path, 'url': module_url}}
                        )
                        continue
                    
                    # Small delay to be respectful
                    await asyncio.sleep(0.5)
                
                # Fetch feature flags if requested
                if include_features:
                    features_doc = await self._fetch_feature_flags(crate_name, version, logger, ctx)
                    if features_doc:
                        docs["features"] = features_doc
        
        except Exception as e:
            if ctx:
                await ctx.error(f"Error fetching docs for {crate_name}: {str(e)}")
            logger.error(
                "General error during documentation fetch", exc_info=True,
                extra={'extra_data': {'crate': crate_name, 'version': version}}
            )
        
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
    
    async def _fetch_feature_flags(self, crate_name: str, version: str, logger, ctx: Optional[Context] = None) -> str:
        """
        Fetch feature flags information for a crate.
        
        Args:
            crate_name: Name of the crate
            version: Version of the crate
            logger: Logger instance
            ctx: Optional FastMCP context
            
        Returns:
            Markdown content of feature flags or empty string if not found
        """
        features_url = f"https://docs.rs/crate/{crate_name}/{version}/features"
        
        if ctx:
            await ctx.info(f"Fetching feature flags from {features_url}")
        logger.info(
            "Fetching feature flags",
            extra={'extra_data': {'crate': crate_name, 'version': version, 'url': features_url}}
        )
        
        try:
            async with self.session.get(features_url) as response:
                if response.status != 200:
                    logger.warning(
                        "Failed to fetch feature flags", 
                        extra={'extra_data': {'url': features_url, 'status': response.status}}
                    )
                    return ""
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                return self._parse_feature_flags(soup, crate_name)
        
        except Exception as e:
            logger.error(
                "Error fetching feature flags", exc_info=True,
                extra={'extra_data': {'crate': crate_name, 'version': version, 'url': features_url}}
            )
            return ""
    
    def _parse_feature_flags(self, soup: BeautifulSoup, crate_name: str) -> str:
        """
        Parse feature flags from the features page HTML.
        
        Args:
            soup: BeautifulSoup object of the features page
            crate_name: Name of the crate
            
        Returns:
            Markdown formatted feature flags information
        """
        markdown_parts = [f"# {crate_name} - Feature Flags\n"]
        
        # Look for feature flag sections
        feature_sections = soup.find_all(['div', 'section'], class_=lambda x: x and 'feature' in x.lower())
        
        if not feature_sections:
            # Try to find features in tables or lists
            tables = soup.find_all('table')
            for table in tables:
                headers = table.find_all('th')
                if any('feature' in th.get_text().lower() for th in headers):
                    feature_sections.append(table)
        
        if not feature_sections:
            # Look for any structured content that might contain features
            main_content = soup.find('main') or soup.find('div', class_='content') or soup.find('body')
            if main_content:
                feature_sections = [main_content]
        
        for section in feature_sections:
            # Extract feature information from tables
            tables = section.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                if not rows:
                    continue
                
                # Check if this looks like a features table
                header_row = rows[0]
                headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]
                
                if any(keyword in ' '.join(headers) for keyword in ['feature', 'name', 'description']):
                    markdown_parts.append("\n## Available Features\n")
                    
                    for row in rows[1:]:  # Skip header row
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            feature_name = cells[0].get_text(strip=True)
                            feature_desc = cells[1].get_text(strip=True)
                            
                            if feature_name and feature_desc:
                                markdown_parts.append(f"### `{feature_name}`")
                                markdown_parts.append(f"{feature_desc}\n")
            
            # Extract from lists
            lists = section.find_all(['ul', 'ol'])
            for ul in lists:
                items = ul.find_all('li')
                if items and any('feature' in item.get_text().lower() for item in items[:3]):
                    markdown_parts.append("\n## Feature List\n")
                    for li in items:
                        text = li.get_text(strip=True)
                        if text:
                            markdown_parts.append(f"- {text}")
                    markdown_parts.append("")
        
        # If no structured features found, try to extract any relevant text
        if len(markdown_parts) == 1:  # Only has the header
            content_divs = soup.find_all(['div', 'p'], string=lambda text: text and 'feature' in text.lower())
            if content_divs:
                markdown_parts.append("\n## Feature Information\n")
                for div in content_divs[:5]:  # Limit to first 5 relevant sections
                    text = div.get_text(strip=True)
                    if text and len(text) > 10:
                        markdown_parts.append(f"{text}\n")
        
        result = "\n".join(markdown_parts)
        return result if len(result.strip()) > len(f"# {crate_name} - Feature Flags") else ""


async def load_cached_docs(crate_name: str, version: str, docs_cache_dir: Path, logger, ctx: Optional[Context] = None) -> Optional[Dict[str, str]]:
    """
    Load documentation from local cache if available.
    
    Args:
        crate_name: Name of the crate
        version: Version of the crate
        docs_cache_dir: Path to the documentation cache directory
        logger: Logger instance
        ctx: Optional FastMCP context for logging
        
    Returns:
        Dictionary of module_path -> markdown_content if cached, None otherwise
    """
    crate_dir = docs_cache_dir / f"{crate_name}-{version}"
    
    if not crate_dir.exists():
        return None
    
    if ctx:
        await ctx.info(f"Found cached docs for {crate_name} v{version}")
    logger.info(
        "Loading documentation from cache",
        extra={'extra_data': {'crate': crate_name, 'version': version, 'path': str(crate_dir)}}
    )
    
    try:
        docs = {}
        for file_path in crate_dir.glob("*.md"):
            if file_path.name == "README.md":
                continue  # Skip the index file
            
            module_name = file_path.stem
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            docs[module_name] = content
        
        if ctx:
            await ctx.info(f"Loaded {len(docs)} cached documentation sections")
        logger.info(
            "Successfully loaded cached documentation",
            extra={'extra_data': {'crate': crate_name, 'version': version, 'section_count': len(docs)}}
        )
        return docs
    
    except Exception as e:
        if ctx:
            await ctx.error(f"Error loading cached docs: {str(e)}")
        logger.error(
            "Error loading cached documentation", exc_info=True,
            extra={'extra_data': {'crate': crate_name, 'version': version}}
        )
        return None


async def save_docs_to_disk(crate_name: str, version: str, docs: Dict[str, str], docs_cache_dir: Path, logger, ctx: Optional[Context] = None) -> str:
    """
    Save fetched documentation to local disk as markdown files.
    
    Args:
        crate_name: Name of the crate
        version: Version of the crate
        docs: Dictionary of module_path -> markdown_content
        docs_cache_dir: Path to the documentation cache directory
        logger: Logger instance
        ctx: Optional FastMCP context for logging
        
    Returns:
        Path to the saved documentation directory
    """
    if ctx:
        await ctx.info(f"Saving documentation for {crate_name} v{version} to disk")
    logger.info(
        "Saving documentation to disk",
        extra={'extra_data': {'crate': crate_name, 'version': version}}
    )
    
    try:
        # Create directory structure
        crate_dir = docs_cache_dir / f"{crate_name}-{version}"
        crate_dir.mkdir(exist_ok=True)
        logger.info("Created cache directory", extra={'extra_data': {'path': str(crate_dir)}})
        
        saved_files = []
        
        for module_path, content in docs.items():
            # Create safe filename
            safe_filename = re.sub(r'[<>:"/\\|?*]', '_', module_path)
            file_path = crate_dir / f"{safe_filename}.md"
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            saved_files.append(str(file_path))
            logger.info("Wrote module to file", extra={'extra_data': {'module': module_path, 'file_path': str(file_path)}})
        
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
        logger.info(
            "Successfully saved documentation files",
            extra={'extra_data': {'crate': crate_name, 'version': version, 'path': str(crate_dir), 'file_count': len(saved_files)}}
        )
        return str(crate_dir)
    
    except Exception as e:
        if ctx:
            await ctx.error(f"Error saving docs to disk: {str(e)}")
        logger.error(
            "Error saving docs to disk", exc_info=True,
            extra={'extra_data': {'crate': crate_name, 'version': version}}
        )
        return ""