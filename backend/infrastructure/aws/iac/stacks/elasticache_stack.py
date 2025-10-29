"""
ElastiCache Stack

Creates ElastiCache Redis cluster for caching with tenant isolation.
"""

from aws_cdk import (
    aws_elasticache as elasticache,
    aws_ec2 as ec2,
    CfnOutput
)
from constructs import Construct

from .base_stack import BaseStack
from ..config.environment_config import EnvironmentConfig


class ElastiCacheStack(BaseStack):
    """ElastiCache stack for Redis caching."""
    
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        vpc: ec2.Vpc,
        security_group: ec2.SecurityGroup,
        env_config: EnvironmentConfig,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, env_config, **kwargs)
        
        self.vpc = vpc
        self.security_group = security_group
        
        # Create subnet group
        self.subnet_group = self._create_subnet_group()
        
        # Create Redis cluster
        self.cluster = self._create_redis_cluster()
        
        # Create outputs
        self._create_outputs()
    
    def _create_subnet_group(self) -> elasticache.CfnSubnetGroup:
        """Create ElastiCache subnet group."""
        
        private_subnet_ids = [subnet.subnet_id for subnet in self.vpc.private_subnets]
        
        subnet_group = elasticache.CfnSubnetGroup(
            self,
            "ElastiCacheSubnetGroup",
            description="Subnet group for ElastiCache cluster",
            subnet_ids=private_subnet_ids,
            cache_subnet_group_name=self.get_resource_name("cache-subnet-group")
        )
        
        return subnet_group
    
    def _create_redis_cluster(self) -> elasticache.CfnCacheCluster:
        """Create Redis cache cluster."""
        
        cluster = elasticache.CfnCacheCluster(
            self,
            "RedisCluster",
            cache_node_type=self.env_config.services.elasticache_node_type,
            engine="redis",
            num_cache_nodes=self.env_config.services.elasticache_num_cache_nodes,
            cluster_name=self.get_resource_name("redis-cluster"),
            cache_subnet_group_name=self.subnet_group.cache_subnet_group_name,
            vpc_security_group_ids=[self.security_group.security_group_id],
            engine_version="7.0",
            port=6379,
            auto_minor_version_upgrade=True,
            preferred_maintenance_window="sun:05:00-sun:06:00",
            snapshot_retention_limit=5 if self.env_config.environment == "prod" else 1,
            snapshot_window="03:00-04:00"
        )
        
        cluster.add_dependency(self.subnet_group)
        
        return cluster
    
    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        
        self.create_output(
            "RedisClusterEndpoint",
            value=self.cluster.attr_redis_endpoint_address,
            description="Redis cluster endpoint address"
        )
        
        self.create_output(
            "RedisClusterPort",
            value=self.cluster.attr_redis_endpoint_port,
            description="Redis cluster port"
        )