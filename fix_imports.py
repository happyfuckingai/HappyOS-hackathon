#!/usr/bin/env python3
"""
Script to fix imports after moving modules from inspiration/core to backend/core
"""

import os
import re
from pathlib import Path

# Define import replacements
REPLACEMENTS = [
    # Self-building imports
    (r'from app\.core\.self_building', 'from backend.core.self_building'),
    (r'from app\.core\.code_generation', 'from backend.core.code_generation'),
    (r'from app\.core\.component_generation', 'from backend.core.component_generation'),
    (r'from app\.core\.error_handler', 'from backend.core.error_handler'),
    (r'from app\.core\.skill_executor', 'from backend.core.skill_executor'),
    
    # Config and LLM imports
    (r'from app\.config\.settings', 'from backend.core.settings'),
    (r'from app\.llm\.router', 'from backend.core.llm.router'),
    
    # Other core imports
    (r'from app\.core\.config\.settings', 'from backend.core.settings'),
]

def fix_file(filepath):
    """Fix imports in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply all replacements
        for pattern, replacement in REPLACEMENTS:
            content = re.sub(pattern, replacement, content)
        
        # Only write if changes were made
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Fixed: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"❌ Error fixing {filepath}: {e}")
        return False

def fix_directory(directory):
    """Fix all Python files in a directory recursively"""
    fixed_count = 0
    
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != '__pycache__']
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if fix_file(filepath):
                    fixed_count += 1
    
    return fixed_count

if __name__ == '__main__':
    print("🔧 Fixing imports in moved modules...")
    print()
    
    directories = [
        'backend/core/self_building',
        'backend/core/code_generation',
        'backend/core/component_generation',
    ]
    
    files = [
        'backend/core/error_handler.py',
        'backend/core/skill_executor.py',
    ]
    
    total_fixed = 0
    
    # Fix directories
    for directory in directories:
        if os.path.exists(directory):
            print(f"📁 Processing {directory}...")
            count = fix_directory(directory)
            total_fixed += count
            print(f"   Fixed {count} files")
        else:
            print(f"⚠️  Directory not found: {directory}")
    
    # Fix individual files
    for filepath in files:
        if os.path.exists(filepath):
            if fix_file(filepath):
                total_fixed += 1
        else:
            print(f"⚠️  File not found: {filepath}")
    
    print()
    print(f"✨ Done! Fixed {total_fixed} files total")
