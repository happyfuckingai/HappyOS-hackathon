"""
Dynamically imports skills for the self-building orchestrator.
"""
import os
import importlib
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def import_skills(skill_dirs: List[str]) -> List[Dict[str, Any]]:
    """
    Dynamically import skills from specified directories.
    
    Args:
        skill_dirs: List of directories to search for skills
        
    Returns:
        List of imported skill modules
    """
    imported_skills = []
    for skill_dir in skill_dirs:
        for root, _, files in os.walk(skill_dir):
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    module_name = file[:-3]
                    module_path = os.path.join(root, file)
                    try:
                        spec = importlib.util.spec_from_file_location(module_name, module_path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        imported_skills.append(module)
                        logger.info(f"Successfully imported skill: {module_name}")
                    except Exception as e:
                        logger.error(f"Failed to import skill {module_name}: {e}")
    return imported_skills
