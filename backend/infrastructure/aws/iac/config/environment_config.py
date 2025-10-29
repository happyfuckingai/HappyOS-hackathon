"""
Environment Configuration for CDK Application

Manages environment-specific settings and parameters for infrastructure deployment.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional
import yaml


@dataclass
class TenantConfig:
    """Configuration for a specific tenant."""
    name: str
    domain: str
    agents: List[str]
    opensearch_index_prefix: str
    lambda_prefix: str
    cache_namespace: str
    resource_limits: Dict[str, int]


@dataclass
class NetworkConfig:
    """Network configuration settings."""
    vpc_cidr: str
    availability_zones: List[str]
    public_subnet_cidrs: List[str]
    private_subnet_cidrs: List[str]
    enable_nat_gateway: bool
    enable_vpc_endpoints: bool


@dataclass
class ServiceConfig:
    """Service-specific configuration settings."""
    opensearch_instance_type: str
    opensearch_instance_count: int
    opensearch_volume_size: int
    elasticache_node_type: str
    elasticache_num_cache_nodes: int
    lambda_memory_size: int
    lambda_timeout: int
    api_gateway_throttle_rate: int
    api_gateway_throttle_burst: int


class EnvironmentConfig:
    """Main environment configuration class."""
    
    def __init__(self, environment: Optional[str] = None):
        self.environment = environment or os.getenv("CDK_ENVIRONMENT", "dev")
        self.aws_account_id = os.getenv("CDK_DEFAULT_ACCOUNT")
        self.aws_region = os.getenv("CDK_DEFAULT_REGION", "us-east-1")
        self.cost_center = os.getenv("COST_CENTER", "InfrastructureRecovery")
        
        # Load configuration files
        self._load_tenant_config()
        self._load_network_config()
        self._load_service_config()
        
        # Validate configuration
        self._validate_config()
    
    def _load_tenant_config(self) -> None:
        """Load tenant configuration from YAML file."""
        config_path = os.path.join(
            os.path.dirname(__file__), 
            "..", "..", "..", "..", "config", "tenants.yaml"
        )
        
        try:
            with open(config_path, 'r') as f:
                tenant_data = yaml.safe_load(f)
            
            self.tenants = {}
            for tenant_name, config in tenant_data.get('tenants', {}).items():
                self.tenants[tenant_name] = TenantConfig(
                    name=tenant_name,
                    domain=config.get('domain', ''),
                    agents=config.get('agents', []),
                    opensearch_index_prefix=config.get('resources', {}).get('opensearch_index', ''),
                    lambda_prefix=config.get('resources', {}).get('lambda_prefix', ''),
                    cache_namespace=config.get('resources', {}).get('cache_namespace', ''),
                    resource_limits=config.get('resource_limits', {})
                )
        except FileNotFoundError:
            # Use default tenant configuration if file not found
            self._create_default_tenant_config()
    
    def _create_default_tenant_config(self) -> None:
        """Create default tenant configuration."""
        self.tenants = {
            'meetmind': TenantConfig(
                name='meetmind',
                domain='meetmind.se',
                agents=['summarizer', 'pipeline'],
                opensearch_index_prefix='meetmind-',
                lambda_prefix='meetmind-',
                cache_namespace='mm:',
                resource_limits={'max_memory': 1024, 'max_storage': 10240}
            ),
            'agent_svea': TenantConfig(
                name='agent_svea',
                domain='agentsvea.se',
                agents=['gov_docs', 'workflow'],
                opensearch_index_prefix='agentsvea-',
                lambda_prefix='agentsvea-',
                cache_namespace='as:',
                resource_limits={'max_memory': 2048, 'max_storage': 20480}
            ),
            'felicias_finance': TenantConfig(
                name='felicias_finance',
                domain='feliciasfi.com',
                agents=['ledger', 'analytics'],
                opensearch_index_prefix='feliciasfi-',
                lambda_prefix='feliciasfi-',
                cache_namespace='ff:',
                resource_limits={'max_memory': 1536, 'max_storage': 15360}
            )
        }
    
    def _load_network_config(self) -> None:
        """Load network configuration based on environment."""
        network_configs = {
            'dev': NetworkConfig(
                vpc_cidr='10.0.0.0/16',
                availability_zones=['us-east-1a', 'us-east-1b'],
                public_subnet_cidrs=['10.0.1.0/24', '10.0.2.0/24'],
                private_subnet_cidrs=['10.0.10.0/24', '10.0.20.0/24'],
                enable_nat_gateway=True,
                enable_vpc_endpoints=False
            ),
            'staging': NetworkConfig(
                vpc_cidr='10.1.0.0/16',
                availability_zones=['us-east-1a', 'us-east-1b', 'us-east-1c'],
                public_subnet_cidrs=['10.1.1.0/24', '10.1.2.0/24', '10.1.3.0/24'],
                private_subnet_cidrs=['10.1.10.0/24', '10.1.20.0/24', '10.1.30.0/24'],
                enable_nat_gateway=True,
                enable_vpc_endpoints=True
            ),
            'prod': NetworkConfig(
                vpc_cidr='10.2.0.0/16',
                availability_zones=['us-east-1a', 'us-east-1b', 'us-east-1c'],
                public_subnet_cidrs=['10.2.1.0/24', '10.2.2.0/24', '10.2.3.0/24'],
                private_subnet_cidrs=['10.2.10.0/24', '10.2.20.0/24', '10.2.30.0/24'],
                enable_nat_gateway=True,
                enable_vpc_endpoints=True
            )
        }
        
        self.network = network_configs.get(self.environment, network_configs['dev'])
    
    def _load_service_config(self) -> None:
        """Load service configuration based on environment."""
        service_configs = {
            'dev': ServiceConfig(
                opensearch_instance_type='t3.small.search',
                opensearch_instance_count=1,
                opensearch_volume_size=20,
                elasticache_node_type='cache.t3.micro',
                elasticache_num_cache_nodes=1,
                lambda_memory_size=512,
                lambda_timeout=30,
                api_gateway_throttle_rate=100,
                api_gateway_throttle_burst=200
            ),
            'staging': ServiceConfig(
                opensearch_instance_type='t3.medium.search',
                opensearch_instance_count=2,
                opensearch_volume_size=50,
                elasticache_node_type='cache.t3.small',
                elasticache_num_cache_nodes=2,
                lambda_memory_size=1024,
                lambda_timeout=60,
                api_gateway_throttle_rate=500,
                api_gateway_throttle_burst=1000
            ),
            'prod': ServiceConfig(
                opensearch_instance_type='m6g.large.search',
                opensearch_instance_count=3,
                opensearch_volume_size=100,
                elasticache_node_type='cache.r6g.large',
                elasticache_num_cache_nodes=3,
                lambda_memory_size=2048,
                lambda_timeout=300,
                api_gateway_throttle_rate=2000,
                api_gateway_throttle_burst=5000
            )
        }
        
        self.services = service_configs.get(self.environment, service_configs['dev'])
    
    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        if not self.aws_account_id:
            raise ValueError("AWS_ACCOUNT_ID environment variable is required")
        
        if not self.aws_region:
            raise ValueError("AWS_REGION environment variable is required")
        
        if len(self.tenants) == 0:
            raise ValueError("At least one tenant must be configured")
        
        # Validate network configuration
        if len(self.network.availability_zones) != len(self.network.public_subnet_cidrs):
            raise ValueError("Number of AZs must match number of public subnets")
        
        if len(self.network.availability_zones) != len(self.network.private_subnet_cidrs):
            raise ValueError("Number of AZs must match number of private subnets")
    
    def get_stack_name(self, stack_type: str) -> str:
        """Generate standardized stack name."""
        return f"InfraRecovery-{self.environment}-{stack_type}"
    
    def get_resource_name(self, resource_type: str, tenant: Optional[str] = None) -> str:
        """Generate standardized resource name."""
        if tenant:
            return f"infra-recovery-{self.environment}-{tenant}-{resource_type}"
        return f"infra-recovery-{self.environment}-{resource_type}"
    
    def get_tenant_config(self, tenant_name: str) -> TenantConfig:
        """Get configuration for a specific tenant."""
        if tenant_name not in self.tenants:
            raise ValueError(f"Tenant '{tenant_name}' not found in configuration")
        return self.tenants[tenant_name]
    
    def get_all_tenant_names(self) -> List[str]:
        """Get list of all configured tenant names."""
        return list(self.tenants.keys())