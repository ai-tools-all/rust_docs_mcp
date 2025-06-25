#!/usr/bin/env python3
"""
Parsing utilities for Rust project files.

Provides functionality to parse and extract information from Cargo.lock files
and other Rust project configuration files.
"""

from typing import Dict


class CargoLockParser:
    """Parser for Cargo.lock files to extract dependency information."""
    
    @staticmethod
    def parse_cargo_lock(content: str) -> Dict[str, str]:
        """
        Parse Cargo.lock content and return a dict of package -> version.
        
        Args:
            content: String content of the Cargo.lock file
            
        Returns:
            Dictionary mapping package names to their versions
        """
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