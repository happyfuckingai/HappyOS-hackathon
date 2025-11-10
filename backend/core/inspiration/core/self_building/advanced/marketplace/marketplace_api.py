"""
External Skills Marketplace - Fetches and integrates skills from external sources.
Supports Git repos, APIs, and P2P networks with validation and sandboxing.
"""

import logging
import asyncio
import json
import hashlib
import tempfile
import shutil
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

# Optional git import with error handling
try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    git = None
    GIT_AVAILABLE = False
    logging.getLogger(__name__).warning("GitPython not available. Git repository functionality will be disabled.")

from app.config.settings import get_settings
from app.core.error_handler import safe_execute

from ...discovery.component_scanner import ComponentInfo
from ...registry.dynamic_registry import dynamic_registry
from ...intelligence.audit_logger import audit_logger

logger = logging.getLogger(__name__)
settings = get_settings()


class SourceType(Enum):
    """Types of external sources."""
    GIT_REPO = "git_repo"
    HTTP_API = "http_api"
    FILE_UPLOAD = "file_upload"
    P2P_NETWORK = "p2p_network"
    MARKETPLACE_API = "marketplace_api"


class ValidationStatus(Enum):
    """Validation status of external skills."""
    PENDING = "pending"
    VALIDATING = "validating"
    APPROVED = "approved"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"


@dataclass
class ExternalSource:
    """Configuration for an external source."""
    name: str
    source_type: SourceType
    url: str
    credentials: Dict[str, str] = field(default_factory=dict)
    trusted: bool = False
    auto_sync: bool = False
    sync_interval: int = 3600  # seconds
    last_sync: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalSkill:
    """Represents a skill from an external source."""
    skill_id: str
    name: str
    description: str
    source: ExternalSource
    version: str
    author: str
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    file_path: Optional[str] = None
    file_hash: Optional[str] = None
    validation_status: ValidationStatus = ValidationStatus.PENDING
    validation_results: Dict[str, Any] = field(default_factory=dict)
    downloaded_at: Optional[datetime] = None
    installed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketplaceStats:
    """Statistics for the marketplace."""
    total_sources: int = 0
    total_skills: int = 0
    approved_skills: int = 0
    rejected_skills: int = 0
    installed_skills: int = 0
    last_sync: Optional[datetime] = None


