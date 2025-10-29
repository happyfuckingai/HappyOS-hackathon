"""
AWS Services Package

This package contains all AWS service adapters and the service factory
for creating AWS service instances.
"""

from .agent_core_adapter import AWSAgentCoreAdapter
from .opensearch_adapter import AWSOpenSearchAdapter
from .lambda_adapter import AWSLambdaAdapter
from .api_gateway_adapter import AWSAPIGatewayAdapter
from .elasticache_adapter import AWSElastiCacheAdapter
from .s3_adapter import AWSS3Adapter
from .secrets_adapter import AWSSecretsManagerAdapter

__all__ = [
    'AWSAgentCoreAdapter',
    'AWSOpenSearchAdapter', 
    'AWSLambdaAdapter',
    'AWSAPIGatewayAdapter',
    'AWSElastiCacheAdapter',
    'AWSS3Adapter',
    'AWSSecretsManagerAdapter'
]