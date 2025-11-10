"""
Skill code templates.
Provides base templates for different types of skills.
"""

from typing import Dict, Any
from datetime import datetime


class SkillTemplates:
    """Manages code templates for skill generation."""
    
    def __init__(self):
        self.templates = self._load_templates()
    
    def get_base_template(self) -> str:
        """Get the base skill template."""
        return self.templates["base"]
    
    def get_template_for_type(self, skill_type: str) -> str:
        """Get template for specific skill type."""
        return self.templates.get(skill_type, self.templates["base"])
    
    def get_all_templates(self) -> Dict[str, str]:
        """Get all available templates."""
        return self.templates.copy()
    
    def _load_templates(self) -> Dict[str, str]:
        """Load all skill templates."""
        
        return {
            "base": '''
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

logger = logging.getLogger(__name__)

async def execute_skill(request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Base skill template.
    
    Args:
        request: The user's request string
        context: Additional context information
        
    Returns:
        Dict containing the result and metadata
    """
    if context is None:
        context = {}
    
    try:
        # Implementation goes here
        result = "Skill executed successfully"
        
        return {
            "success": True,
            "result": result,
            "metadata": {
                "skill_name": "base_skill",
                "execution_time": 0.0,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Skill execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "metadata": {
                "skill_name": "base_skill",
                "error_type": type(e).__name__
            }
        }
''',
            
            "web_scraping": '''
import logging
import aiohttp
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

async def execute_skill(request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Web scraping skill template.
    
    Args:
        request: The user's request string (should contain URL)
        context: Additional context including headers, selectors, etc.
        
    Returns:
        Dict containing scraped data and metadata
    """
    if context is None:
        context = {}
    
    try:
        # Extract URL from request or context
        url = context.get("url") or extract_url_from_request(request)
        
        if not url:
            raise ValueError("No URL provided for scraping")
        
        # Setup headers
        headers = context.get("headers", {
            "User-Agent": "Mozilla/5.0 (compatible; HappyOS-Bot/1.0)"
        })
        
        # Perform scraping
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: {response.reason}")
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract data based on selectors
                selectors = context.get("selectors", {})
                scraped_data = {}
                
                for key, selector in selectors.items():
                    elements = soup.select(selector)
                    scraped_data[key] = [elem.get_text(strip=True) for elem in elements]
                
                # If no selectors provided, extract basic info
                if not scraped_data:
                    scraped_data = {
                        "title": soup.title.string if soup.title else "",
                        "text_content": soup.get_text()[:1000]  # First 1000 chars
                    }
        
        return {
            "success": True,
            "result": scraped_data,
            "metadata": {
                "skill_name": "web_scraping",
                "url": url,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Web scraping failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "metadata": {
                "skill_name": "web_scraping",
                "error_type": type(e).__name__
            }
        }

def extract_url_from_request(request: str) -> Optional[str]:
    """Extract URL from user request."""
    import re
    url_pattern = r'https?://[^\s]+'
    match = re.search(url_pattern, request)
    return match.group(0) if match else None
''',
            
            "data_processing": '''
import logging
import pandas as pd
import json
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

logger = logging.getLogger(__name__)

async def execute_skill(request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Data processing skill template.
    
    Args:
        request: The user's request string describing the processing needed
        context: Additional context including data, operations, etc.
        
    Returns:
        Dict containing processed data and metadata
    """
    if context is None:
        context = {}
    
    try:
        # Get data from context
        data = context.get("data")
        if not data:
            raise ValueError("No data provided for processing")
        
        # Determine data format and convert to DataFrame if needed
        if isinstance(data, str):
            # Try to parse as JSON
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON data format")
        
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        else:
            raise ValueError("Unsupported data format")
        
        # Perform operations based on request
        operations = context.get("operations", [])
        
        for operation in operations:
            op_type = operation.get("type")
            
            if op_type == "filter":
                column = operation.get("column")
                value = operation.get("value")
                df = df[df[column] == value]
            
            elif op_type == "sort":
                column = operation.get("column")
                ascending = operation.get("ascending", True)
                df = df.sort_values(by=column, ascending=ascending)
            
            elif op_type == "group":
                column = operation.get("column")
                agg_func = operation.get("function", "count")
                df = df.groupby(column).agg(agg_func)
            
            elif op_type == "select":
                columns = operation.get("columns", [])
                df = df[columns]
        
        # Convert result back to appropriate format
        result = df.to_dict('records') if len(df) > 1 else df.to_dict('records')[0] if len(df) == 1 else {}
        
        return {
            "success": True,
            "result": result,
            "metadata": {
                "skill_name": "data_processing",
                "rows_processed": len(df),
                "operations_applied": len(operations),
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Data processing failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "metadata": {
                "skill_name": "data_processing",
                "error_type": type(e).__name__
            }
        }
''',
            
            "api_integration": '''
import logging
import aiohttp
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

async def execute_skill(request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    API integration skill template.
    
    Args:
        request: The user's request string
        context: Additional context including API details, auth, etc.
        
    Returns:
        Dict containing API response and metadata
    """
    if context is None:
        context = {}
    
    try:
        # Get API configuration
        api_url = context.get("api_url")
        method = context.get("method", "GET").upper()
        headers = context.get("headers", {})
        params = context.get("params", {})
        data = context.get("data")
        
        if not api_url:
            raise ValueError("No API URL provided")
        
        # Add authentication if provided
        auth = context.get("auth")
        if auth:
            if auth.get("type") == "bearer":
                headers["Authorization"] = f"Bearer {auth.get('token')}"
            elif auth.get("type") == "api_key":
                headers[auth.get("header", "X-API-Key")] = auth.get("key")
        
        # Make API request with retry logic
        max_retries = context.get("max_retries", 3)
        retry_delay = context.get("retry_delay", 1)
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method=method,
                        url=api_url,
                        headers=headers,
                        params=params,
                        json=data if method in ["POST", "PUT", "PATCH"] else None
                    ) as response:
                        
                        response_data = await response.json() if response.content_type == "application/json" else await response.text()
                        
                        if response.status >= 400:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay)
                                continue
                            else:
                                raise Exception(f"API request failed: {response.status} {response.reason}")
                        
                        return {
                            "success": True,
                            "result": response_data,
                            "metadata": {
                                "skill_name": "api_integration",
                                "api_url": api_url,
                                "method": method,
                                "status_code": response.status,
                                "attempt": attempt + 1,
                                "timestamp": datetime.now().isoformat()
                            }
                        }
                        
            except aiohttp.ClientError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    raise e
        
    except Exception as e:
        logger.error(f"API integration failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "metadata": {
                "skill_name": "api_integration",
                "error_type": type(e).__name__
            }
        }
''',
            
            "file_operations": '''
import logging
import aiofiles
import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

async def execute_skill(request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    File operations skill template.
    
    Args:
        request: The user's request string describing the file operation
        context: Additional context including file paths, operations, etc.
        
    Returns:
        Dict containing operation result and metadata
    """
    if context is None:
        context = {}
    
    try:
        operation = context.get("operation", "read")
        file_path = context.get("file_path")
        
        if not file_path:
            raise ValueError("No file path provided")
        
        file_path = Path(file_path)
        
        # Validate file path for security
        if not is_safe_path(file_path):
            raise ValueError("Unsafe file path")
        
        if operation == "read":
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Try to parse as JSON if requested
            if context.get("parse_json", False):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    pass  # Keep as string if not valid JSON
            
            result = {"content": content, "size": file_path.stat().st_size}
        
        elif operation == "write":
            content = context.get("content", "")
            
            # Create directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to JSON string if content is dict/list
            if isinstance(content, (dict, list)):
                content = json.dumps(content, indent=2)
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            result = {"bytes_written": len(content), "file_path": str(file_path)}
        
        elif operation == "append":
            content = context.get("content", "")
            
            async with aiofiles.open(file_path, 'a', encoding='utf-8') as f:
                await f.write(content)
            
            result = {"bytes_appended": len(content), "file_path": str(file_path)}
        
        elif operation == "delete":
            if file_path.exists():
                file_path.unlink()
                result = {"deleted": True, "file_path": str(file_path)}
            else:
                result = {"deleted": False, "reason": "File not found"}
        
        else:
            raise ValueError(f"Unsupported operation: {operation}")
        
        return {
            "success": True,
            "result": result,
            "metadata": {
                "skill_name": "file_operations",
                "operation": operation,
                "file_path": str(file_path),
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"File operation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "metadata": {
                "skill_name": "file_operations",
                "error_type": type(e).__name__
            }
        }

def is_safe_path(file_path: Path) -> bool:
    """Check if file path is safe (no directory traversal)."""
    try:
        # Resolve the path and check if it's within allowed directories
        resolved = file_path.resolve()
        # Add your allowed directories here
        allowed_dirs = [Path.cwd(), Path("/tmp"), Path("/home/mr/Dokument/filee.tar")]

        return any(str(resolved).startswith(str(allowed_dir.resolve())) for allowed_dir in allowed_dirs)
    except Exception:
        return False
'''
        }


# Global templates instance
skill_templates = SkillTemplates()