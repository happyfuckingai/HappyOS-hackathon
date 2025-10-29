"""
Local file storage service as fallback for AWS S3.
Provides object storage operations with directory organization and tenant isolation.
"""

import asyncio
import json
import logging
import hashlib
import shutil
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
import mimetypes
import os

from ....core.interfaces import StorageService
from ....core.settings import get_settings


logger = logging.getLogger(__name__)


@dataclass
class StorageObject:
    """Metadata for a stored object."""
    key: str
    tenant_id: str
    size_bytes: int
    content_type: str
    etag: str  # MD5 hash of content
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, str]
    version_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "key": self.key,
            "tenant_id": self.tenant_id,
            "size_bytes": self.size_bytes,
            "content_type": self.content_type,
            "etag": self.etag,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "version_id": self.version_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StorageObject':
        """Create from dictionary."""
        data = data.copy()
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


class LocalStorageService(StorageService):
    """
    Local file storage service that provides S3-like functionality.
    Supports tenant isolation, metadata, and versioning.
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # Storage configuration
        self.data_directory = Path(self.settings.local.data_directory) / "storage"
        self.data_directory.mkdir(parents=True, exist_ok=True)
        
        self.metadata_directory = self.data_directory / "metadata"
        self.metadata_directory.mkdir(parents=True, exist_ok=True)
        
        # Object metadata storage: {tenant_id: {key: StorageObject}}
        self.object_metadata: Dict[str, Dict[str, StorageObject]] = {}
        
        # Configuration
        self.max_disk_gb = self.settings.local.max_disk_gb
        self.enable_versioning = True
        self.enable_compression = False  # Could be enabled for text files
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Load persisted metadata
        self._load_metadata()
        
        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        asyncio.create_task(self._start_background_tasks())
        
        logger.info("Local storage service initialized")
    
    async def _start_background_tasks(self):
        """Start background cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    def _get_tenant_directory(self, tenant_id: str) -> Path:
        """Get storage directory for a tenant."""
        tenant_dir = self.data_directory / "objects" / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        return tenant_dir
    
    def _get_object_path(self, tenant_id: str, key: str) -> Path:
        """Get file path for an object."""
        # Create directory structure based on key
        tenant_dir = self._get_tenant_directory(tenant_id)
        
        # Use key as path, but ensure it's safe
        safe_key = self._sanitize_key(key)
        object_path = tenant_dir / safe_key
        
        # Ensure parent directories exist
        object_path.parent.mkdir(parents=True, exist_ok=True)
        
        return object_path
    
    def _sanitize_key(self, key: str) -> str:
        """Sanitize object key to be filesystem-safe."""
        # Replace problematic characters
        safe_key = key.replace("\\", "/")  # Normalize path separators
        safe_key = safe_key.replace("..", "_")  # Prevent directory traversal
        
        # Ensure key doesn't start with /
        if safe_key.startswith("/"):
            safe_key = safe_key[1:]
        
        return safe_key
    
    def _calculate_etag(self, data: bytes) -> str:
        """Calculate ETag (MD5 hash) for data."""
        return hashlib.md5(data).hexdigest()
    
    def _get_content_type(self, key: str, data: bytes) -> str:
        """Determine content type for object."""
        # Try to guess from file extension
        content_type, _ = mimetypes.guess_type(key)
        
        if content_type:
            return content_type
        
        # Try to detect from content
        if data.startswith(b'\\x89PNG'):
            return 'image/png'
        elif data.startswith(b'\\xff\\xd8\\xff'):
            return 'image/jpeg'
        elif data.startswith(b'%PDF'):
            return 'application/pdf'
        elif data.startswith(b'{') or data.startswith(b'['):
            try:
                json.loads(data.decode('utf-8'))
                return 'application/json'
            except:
                pass
        
        # Check if it's text
        try:
            data.decode('utf-8')
            return 'text/plain'
        except:
            pass
        
        return 'application/octet-stream'
    
    async def put_object(self, key: str, data: bytes, tenant_id: str, 
                        metadata: Dict[str, str] = None) -> bool:
        """Store an object."""
        try:
            if not tenant_id:
                raise ValueError("Tenant ID is required")
            
            if not key:
                raise ValueError("Object key is required")
            
            if metadata is None:
                metadata = {}
            
            # Check disk space
            current_usage = await self._get_disk_usage()
            max_usage_bytes = self.max_disk_gb * 1024 * 1024 * 1024
            
            if current_usage + len(data) > max_usage_bytes:
                raise Exception(f"Storage quota exceeded. Current: {current_usage / (1024**3):.2f}GB, Max: {self.max_disk_gb}GB")
            
            with self._lock:
                # Get object path
                object_path = self._get_object_path(tenant_id, key)
                
                # Calculate metadata
                etag = self._calculate_etag(data)
                content_type = self._get_content_type(key, data)
                
                # Handle versioning
                version_id = None
                if self.enable_versioning and object_path.exists():
                    version_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    version_path = object_path.with_suffix(f".{version_id}{object_path.suffix}")
                    shutil.move(str(object_path), str(version_path))
                
                # Write object data
                with open(object_path, 'wb') as f:
                    f.write(data)
                
                # Create metadata
                storage_object = StorageObject(
                    key=key,
                    tenant_id=tenant_id,
                    size_bytes=len(data),
                    content_type=content_type,
                    etag=etag,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    metadata=metadata,
                    version_id=version_id
                )
                
                # Store metadata
                if tenant_id not in self.object_metadata:
                    self.object_metadata[tenant_id] = {}
                
                self.object_metadata[tenant_id][key] = storage_object
                
                # Persist metadata
                await self._persist_metadata(tenant_id)
                
                logger.debug(f"Stored object {key} for tenant {tenant_id} ({len(data)} bytes)")
                return True
                
        except Exception as e:
            logger.error(f"Error storing object {key} for tenant {tenant_id}: {e}")
            return False
    
    async def get_object(self, key: str, tenant_id: str) -> Optional[bytes]:
        """Retrieve an object."""
        try:
            if not tenant_id or not key:
                return None
            
            with self._lock:
                # Check if object exists in metadata
                if (tenant_id not in self.object_metadata or 
                    key not in self.object_metadata[tenant_id]):
                    return None
                
                # Get object path
                object_path = self._get_object_path(tenant_id, key)
                
                if not object_path.exists():
                    logger.warning(f"Object file missing: {object_path}")
                    return None
                
                # Read object data
                with open(object_path, 'rb') as f:
                    data = f.read()
                
                # Update access time in metadata
                storage_object = self.object_metadata[tenant_id][key]
                storage_object.updated_at = datetime.now()
                
                logger.debug(f"Retrieved object {key} for tenant {tenant_id} ({len(data)} bytes)")
                return data
                
        except Exception as e:
            logger.error(f"Error retrieving object {key} for tenant {tenant_id}: {e}")
            return None
    
    async def delete_object(self, key: str, tenant_id: str) -> bool:
        """Delete an object."""
        try:
            if not tenant_id or not key:
                return False
            
            with self._lock:
                # Check if object exists
                if (tenant_id not in self.object_metadata or 
                    key not in self.object_metadata[tenant_id]):
                    return False
                
                # Get object path
                object_path = self._get_object_path(tenant_id, key)
                
                # Delete file if it exists
                if object_path.exists():
                    object_path.unlink()
                
                # Delete any versions
                if self.enable_versioning:
                    version_pattern = f"{object_path.stem}.*{object_path.suffix}"
                    for version_file in object_path.parent.glob(version_pattern):
                        if version_file != object_path:
                            version_file.unlink()
                
                # Remove from metadata
                del self.object_metadata[tenant_id][key]
                
                # Persist metadata
                await self._persist_metadata(tenant_id)
                
                logger.debug(f"Deleted object {key} for tenant {tenant_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting object {key} for tenant {tenant_id}: {e}")
            return False
    
    async def list_objects(self, prefix: str, tenant_id: str, max_keys: int = 1000) -> List[str]:
        """List objects with prefix."""
        try:
            if not tenant_id:
                return []
            
            with self._lock:
                if tenant_id not in self.object_metadata:
                    return []
                
                # Filter objects by prefix
                matching_keys = []
                for key in self.object_metadata[tenant_id].keys():
                    if key.startswith(prefix):
                        matching_keys.append(key)
                        
                        if len(matching_keys) >= max_keys:
                            break
                
                logger.debug(f"Listed {len(matching_keys)} objects with prefix '{prefix}' for tenant {tenant_id}")
                return sorted(matching_keys)
                
        except Exception as e:
            logger.error(f"Error listing objects with prefix '{prefix}' for tenant {tenant_id}: {e}")
            return []
    
    async def get_object_metadata(self, key: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an object."""
        try:
            if not tenant_id or not key:
                return None
            
            with self._lock:
                if (tenant_id not in self.object_metadata or 
                    key not in self.object_metadata[tenant_id]):
                    return None
                
                storage_object = self.object_metadata[tenant_id][key]
                return storage_object.to_dict()
                
        except Exception as e:
            logger.error(f"Error getting metadata for object {key} in tenant {tenant_id}: {e}")
            return None
    
    async def copy_object(self, source_key: str, dest_key: str, tenant_id: str, 
                         dest_tenant_id: str = None) -> bool:
        """Copy an object."""
        try:
            if dest_tenant_id is None:
                dest_tenant_id = tenant_id
            
            # Get source object
            source_data = await self.get_object(source_key, tenant_id)
            if source_data is None:
                return False
            
            # Get source metadata
            source_metadata = await self.get_object_metadata(source_key, tenant_id)
            if source_metadata is None:
                return False
            
            # Copy to destination
            return await self.put_object(
                dest_key, 
                source_data, 
                dest_tenant_id, 
                source_metadata.get('metadata', {})
            )
            
        except Exception as e:
            logger.error(f"Error copying object {source_key} to {dest_key}: {e}")
            return False
    
    async def _get_disk_usage(self) -> int:
        """Get current disk usage in bytes."""
        try:
            total_size = 0
            for tenant_dir in (self.data_directory / "objects").iterdir():
                if tenant_dir.is_dir():
                    for root, dirs, files in os.walk(tenant_dir):
                        for file in files:
                            file_path = Path(root) / file
                            if file_path.exists():
                                total_size += file_path.stat().st_size
            return total_size
        except Exception as e:
            logger.error(f"Error calculating disk usage: {e}")
            return 0
    
    def _load_metadata(self):
        """Load object metadata from disk."""
        try:
            for metadata_file in self.metadata_directory.glob("*.json"):
                tenant_id = metadata_file.stem
                
                with open(metadata_file, 'r') as f:
                    metadata_data = json.load(f)
                
                tenant_metadata = {}
                for key, obj_data in metadata_data.items():
                    storage_object = StorageObject.from_dict(obj_data)
                    tenant_metadata[key] = storage_object
                
                self.object_metadata[tenant_id] = tenant_metadata
            
            total_objects = sum(len(tenant_meta) for tenant_meta in self.object_metadata.values())
            logger.info(f"Loaded metadata for {total_objects} objects across {len(self.object_metadata)} tenants")
            
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
    
    async def _persist_metadata(self, tenant_id: str):
        """Persist metadata for a tenant to disk."""
        try:
            if tenant_id not in self.object_metadata:
                return
            
            metadata_file = self.metadata_directory / f"{tenant_id}.json"
            metadata_data = {}
            
            for key, storage_object in self.object_metadata[tenant_id].items():
                metadata_data[key] = storage_object.to_dict()
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata_data, f, indent=2)
            
            logger.debug(f"Persisted metadata for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error persisting metadata for tenant {tenant_id}: {e}")
    
    async def _cleanup_loop(self):
        """Background cleanup for orphaned files and old versions."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Clean up orphaned files (files without metadata)
                await self._cleanup_orphaned_files()
                
                # Clean up old versions if versioning is enabled
                if self.enable_versioning:
                    await self._cleanup_old_versions()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in storage cleanup loop: {e}")
    
    async def _cleanup_orphaned_files(self):
        """Remove files that don't have corresponding metadata."""
        try:
            orphaned_count = 0
            
            for tenant_dir in (self.data_directory / "objects").iterdir():
                if not tenant_dir.is_dir():
                    continue
                
                tenant_id = tenant_dir.name
                tenant_metadata = self.object_metadata.get(tenant_id, {})
                
                for root, dirs, files in os.walk(tenant_dir):
                    for file in files:
                        file_path = Path(root) / file
                        
                        # Calculate relative key
                        relative_path = file_path.relative_to(tenant_dir)
                        key = str(relative_path)
                        
                        # Check if metadata exists
                        if key not in tenant_metadata:
                            # Check if it's a version file
                            is_version = False
                            for metadata_key in tenant_metadata.keys():
                                if key.startswith(metadata_key.split('.')[0]):
                                    is_version = True
                                    break
                            
                            if not is_version:
                                file_path.unlink()
                                orphaned_count += 1
                                logger.debug(f"Removed orphaned file: {file_path}")
            
            if orphaned_count > 0:
                logger.info(f"Cleaned up {orphaned_count} orphaned files")
                
        except Exception as e:
            logger.error(f"Error cleaning up orphaned files: {e}")
    
    async def _cleanup_old_versions(self, max_versions: int = 5, max_age_days: int = 30):
        """Clean up old object versions."""
        try:
            cleaned_count = 0
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            
            for tenant_dir in (self.data_directory / "objects").iterdir():
                if not tenant_dir.is_dir():
                    continue
                
                # Find version files
                for root, dirs, files in os.walk(tenant_dir):
                    version_groups = {}
                    
                    for file in files:
                        file_path = Path(root) / file
                        
                        # Check if it's a version file (contains timestamp)
                        if '.' in file and len(file.split('.')[-2]) == 21:  # timestamp format
                            base_name = '.'.join(file.split('.')[:-2])
                            if base_name not in version_groups:
                                version_groups[base_name] = []
                            version_groups[base_name].append(file_path)
                    
                    # Clean up old versions
                    for base_name, version_files in version_groups.items():
                        # Sort by modification time
                        version_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                        
                        # Keep only max_versions newest files
                        files_to_remove = version_files[max_versions:]
                        
                        # Also remove files older than cutoff_date
                        for version_file in version_files:
                            file_time = datetime.fromtimestamp(version_file.stat().st_mtime)
                            if file_time < cutoff_date and version_file not in files_to_remove:
                                files_to_remove.append(version_file)
                        
                        # Remove old versions
                        for version_file in files_to_remove:
                            version_file.unlink()
                            cleaned_count += 1
                            logger.debug(f"Removed old version: {version_file}")
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old version files")
                
        except Exception as e:
            logger.error(f"Error cleaning up old versions: {e}")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage service statistics."""
        try:
            with self._lock:
                total_objects = 0
                total_size = 0
                tenant_stats = {}
                
                for tenant_id, tenant_metadata in self.object_metadata.items():
                    tenant_objects = len(tenant_metadata)
                    tenant_size = sum(obj.size_bytes for obj in tenant_metadata.values())
                    
                    tenant_stats[tenant_id] = {
                        "objects": tenant_objects,
                        "size_bytes": tenant_size,
                        "size_mb": tenant_size / (1024 * 1024)
                    }
                    
                    total_objects += tenant_objects
                    total_size += tenant_size
                
                return {
                    "total_objects": total_objects,
                    "total_size_bytes": total_size,
                    "total_size_mb": total_size / (1024 * 1024),
                    "total_size_gb": total_size / (1024 * 1024 * 1024),
                    "max_size_gb": self.max_disk_gb,
                    "utilization_percent": (total_size / (self.max_disk_gb * 1024 * 1024 * 1024)) * 100,
                    "tenant_count": len(self.object_metadata),
                    "tenant_stats": tenant_stats,
                    "versioning_enabled": self.enable_versioning
                }
                
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {}
    
    async def shutdown(self):
        """Shutdown the storage service and persist metadata."""
        logger.info("Shutting down local storage service")
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
        
        # Persist all metadata
        for tenant_id in self.object_metadata.keys():
            await self._persist_metadata(tenant_id)
        
        logger.info("Local storage service shutdown complete")