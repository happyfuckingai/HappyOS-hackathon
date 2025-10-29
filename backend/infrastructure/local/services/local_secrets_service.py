"""
Local Secrets Service

Provides secrets management using environment variables and local configuration
as a fallback when AWS Secrets Manager is unavailable.
"""

import os
import json
from typing import Any, Dict, List, Optional
from backend.core.interfaces import SecretsService


class LocalSecretsService(SecretsService):
    """Local secrets service using environment variables and config files."""
    
    def __init__(self, config_file: str = None):
        """Initialize local secrets service."""
        self.config_file = config_file or os.path.join(os.getcwd(), '.secrets.json')
        self._secrets_cache: Dict[str, str] = {}
        self._load_secrets_file()
    
    def _load_secrets_file(self):
        """Load secrets from local configuration file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self._secrets_cache.update(json.load(f))
        except Exception as e:
            print(f"Warning: Could not load secrets file {self.config_file}: {e}")
    
    def _save_secrets_file(self):
        """Save secrets to local configuration file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self._secrets_cache, f, indent=2)
        except Exception as e:
            print(f"Error saving secrets file: {e}")
    
    def _get_secret_key(self, secret_name: str, tenant_id: str = None) -> str:
        """Generate tenant-isolated secret key."""
        if tenant_id:
            return f"{tenant_id}_{secret_name}".upper()
        return secret_name.upper()
    
    async def get_secret(self, secret_name: str, tenant_id: str = None) -> Optional[str]:
        """Retrieve a secret value from environment or config file."""
        secret_key = self._get_secret_key(secret_name, tenant_id)
        
        # Try environment variable first
        env_value = os.getenv(secret_key)
        if env_value:
            return env_value
        
        # Try config file cache
        return self._secrets_cache.get(secret_key)
    
    async def put_secret(self, secret_name: str, secret_value: str, tenant_id: str = None) -> bool:
        """Store a secret value in config file."""
        try:
            secret_key = self._get_secret_key(secret_name, tenant_id)
            self._secrets_cache[secret_key] = secret_value
            self._save_secrets_file()
            return True
        except Exception as e:
            print(f"Error storing secret {secret_name}: {e}")
            return False
    
    async def delete_secret(self, secret_name: str, tenant_id: str = None) -> bool:
        """Delete a secret from config file."""
        try:
            secret_key = self._get_secret_key(secret_name, tenant_id)
            if secret_key in self._secrets_cache:
                del self._secrets_cache[secret_key]
                self._save_secrets_file()
            return True
        except Exception as e:
            print(f"Error deleting secret {secret_name}: {e}")
            return False