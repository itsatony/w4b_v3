#!/usr/bin/env python3
"""
Utility script to check for potentially missing imports in Python files.

Usage:
    python check_imports.py <path_to_python_file>
"""

import sys
import os
import ast
import importlib

def find_potential_missing_imports(file_path):
    """
    Analyze a Python file to find potentially missing imports.
    
    Args:
        file_path: Path to the Python file to analyze
        
    Returns:
        List of potentially missing imports
    """
    try:
        with open(file_path, 'r') as f:
            code = f.read()
        
        # Parse the code
        tree = ast.parse(code)
        
        # Track imported names
        imported_names = set()
        
        # Track defined names (functions, classes, variables at module level)
        defined_names = set()
        
        # Track names used
        used_names = set()
        
        # Find imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imported_names.add(name.name)
                    if name.asname:
                        imported_names.add(name.asname)
            elif isinstance(node, ast.ImportFrom):
                module = node.module
                for name in node.names:
                    if name.name == '*':
                        # Can't track star imports reliably
                        print(f"Warning: Star import found: from {module} import *")
                    else:
                        imported_names.add(name.name)
                        if name.asname:
                            imported_names.add(name.asname)
            
            # Track defined names
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                defined_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)
            
            # Track name usage
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
        
        # Find potentially missing imports
        potential_missing = used_names - imported_names - defined_names - {'True', 'False', 'None'}
        
        # Filter out builtins
        builtins = dir(__builtins__)
        genuine_missing = [name for name in potential_missing if name not in builtins]
        
        return genuine_missing
        
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return []

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path_to_python_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    missing = find_potential_missing_imports(file_path)
    
    if missing:
        print(f"Potentially missing imports in {file_path}:")
        for name in sorted(missing):
            print(f"  - {name}")
    else:
        print(f"No potentially missing imports found in {file_path}")