class ExternalMarketplace:
    """
    Manages external skills marketplace integration.
    Fetches, validates, and installs skills from various sources.
    """
    
    def __init__(self):
        self.sources: Dict[str, ExternalSource] = {}
        self.external_skills: Dict[str, ExternalSkill] = {}
        self.marketplace_dir = Path("/home/mr/Dokument/filee.tar/happyos/marketplace")
        self.downloads_dir = self.marketplace_dir / "downloads"
        self.quarantine_dir = self.marketplace_dir / "quarantine"
        
        # Ensure directories exist
        self.marketplace_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        
        # Security settings
        self.security_config = {
            "max_file_size": 10 * 1024 * 1024,  # 10MB
            "allowed_extensions": {".py", ".json", ".md", ".txt", ".yml", ".yaml"},
            "blocked_patterns": [
                r"import\s+os\s*\.\s*system",
                r"subprocess\s*\.\s*call",
                r"eval\s*\(",
                r"exec\s*\(",
                r"__import__",
                r"open\s*\(\s*['\"][^'\"]*['\"],\s*['\"]w",  # Write file operations
            ],
            "max_validation_time": 300,  # 5 minutes
            "quarantine_suspicious": True
        }
        
        # Statistics
        self.stats = MarketplaceStats()
    
    async def initialize(self):
        """Initialize the marketplace system."""
        
        try:
            # Load existing sources and skills
            await self._load_marketplace_data()
            
            # Set up default sources
            await self._setup_default_sources()
            
            # Start background sync task
            asyncio.create_task(self._background_sync_task())
            
            logger.info("External marketplace initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize marketplace: {e}")
            raise
    
    async def add_source(self, source: ExternalSource) -> bool:
        """Add a new external source."""
        
        try:
            # Validate source
            if not await self._validate_source(source):
                logger.error(f"Source validation failed: {source.name}")
                return False
            
            # Add to sources
            self.sources[source.name] = source
            self.stats.total_sources += 1
            
            # Save configuration
            await self._save_marketplace_data()
            
            # Perform initial sync if auto_sync is enabled
            if source.auto_sync:
                await self.sync_source(source.name)
            
            logger.info(f"Added external source: {source.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding source: {e}")
            return False
    
    async def sync_source(self, source_name: str) -> Dict[str, Any]:
        """Sync skills from a specific source."""
        
        if source_name not in self.sources:
            return {"error": "Source not found"}
        
        source = self.sources[source_name]
        
        try:
            logger.info(f"Syncing source: {source_name}")
            
            if source.source_type == SourceType.GIT_REPO:
                result = await self._sync_git_repo(source)
            elif source.source_type == SourceType.HTTP_API:
                result = await self._sync_http_api(source)
            elif source.source_type == SourceType.MARKETPLACE_API:
                result = await self._sync_marketplace_api(source)
            else:
                result = {"error": f"Unsupported source type: {source.source_type}"}
            
            # Update last sync time
            source.last_sync = datetime.now()
            self.stats.last_sync = datetime.now()
            
            await self._save_marketplace_data()
            
            logger.info(f"Sync completed for {source_name}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error syncing source {source_name}: {e}")
            return {"error": str(e)}
    
    async def _sync_git_repo(self, source: ExternalSource) -> Dict[str, Any]:
        """Sync skills from a Git repository."""

        if not GIT_AVAILABLE:
            error_msg = "GitPython not available. Cannot sync from Git repositories."
            logger.error(error_msg)
            return {"error": error_msg}

        try:
            # Create temporary directory for cloning
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_dir = Path(temp_dir) / "repo"

                # Clone repository
                logger.debug(f"Cloning repository: {source.url}")
                repo = git.Repo.clone_from(source.url, repo_dir)
                
                # Find skill files
                skill_files = []
                for pattern in ["**/*.py", "**/skill_*.py", "**/skills/**/*.py"]:
                    skill_files.extend(repo_dir.glob(pattern))
                
                results = {
                    "found": len(skill_files),
                    "processed": 0,
                    "approved": 0,
                    "rejected": 0
                }
                
                # Process each skill file
                for skill_file in skill_files:
                    try:
                        skill = await self._process_skill_file(skill_file, source)
                        if skill:
                            results["processed"] += 1
                            if skill.validation_status == ValidationStatus.APPROVED:
                                results["approved"] += 1
                            else:
                                results["rejected"] += 1
                    except Exception as e:
                        logger.error(f"Error processing skill file {skill_file}: {e}")
                
                return results
                
        except Exception as e:
            logger.error(f"Error syncing Git repo: {e}")
            return {"error": str(e)}
    
    async def _sync_http_api(self, source: ExternalSource) -> Dict[str, Any]:
        """Sync skills from an HTTP API."""
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {}
                if "api_key" in source.credentials:
                    headers["Authorization"] = f"Bearer {source.credentials['api_key']}"
                
                async with session.get(source.url, headers=headers) as response:
                    if response.status != 200:
                        return {"error": f"HTTP {response.status}: {await response.text()}"}
                    
                    data = await response.json()
                    
                    # Process skills from API response
                    skills = data.get("skills", [])
                    
                    results = {
                        "found": len(skills),
                        "processed": 0,
                        "approved": 0,
                        "rejected": 0
                    }
                    
                    for skill_data in skills:
                        try:
                            skill = await self._process_api_skill(skill_data, source)
                            if skill:
                                results["processed"] += 1
                                if skill.validation_status == ValidationStatus.APPROVED:
                                    results["approved"] += 1
                                else:
                                    results["rejected"] += 1
                        except Exception as e:
                            logger.error(f"Error processing API skill: {e}")
                    
                    return results
                    
        except Exception as e:
            logger.error(f"Error syncing HTTP API: {e}")
            return {"error": str(e)}
    
    async def _sync_marketplace_api(self, source: ExternalSource) -> Dict[str, Any]:
        """Sync skills from a marketplace API."""
        
        # This would implement a standardized marketplace protocol
        # For now, delegate to HTTP API sync
        return await self._sync_http_api(source)
    
    async def _process_skill_file(self, file_path: Path, source: ExternalSource) -> Optional[ExternalSkill]:
        """Process a skill file from a source."""
        
        try:
            # Read file content
            content = file_path.read_text(encoding='utf-8')
            
            # Calculate hash
            file_hash = hashlib.sha256(content.encode()).hexdigest()
            
            # Check if we already have this skill
            existing_skill = None
            for skill in self.external_skills.values():
                if skill.file_hash == file_hash:
                    existing_skill = skill
                    break
            
            if existing_skill:
                logger.debug(f"Skill already exists: {file_path.name}")
                return existing_skill
            
            # Extract metadata from file
            metadata = await self._extract_skill_metadata(content, file_path)
            
            # Create skill object
            skill = ExternalSkill(
                skill_id=f"{source.name}_{file_path.stem}_{file_hash[:8]}",
                name=metadata.get("name", file_path.stem),
                description=metadata.get("description", ""),
                source=source,
                version=metadata.get("version", "1.0.0"),
                author=metadata.get("author", "Unknown"),
                tags=metadata.get("tags", []),
                dependencies=metadata.get("dependencies", []),
                file_hash=file_hash,
                downloaded_at=datetime.now(),
                metadata=metadata
            )
            
            # Download and validate
            downloaded_path = await self._download_skill_file(content, skill)
            if downloaded_path:
                skill.file_path = str(downloaded_path)
                
                # Validate skill
                await self._validate_skill(skill)
                
                # Store skill
                self.external_skills[skill.skill_id] = skill
                self.stats.total_skills += 1
                
                if skill.validation_status == ValidationStatus.APPROVED:
                    self.stats.approved_skills += 1
                else:
                    self.stats.rejected_skills += 1
                
                return skill
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing skill file: {e}")
            return None
    
    async def _process_api_skill(self, skill_data: Dict[str, Any], source: ExternalSource) -> Optional[ExternalSkill]:
        """Process a skill from API data."""
        
        try:
            # Download skill content
            download_url = skill_data.get("download_url")
            if not download_url:
                logger.error("No download URL in skill data")
                return None
            
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status != 200:
                        logger.error(f"Failed to download skill: HTTP {response.status}")
                        return None
                    
                    content = await response.text()
            
            # Calculate hash
            file_hash = hashlib.sha256(content.encode()).hexdigest()
            
            # Create skill object
            skill = ExternalSkill(
                skill_id=skill_data.get("id", f"{source.name}_{file_hash[:8]}"),
                name=skill_data.get("name", "Unknown"),
                description=skill_data.get("description", ""),
                source=source,
                version=skill_data.get("version", "1.0.0"),
                author=skill_data.get("author", "Unknown"),
                tags=skill_data.get("tags", []),
                dependencies=skill_data.get("dependencies", []),
                file_hash=file_hash,
                downloaded_at=datetime.now(),
                metadata=skill_data
            )
            
            # Download and validate
            downloaded_path = await self._download_skill_file(content, skill)
            if downloaded_path:
                skill.file_path = str(downloaded_path)
                
                # Validate skill
                await self._validate_skill(skill)
                
                # Store skill
                self.external_skills[skill.skill_id] = skill
                self.stats.total_skills += 1
                
                if skill.validation_status == ValidationStatus.APPROVED:
                    self.stats.approved_skills += 1
                else:
                    self.stats.rejected_skills += 1
                
                return skill
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing API skill: {e}")
            return None
    
    async def _extract_skill_metadata(self, content: str, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from skill file content."""
        
        metadata = {
            "name": file_path.stem,
            "description": "",
            "version": "1.0.0",
            "author": "Unknown",
            "tags": [],
            "dependencies": []
        }
        
        try:
            # Look for metadata in docstring
            import ast
            tree = ast.parse(content)
            module_docstring = ast.get_docstring(tree)
            
            if module_docstring:
                # Try to extract structured metadata
                lines = module_docstring.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('Name:'):
                        metadata["name"] = line.split(':', 1)[1].strip()
                    elif line.startswith('Description:'):
                        metadata["description"] = line.split(':', 1)[1].strip()
                    elif line.startswith('Version:'):
                        metadata["version"] = line.split(':', 1)[1].strip()
                    elif line.startswith('Author:'):
                        metadata["author"] = line.split(':', 1)[1].strip()
                    elif line.startswith('Tags:'):
                        tags_str = line.split(':', 1)[1].strip()
                        metadata["tags"] = [tag.strip() for tag in tags_str.split(',')]
            
            # Extract imports as dependencies
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not alias.name.startswith('_'):
                            metadata["dependencies"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and not node.module.startswith('_'):
                        metadata["dependencies"].append(node.module)
            
            # Remove duplicates and standard library modules
            standard_libs = {'os', 'sys', 'json', 'datetime', 'pathlib', 'typing', 'asyncio', 'logging'}
            metadata["dependencies"] = list(set(metadata["dependencies"]) - standard_libs)
            
        except Exception as e:
            logger.warning(f"Error extracting metadata: {e}")
        
        return metadata
    
    async def _download_skill_file(self, content: str, skill: ExternalSkill) -> Optional[Path]:
        """Download and save skill file."""
        
        try:
            # Check file size
            if len(content.encode()) > self.security_config["max_file_size"]:
                logger.error(f"Skill file too large: {skill.name}")
                return None
            
            # Create filename
            filename = f"{skill.skill_id}.py"
            file_path = self.downloads_dir / filename
            
            # Save file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.debug(f"Downloaded skill file: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error downloading skill file: {e}")
            return None
    
    async def _validate_skill(self, skill: ExternalSkill):
        """Validate a downloaded skill."""
        
        try:
            skill.validation_status = ValidationStatus.VALIDATING
            validation_results = {
                "syntax_check": False,
                "security_scan": False,
                "dependency_check": False,
                "sandbox_test": False,
                "issues": [],
                "warnings": []
            }
            
            if not skill.file_path:
                validation_results["issues"].append("No file path")
                skill.validation_status = ValidationStatus.REJECTED
                skill.validation_results = validation_results
                return
            
            # Read file content
            with open(skill.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 1. Syntax check
            try:
                compile(content, skill.file_path, 'exec')
                validation_results["syntax_check"] = True
            except SyntaxError as e:
                validation_results["issues"].append(f"Syntax error: {e}")
            
            # 2. Security scan
            security_issues = await self._security_scan(content)
            if not security_issues:
                validation_results["security_scan"] = True
            else:
                validation_results["issues"].extend(security_issues)
            
            # 3. Dependency check
            missing_deps = await self._check_dependencies(skill.dependencies)
            if not missing_deps:
                validation_results["dependency_check"] = True
            else:
                validation_results["warnings"].extend([f"Missing dependency: {dep}" for dep in missing_deps])
                validation_results["dependency_check"] = True  # Don't fail for missing deps
            
            # 4. Sandbox test (simplified)
            if validation_results["syntax_check"] and validation_results["security_scan"]:
                sandbox_result = await self._sandbox_test(skill)
                validation_results["sandbox_test"] = sandbox_result
                if not sandbox_result:
                    validation_results["issues"].append("Sandbox test failed")
            
            # Determine final status
            critical_checks = ["syntax_check", "security_scan"]
            if all(validation_results[check] for check in critical_checks):
                if skill.source.trusted or validation_results["sandbox_test"]:
                    skill.validation_status = ValidationStatus.APPROVED
                else:
                    skill.validation_status = ValidationStatus.QUARANTINED
                    # Move to quarantine
                    await self._quarantine_skill(skill)
            else:
                skill.validation_status = ValidationStatus.REJECTED
            
            skill.validation_results = validation_results
            
            # Log validation result
            await audit_logger.log_event(
                audit_logger.AuditEventType.COMPONENT_REGISTERED,
                component_name=skill.name,
                details={
                    "external_skill": True,
                    "validation_status": skill.validation_status.value,
                    "validation_results": validation_results,
                    "source": skill.source.name
                }
            )
            
            logger.info(f"Skill validation completed: {skill.name} - {skill.validation_status.value}")
            
        except Exception as e:
            logger.error(f"Error validating skill: {e}")
            skill.validation_status = ValidationStatus.REJECTED
            skill.validation_results = {"error": str(e)}
    
    async def _security_scan(self, content: str) -> List[str]:
        """Perform security scan on skill content."""
        
        issues = []
        
        try:
            import re
            
            # Check for blocked patterns
            for pattern in self.security_config["blocked_patterns"]:
                if re.search(pattern, content, re.IGNORECASE):
                    issues.append(f"Blocked pattern detected: {pattern}")
            
            # Check for suspicious imports
            suspicious_imports = ['subprocess', 'os.system', 'eval', 'exec']
            for imp in suspicious_imports:
                if imp in content:
                    issues.append(f"Suspicious import: {imp}")
            
            # Check for file operations
            file_ops = ['open(', 'file(', 'write(', 'remove(', 'delete(']
            for op in file_ops:
                if op in content:
                    issues.append(f"File operation detected: {op}")
            
            # Check for network operations
            network_ops = ['socket', 'urllib', 'requests', 'http']
            for op in network_ops:
                if op in content:
                    issues.append(f"Network operation detected: {op}")
            
        except Exception as e:
            logger.error(f"Error in security scan: {e}")
            issues.append(f"Security scan error: {e}")
        
        return issues
    
    async def _check_dependencies(self, dependencies: List[str]) -> List[str]:
        """Check if dependencies are available."""
        
        missing = []
        
        for dep in dependencies:
            try:
                __import__(dep)
            except ImportError:
                missing.append(dep)
        
        return missing
    
    async def _sandbox_test(self, skill: ExternalSkill) -> bool:
        """Test skill in sandbox environment."""
        
        try:
            # This is a simplified sandbox test
            # In production, this would use proper containerization
            
            if not skill.file_path:
                return False
            
            # Try to import the skill module
            import importlib.util
            spec = importlib.util.spec_from_file_location(skill.name, skill.file_path)
            if not spec or not spec.loader:
                return False
            
            module = importlib.util.module_from_spec(spec)
            
            # Load in a controlled environment
            try:
                spec.loader.exec_module(module)
                
                # Check if it has required functions
                if hasattr(module, 'execute_skill'):
                    return True
                else:
                    logger.warning(f"Skill {skill.name} missing execute_skill function")
                    return False
                    
            except Exception as e:
                logger.error(f"Error loading skill module: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error in sandbox test: {e}")
            return False
    
    async def _quarantine_skill(self, skill: ExternalSkill):
        """Move skill to quarantine."""
        
        try:
            if skill.file_path:
                quarantine_path = self.quarantine_dir / Path(skill.file_path).name
                shutil.move(skill.file_path, quarantine_path)
                skill.file_path = str(quarantine_path)
                
                logger.info(f"Skill quarantined: {skill.name}")
                
        except Exception as e:
            logger.error(f"Error quarantining skill: {e}")
    
    async def install_skill(self, skill_id: str) -> Dict[str, Any]:
        """Install an approved external skill."""
        
        if skill_id not in self.external_skills:
            return {"success": False, "error": "Skill not found"}
        
        skill = self.external_skills[skill_id]
        
        if skill.validation_status != ValidationStatus.APPROVED:
            return {"success": False, "error": f"Skill not approved: {skill.validation_status.value}"}
        
        try:
            # Copy skill to skills directory
            skills_dir = Path("/home/mr/Dokument/filee.tar/happyos/app/skills/external")
            skills_dir.mkdir(parents=True, exist_ok=True)
            
            skill_filename = f"{skill.name}.py"
            target_path = skills_dir / skill_filename
            
            shutil.copy2(skill.file_path, target_path)
            
            # Create component info
            component = ComponentInfo(
                name=skill.name,
                type="skills",
                path=str(target_path),
                module_name=f"app.skills.external.{skill.name}",
                last_modified=datetime.now(),
                metadata={
                    "external_skill": True,
                    "source": skill.source.name,
                    "author": skill.author,
                    "version": skill.version,
                    "skill_id": skill_id
                }
            )
            
            # Register with dynamic registry
            success = await dynamic_registry.register_component(component)
            
            if success:
                skill.installed = True
                self.stats.installed_skills += 1
                
                # Activate the skill
                await dynamic_registry.activate_component(skill.name)
                
                logger.info(f"Successfully installed external skill: {skill.name}")
                
                return {
                    "success": True,
                    "skill_name": skill.name,
                    "file_path": str(target_path)
                }
            else:
                return {"success": False, "error": "Failed to register skill"}
                
        except Exception as e:
            logger.error(f"Error installing skill: {e}")
            return {"success": False, "error": str(e)}
    
    async def _validate_source(self, source: ExternalSource) -> bool:
        """Validate an external source."""

        try:
            if source.source_type == SourceType.GIT_REPO:
                # Check if Git URL is accessible
                if not GIT_AVAILABLE:
                    logger.error("GitPython not available for repository validation")
                    return False
                # This is a simple check - in production, use more sophisticated validation
                return source.url.startswith(('https://', 'git://'))
            
            elif source.source_type == SourceType.HTTP_API:
                # Check if HTTP endpoint is accessible
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.head(source.url, timeout=10) as response:
                            return response.status < 400
                except:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating source: {e}")
            return False
    
    async def _setup_default_sources(self):
        """Set up default external sources."""
        
        # Add some default sources (examples)
        default_sources = [
            ExternalSource(
                name="happyos_community",
                source_type=SourceType.GIT_REPO,
                url="https://github.com/happyos/community-skills.git",
                trusted=True,
                auto_sync=True,
                sync_interval=3600
            ),
            ExternalSource(
                name="skills_marketplace",
                source_type=SourceType.HTTP_API,
                url="https://api.skills-marketplace.com/v1/skills",
                trusted=False,
                auto_sync=False
            )
        ]
        
        for source in default_sources:
            if source.name not in self.sources:
                await self.add_source(source)
    
    async def _background_sync_task(self):
        """Background task for automatic syncing."""
        
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                current_time = datetime.now()
                
                for source in self.sources.values():
                    if (source.auto_sync and 
                        (not source.last_sync or 
                         current_time - source.last_sync > timedelta(seconds=source.sync_interval))):
                        
                        logger.info(f"Auto-syncing source: {source.name}")
                        await self.sync_source(source.name)
                        
            except Exception as e:
                logger.error(f"Error in background sync task: {e}")
    
    async def _save_marketplace_data(self):
        """Save marketplace data to file."""
        
        try:
            data = {
                "sources": {
                    name: {
                        "name": source.name,
                        "source_type": source.source_type.value,
                        "url": source.url,
                        "trusted": source.trusted,
                        "auto_sync": source.auto_sync,
                        "sync_interval": source.sync_interval,
                        "last_sync": source.last_sync.isoformat() if source.last_sync else None,
                        "metadata": source.metadata
                    }
                    for name, source in self.sources.items()
                },
                "stats": {
                    "total_sources": self.stats.total_sources,
                    "total_skills": self.stats.total_skills,
                    "approved_skills": self.stats.approved_skills,
                    "rejected_skills": self.stats.rejected_skills,
                    "installed_skills": self.stats.installed_skills,
                    "last_sync": self.stats.last_sync.isoformat() if self.stats.last_sync else None
                }
            }
            
            config_path = self.marketplace_dir / "marketplace_config.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving marketplace data: {e}")
    
    async def _load_marketplace_data(self):
        """Load marketplace data from file."""
        
        try:
            config_path = self.marketplace_dir / "marketplace_config.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Load sources
                for source_data in data.get("sources", {}).values():
                    source = ExternalSource(
                        name=source_data["name"],
                        source_type=SourceType(source_data["source_type"]),
                        url=source_data["url"],
                        trusted=source_data.get("trusted", False),
                        auto_sync=source_data.get("auto_sync", False),
                        sync_interval=source_data.get("sync_interval", 3600),
                        last_sync=datetime.fromisoformat(source_data["last_sync"]) if source_data.get("last_sync") else None,
                        metadata=source_data.get("metadata", {})
                    )
                    self.sources[source.name] = source
                
                # Load stats
                stats_data = data.get("stats", {})
                self.stats = MarketplaceStats(
                    total_sources=stats_data.get("total_sources", 0),
                    total_skills=stats_data.get("total_skills", 0),
                    approved_skills=stats_data.get("approved_skills", 0),
                    rejected_skills=stats_data.get("rejected_skills", 0),
                    installed_skills=stats_data.get("installed_skills", 0),
                    last_sync=datetime.fromisoformat(stats_data["last_sync"]) if stats_data.get("last_sync") else None
                )
                
                logger.info(f"Loaded marketplace data: {len(self.sources)} sources")
                
        except Exception as e:
            logger.error(f"Error loading marketplace data: {e}")
    
    def list_skills(
        self, 
        status: Optional[ValidationStatus] = None,
        source_name: Optional[str] = None,
        installed_only: bool = False
    ) -> List[ExternalSkill]:
        """List external skills with optional filtering."""
        
        skills = list(self.external_skills.values())
        
        if status:
            skills = [s for s in skills if s.validation_status == status]
        
        if source_name:
            skills = [s for s in skills if s.source.name == source_name]
        
        if installed_only:
            skills = [s for s in skills if s.installed]
        
        return sorted(skills, key=lambda x: x.name)
    
    def get_marketplace_stats(self) -> Dict[str, Any]:
        """Get marketplace statistics."""
        
        return {
            "sources": len(self.sources),
            "total_skills": self.stats.total_skills,
            "approved_skills": self.stats.approved_skills,
            "rejected_skills": self.stats.rejected_skills,
            "quarantined_skills": len([s for s in self.external_skills.values() if s.validation_status == ValidationStatus.QUARANTINED]),
            "installed_skills": self.stats.installed_skills,
            "last_sync": self.stats.last_sync.isoformat() if self.stats.last_sync else None,
            "validation_stats": {
                status.value: len([s for s in self.external_skills.values() if s.validation_status == status])
                for status in ValidationStatus
            }
        }


# Global marketplace instance
external_marketplace = ExternalMarketplace()


# Convenience functions
async def sync_all_sources() -> Dict[str, Any]:
    """Sync all external sources."""
    results = {}
    for source_name in external_marketplace.sources.keys():
        results[source_name] = await external_marketplace.sync_source(source_name)
    return results


async def install_external_skill(skill_id: str) -> Dict[str, Any]:
    """Install an external skill."""
    return await external_marketplace.install_skill(skill_id)


def list_external_skills(**kwargs) -> List[ExternalSkill]:
    """List external skills."""
    return external_marketplace.list_skills(**kwargs)