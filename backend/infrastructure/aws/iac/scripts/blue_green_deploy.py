#!/usr/bin/env python3
"""
Blue-Green Deployment Script

Implements blue-green deployment strategy for zero-downtime deployments.
"""

import os
import sys
import json
import time
import subprocess
import argparse
from typing import Dict, List, Optional, Tuple
import boto3
from botocore.exceptions import ClientError

from .deploy import DeploymentManager


class BlueGreenDeploymentManager(DeploymentManager):
    """Manages blue-green deployments with automatic rollback capabilities."""
    
    def __init__(self, environment: str, region: str, profile: Optional[str] = None):
        super().__init__(environment, region, profile)
        
        # Initialize additional AWS clients for blue-green deployment
        self.route53 = self.session.client('route53', region_name=region) if hasattr(self, 'session') else boto3.client('route53', region_name=region)
        self.elbv2 = self.session.client('elbv2', region_name=region) if hasattr(self, 'session') else boto3.client('elbv2', region_name=region)
        
        # Blue-green configuration
        self.blue_suffix = "blue"
        self.green_suffix = "green"
        self.current_color = self._get_current_deployment_color()
        self.target_color = "green" if self.current_color == "blue" else "blue"
    
    def deploy_blue_green(self, validation_timeout: int = 300) -> bool:
        """Execute blue-green deployment with validation and traffic switching."""
        print(f"Starting blue-green deployment: {self.current_color} -> {self.target_color}")
        
        try:
            # Step 1: Deploy to target environment
            if not self._deploy_target_environment():
                print("Failed to deploy target environment")
                return False
            
            # Step 2: Validate target environment
            if not self._validate_target_environment(validation_timeout):
                print("Target environment validation failed")
                self._cleanup_failed_deployment()
                return False
            
            # Step 3: Switch traffic gradually
            if not self._switch_traffic_gradually():
                print("Traffic switching failed")
                self._rollback_traffic()
                return False
            
            # Step 4: Cleanup old environment
            if not self._cleanup_old_environment():
                print("Warning: Failed to cleanup old environment")
            
            # Step 5: Update deployment metadata
            self._update_deployment_metadata()
            
            print(f"Blue-green deployment completed successfully: {self.current_color} -> {self.target_color}")
            return True
            
        except Exception as e:
            print(f"Blue-green deployment failed: {e}")
            self._rollback_deployment()
            return False
    
    def _get_current_deployment_color(self) -> str:
        """Determine current deployment color from Route53 or default to blue."""
        try:
            # Check Route53 records to determine current color
            hosted_zone_id = self._get_hosted_zone_id()
            if not hosted_zone_id:
                return "blue"  # Default to blue if no hosted zone
            
            response = self.route53.list_resource_record_sets(
                HostedZoneId=hosted_zone_id
            )
            
            for record in response['ResourceRecordSets']:
                if record['Name'].startswith(f"api-{self.environment}"):
                    # Parse the target to determine color
                    if 'blue' in str(record.get('ResourceRecords', [])):
                        return "blue"
                    elif 'green' in str(record.get('ResourceRecords', [])):
                        return "green"
            
            return "blue"  # Default fallback
            
        except Exception as e:
            print(f"Could not determine current color, defaulting to blue: {e}")
            return "blue"
    
    def _deploy_target_environment(self) -> bool:
        """Deploy CDK stacks to target environment."""
        print(f"Deploying to {self.target_color} environment...")
        
        try:
            # Set target color context
            os.environ['CDK_DEPLOYMENT_COLOR'] = self.target_color
            
            # Deploy with color-specific stack names
            cmd = [
                'cdk', 'deploy',
                '--context', f'environment={self.environment}',
                '--context', f'deployment_color={self.target_color}',
                '--require-approval', 'never',
                '--outputs-file', f'outputs-{self.environment}-{self.target_color}.json',
                '--all'
            ]
            
            if self.profile:
                cmd.extend(['--profile', self.profile])
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self._get_cdk_dir())
            
            if result.returncode != 0:
                print(f"Target deployment failed: {result.stderr}")
                return False
            
            print(f"Successfully deployed to {self.target_color} environment")
            return True
            
        except Exception as e:
            print(f"Error deploying target environment: {e}")
            return False
    
    def _validate_target_environment(self, timeout: int) -> bool:
        """Validate target environment health and functionality."""
        print(f"Validating {self.target_color} environment...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Get target environment endpoints
                endpoints = self._get_target_endpoints()
                
                if not endpoints:
                    print("No endpoints found for target environment")
                    time.sleep(10)
                    continue
                
                # Run health checks on all endpoints
                all_healthy = True
                for service_name, endpoint in endpoints.items():
                    if not self._check_service_health(service_name, endpoint):
                        all_healthy = False
                        break
                
                if all_healthy:
                    print(f"{self.target_color} environment validation passed")
                    return True
                
                print(f"Health checks failed, retrying in 10 seconds...")
                time.sleep(10)
                
            except Exception as e:
                print(f"Validation error: {e}")
                time.sleep(10)
        
        print(f"Validation timeout after {timeout} seconds")
        return False
    
    def _switch_traffic_gradually(self) -> bool:
        """Switch traffic gradually from current to target environment."""
        print(f"Switching traffic from {self.current_color} to {self.target_color}...")
        
        try:
            # Traffic switching percentages
            traffic_steps = [10, 25, 50, 75, 100]
            
            for percentage in traffic_steps:
                print(f"Switching {percentage}% traffic to {self.target_color}...")
                
                if not self._update_traffic_weights(percentage):
                    print(f"Failed to switch {percentage}% traffic")
                    return False
                
                # Wait and validate after each step
                time.sleep(30)
                
                if not self._validate_traffic_switch(percentage):
                    print(f"Traffic validation failed at {percentage}%")
                    return False
                
                print(f"Successfully switched {percentage}% traffic")
            
            print("Traffic switching completed successfully")
            return True
            
        except Exception as e:
            print(f"Traffic switching failed: {e}")
            return False
    
    def _update_traffic_weights(self, target_percentage: int) -> bool:
        """Update load balancer or Route53 weights for traffic distribution."""
        try:
            # Update Route53 weighted routing
            hosted_zone_id = self._get_hosted_zone_id()
            if not hosted_zone_id:
                print("No hosted zone found for traffic switching")
                return False
            
            current_weight = 100 - target_percentage
            target_weight = target_percentage
            
            # Update current environment weight
            self._update_route53_weight(
                hosted_zone_id,
                f"api-{self.environment}.{self._get_domain_name()}",
                self._get_environment_endpoint(self.current_color),
                current_weight,
                self.current_color
            )
            
            # Update target environment weight
            self._update_route53_weight(
                hosted_zone_id,
                f"api-{self.environment}.{self._get_domain_name()}",
                self._get_environment_endpoint(self.target_color),
                target_weight,
                self.target_color
            )
            
            return True
            
        except Exception as e:
            print(f"Failed to update traffic weights: {e}")
            return False
    
    def _validate_traffic_switch(self, expected_percentage: int) -> bool:
        """Validate that traffic is being distributed correctly."""
        try:
            # Monitor CloudWatch metrics for traffic distribution
            cloudwatch = boto3.client('cloudwatch', region_name=self.region)
            
            # Get request counts for both environments
            end_time = time.time()
            start_time = end_time - 300  # Last 5 minutes
            
            current_requests = self._get_request_count(cloudwatch, self.current_color, start_time, end_time)
            target_requests = self._get_request_count(cloudwatch, self.target_color, start_time, end_time)
            
            total_requests = current_requests + target_requests
            
            if total_requests == 0:
                print("No traffic detected, skipping validation")
                return True
            
            actual_percentage = (target_requests / total_requests) * 100
            tolerance = 10  # 10% tolerance
            
            if abs(actual_percentage - expected_percentage) <= tolerance:
                print(f"Traffic distribution validated: {actual_percentage:.1f}% (expected {expected_percentage}%)")
                return True
            else:
                print(f"Traffic distribution mismatch: {actual_percentage:.1f}% (expected {expected_percentage}%)")
                return False
            
        except Exception as e:
            print(f"Traffic validation error: {e}")
            return True  # Don't fail deployment on monitoring issues
    
    def _cleanup_old_environment(self) -> bool:
        """Clean up the old environment after successful deployment."""
        print(f"Cleaning up {self.current_color} environment...")
        
        try:
            # Set cleanup context
            os.environ['CDK_DEPLOYMENT_COLOR'] = self.current_color
            
            # Destroy old environment stacks
            cmd = [
                'cdk', 'destroy',
                '--context', f'environment={self.environment}',
                '--context', f'deployment_color={self.current_color}',
                '--force',
                '--all'
            ]
            
            if self.profile:
                cmd.extend(['--profile', self.profile])
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self._get_cdk_dir())
            
            if result.returncode != 0:
                print(f"Cleanup warning: {result.stderr}")
                return False
            
            print(f"Successfully cleaned up {self.current_color} environment")
            return True
            
        except Exception as e:
            print(f"Cleanup error: {e}")
            return False
    
    def _rollback_deployment(self) -> bool:
        """Rollback failed blue-green deployment."""
        print(f"Rolling back failed deployment...")
        
        try:
            # Switch traffic back to current environment
            self._update_traffic_weights(0)  # 0% to target, 100% to current
            
            # Cleanup failed target environment
            self._cleanup_failed_deployment()
            
            print("Rollback completed")
            return True
            
        except Exception as e:
            print(f"Rollback failed: {e}")
            return False
    
    def _cleanup_failed_deployment(self) -> bool:
        """Clean up failed target deployment."""
        try:
            os.environ['CDK_DEPLOYMENT_COLOR'] = self.target_color
            
            cmd = [
                'cdk', 'destroy',
                '--context', f'environment={self.environment}',
                '--context', f'deployment_color={self.target_color}',
                '--force',
                '--all'
            ]
            
            if self.profile:
                cmd.extend(['--profile', self.profile])
            
            subprocess.run(cmd, capture_output=True, text=True, cwd=self._get_cdk_dir())
            return True
            
        except Exception as e:
            print(f"Failed deployment cleanup error: {e}")
            return False
    
    def _get_target_endpoints(self) -> Dict[str, str]:
        """Get endpoints for target environment."""
        try:
            outputs_file = f'outputs-{self.environment}-{self.target_color}.json'
            
            if not os.path.exists(outputs_file):
                return {}
            
            with open(outputs_file, 'r') as f:
                outputs = json.load(f)
            
            endpoints = {}
            for stack_name, stack_outputs in outputs.items():
                for output_name, output_value in stack_outputs.items():
                    if 'Url' in output_name or 'Endpoint' in output_name:
                        service_name = output_name.replace('Url', '').replace('Endpoint', '')
                        endpoints[service_name] = output_value
            
            return endpoints
            
        except Exception as e:
            print(f"Error getting target endpoints: {e}")
            return {}
    
    def _check_service_health(self, service_name: str, endpoint: str) -> bool:
        """Check health of a specific service endpoint."""
        try:
            import requests
            
            health_url = f"{endpoint}/health"
            response = requests.get(health_url, timeout=10)
            
            if response.status_code == 200:
                print(f"✓ {service_name} health check passed")
                return True
            else:
                print(f"✗ {service_name} health check failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✗ {service_name} health check error: {e}")
            return False
    
    def _get_hosted_zone_id(self) -> Optional[str]:
        """Get Route53 hosted zone ID for the domain."""
        try:
            domain_name = self._get_domain_name()
            
            response = self.route53.list_hosted_zones()
            
            for zone in response['HostedZones']:
                if zone['Name'].rstrip('.') == domain_name:
                    return zone['Id'].split('/')[-1]
            
            return None
            
        except Exception as e:
            print(f"Error getting hosted zone ID: {e}")
            return None
    
    def _get_domain_name(self) -> str:
        """Get domain name for the environment."""
        domain_mapping = {
            'dev': 'dev.infrarecovery.com',
            'staging': 'staging.infrarecovery.com',
            'prod': 'infrarecovery.com'
        }
        return domain_mapping.get(self.environment, 'infrarecovery.com')
    
    def _get_environment_endpoint(self, color: str) -> str:
        """Get endpoint for specific environment color."""
        # This would return the actual load balancer or API Gateway endpoint
        # for the specified color deployment
        return f"https://api-{self.environment}-{color}.{self._get_domain_name()}"
    
    def _update_route53_weight(self, hosted_zone_id: str, name: str, target: str, weight: int, set_identifier: str) -> bool:
        """Update Route53 weighted routing record."""
        try:
            self.route53.change_resource_record_sets(
                HostedZoneId=hosted_zone_id,
                ChangeBatch={
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': name,
                            'Type': 'CNAME',
                            'SetIdentifier': set_identifier,
                            'Weight': weight,
                            'TTL': 60,
                            'ResourceRecords': [{'Value': target}]
                        }
                    }]
                }
            )
            return True
            
        except Exception as e:
            print(f"Route53 update error: {e}")
            return False
    
    def _get_request_count(self, cloudwatch, color: str, start_time: float, end_time: float) -> int:
        """Get request count from CloudWatch metrics."""
        try:
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName='Count',
                Dimensions=[
                    {
                        'Name': 'Stage',
                        'Value': f'{self.environment}-{color}'
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Sum']
            )
            
            total = sum(point['Sum'] for point in response['Datapoints'])
            return int(total)
            
        except Exception as e:
            print(f"CloudWatch metrics error: {e}")
            return 0
    
    def _update_deployment_metadata(self) -> None:
        """Update deployment metadata after successful blue-green deployment."""
        metadata = {
            'environment': self.environment,
            'region': self.region,
            'timestamp': int(time.time()),
            'deployment_type': 'blue-green',
            'previous_color': self.current_color,
            'current_color': self.target_color,
            'stacks': self._get_environment_stacks()
        }
        
        with open(f'deployment-{self.environment}-{self.target_color}.json', 'w') as f:
            json.dump(metadata, f, indent=2)


def main():
    """Main entry point for blue-green deployment script."""
    parser = argparse.ArgumentParser(description='Blue-Green CDK Deployment')
    parser.add_argument('--environment', '-e', required=True, choices=['dev', 'staging', 'prod'])
    parser.add_argument('--region', '-r', default='us-east-1')
    parser.add_argument('--profile', '-p', help='AWS profile to use')
    parser.add_argument('--validation-timeout', '-t', type=int, default=300, help='Validation timeout in seconds')
    
    args = parser.parse_args()
    
    # Initialize blue-green deployment manager
    bg_manager = BlueGreenDeploymentManager(
        environment=args.environment,
        region=args.region,
        profile=args.profile
    )
    
    # Execute blue-green deployment
    success = bg_manager.deploy_blue_green(validation_timeout=args.validation_timeout)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()