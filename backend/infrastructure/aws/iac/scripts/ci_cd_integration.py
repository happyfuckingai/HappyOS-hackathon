#!/usr/bin/env python3
"""
CI/CD Integration Scripts

Provides integration with GitHub Actions, GitLab CI, and other CI/CD systems.
"""

import os
import sys
import json
import yaml
import argparse
from typing import Dict, List, Optional, Any
from pathlib import Path

from .deploy import DeploymentManager
from .blue_green_deploy import BlueGreenDeploymentManager


class CICDIntegrationManager:
    """Manages CI/CD pipeline integration for CDK deployments."""
    
    def __init__(self, ci_system: str = "github"):
        self.ci_system = ci_system
        self.project_root = Path(__file__).parent.parent.parent.parent.parent
        self.workflows_dir = self.project_root / ".github" / "workflows"
        self.gitlab_ci_file = self.project_root / ".gitlab-ci.yml"
    
    def generate_github_workflows(self) -> bool:
        """Generate GitHub Actions workflows for CDK deployment."""
        print("Generating GitHub Actions workflows...")
        
        try:
            # Create workflows directory
            self.workflows_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate main deployment workflow
            self._generate_deployment_workflow()
            
            # Generate pull request validation workflow
            self._generate_pr_validation_workflow()
            
            # Generate blue-green deployment workflow
            self._generate_blue_green_workflow()
            
            # Generate rollback workflow
            self._generate_rollback_workflow()
            
            print("GitHub Actions workflows generated successfully")
            return True
            
        except Exception as e:
            print(f"Error generating GitHub workflows: {e}")
            return False
    
    def _generate_deployment_workflow(self) -> None:
        """Generate main deployment workflow."""
        workflow = {
            'name': 'Infrastructure Deployment',
            'on': {
                'push': {
                    'branches': ['main', 'develop'],
                    'paths': ['backend/infrastructure/aws/iac/**']
                },
                'workflow_dispatch': {
                    'inputs': {
                        'environment': {
                            'description': 'Environment to deploy',
                            'required': True,
                            'default': 'dev',
                            'type': 'choice',
                            'options': ['dev', 'staging', 'prod']
                        },
                        'deployment_type': {
                            'description': 'Deployment type',
                            'required': True,
                            'default': 'standard',
                            'type': 'choice',
                            'options': ['standard', 'blue-green']
                        }
                    }
                }
            },
            'env': {
                'AWS_REGION': 'us-east-1',
                'CDK_DEFAULT_REGION': 'us-east-1'
            },
            'jobs': {
                'deploy': {
                    'runs-on': 'ubuntu-latest',
                    'permissions': {
                        'id-token': 'write',
                        'contents': 'read'
                    },
                    'steps': [
                        {
                            'name': 'Checkout code',
                            'uses': 'actions/checkout@v4'
                        },
                        {
                            'name': 'Configure AWS credentials',
                            'uses': 'aws-actions/configure-aws-credentials@v4',
                            'with': {
                                'role-to-assume': '${{ secrets.AWS_ROLE_ARN }}',
                                'aws-region': '${{ env.AWS_REGION }}'
                            }
                        },
                        {
                            'name': 'Setup Python',
                            'uses': 'actions/setup-python@v4',
                            'with': {
                                'python-version': '3.11'
                            }
                        },
                        {
                            'name': 'Setup Node.js',
                            'uses': 'actions/setup-node@v4',
                            'with': {
                                'node-version': '18'
                            }
                        },
                        {
                            'name': 'Install CDK',
                            'run': 'npm install -g aws-cdk'
                        },
                        {
                            'name': 'Install Python dependencies',
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                pip install -r requirements.txt
                            '''
                        },
                        {
                            'name': 'Determine environment',
                            'id': 'env',
                            'run': '''
                                if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
                                  echo "environment=${{ github.event.inputs.environment }}" >> $GITHUB_OUTPUT
                                  echo "deployment_type=${{ github.event.inputs.deployment_type }}" >> $GITHUB_OUTPUT
                                elif [ "${{ github.ref }}" = "refs/heads/main" ]; then
                                  echo "environment=prod" >> $GITHUB_OUTPUT
                                  echo "deployment_type=blue-green" >> $GITHUB_OUTPUT
                                elif [ "${{ github.ref }}" = "refs/heads/develop" ]; then
                                  echo "environment=staging" >> $GITHUB_OUTPUT
                                  echo "deployment_type=standard" >> $GITHUB_OUTPUT
                                else
                                  echo "environment=dev" >> $GITHUB_OUTPUT
                                  echo "deployment_type=standard" >> $GITHUB_OUTPUT
                                fi
                            '''
                        },
                        {
                            'name': 'CDK Bootstrap',
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                python scripts/deploy.py bootstrap --environment ${{ steps.env.outputs.environment }}
                            '''
                        },
                        {
                            'name': 'CDK Synth',
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                python scripts/deploy.py synth --environment ${{ steps.env.outputs.environment }}
                            '''
                        },
                        {
                            'name': 'Standard Deployment',
                            'if': "steps.env.outputs.deployment_type == 'standard'",
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                python scripts/deploy.py deploy --environment ${{ steps.env.outputs.environment }}
                            '''
                        },
                        {
                            'name': 'Blue-Green Deployment',
                            'if': "steps.env.outputs.deployment_type == 'blue-green'",
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                python scripts/blue_green_deploy.py --environment ${{ steps.env.outputs.environment }}
                            '''
                        },
                        {
                            'name': 'Validate Deployment',
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                python scripts/deploy.py validate --environment ${{ steps.env.outputs.environment }}
                            '''
                        },
                        {
                            'name': 'Upload deployment artifacts',
                            'uses': 'actions/upload-artifact@v3',
                            'with': {
                                'name': 'deployment-outputs-${{ steps.env.outputs.environment }}',
                                'path': 'backend/infrastructure/aws/iac/outputs-*.json'
                            }
                        }
                    ]
                }
            }
        }
        
        with open(self.workflows_dir / "infrastructure-deployment.yml", 'w') as f:
            yaml.dump(workflow, f, default_flow_style=False, sort_keys=False)
    
    def _generate_pr_validation_workflow(self) -> None:
        """Generate pull request validation workflow."""
        workflow = {
            'name': 'Infrastructure Validation',
            'on': {
                'pull_request': {
                    'paths': ['backend/infrastructure/aws/iac/**']
                }
            },
            'env': {
                'AWS_REGION': 'us-east-1',
                'CDK_DEFAULT_REGION': 'us-east-1'
            },
            'jobs': {
                'validate': {
                    'runs-on': 'ubuntu-latest',
                    'permissions': {
                        'id-token': 'write',
                        'contents': 'read',
                        'pull-requests': 'write'
                    },
                    'steps': [
                        {
                            'name': 'Checkout code',
                            'uses': 'actions/checkout@v4'
                        },
                        {
                            'name': 'Configure AWS credentials',
                            'uses': 'aws-actions/configure-aws-credentials@v4',
                            'with': {
                                'role-to-assume': '${{ secrets.AWS_ROLE_ARN }}',
                                'aws-region': '${{ env.AWS_REGION }}'
                            }
                        },
                        {
                            'name': 'Setup Python',
                            'uses': 'actions/setup-python@v4',
                            'with': {
                                'python-version': '3.11'
                            }
                        },
                        {
                            'name': 'Setup Node.js',
                            'uses': 'actions/setup-node@v4',
                            'with': {
                                'node-version': '18'
                            }
                        },
                        {
                            'name': 'Install CDK',
                            'run': 'npm install -g aws-cdk'
                        },
                        {
                            'name': 'Install Python dependencies',
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                pip install -r requirements.txt
                            '''
                        },
                        {
                            'name': 'Lint Python code',
                            'run': '''
                                pip install flake8 black
                                cd backend/infrastructure/aws/iac
                                flake8 . --max-line-length=120
                                black --check .
                            '''
                        },
                        {
                            'name': 'CDK Synth (Dev)',
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                python scripts/deploy.py synth --environment dev
                            '''
                        },
                        {
                            'name': 'CDK Diff (Dev)',
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                cdk diff --context environment=dev || true
                            '''
                        },
                        {
                            'name': 'Security scan',
                            'run': '''
                                pip install bandit
                                cd backend/infrastructure/aws/iac
                                bandit -r . -f json -o security-report.json || true
                            '''
                        },
                        {
                            'name': 'Upload security report',
                            'uses': 'actions/upload-artifact@v3',
                            'with': {
                                'name': 'security-report',
                                'path': 'backend/infrastructure/aws/iac/security-report.json'
                            }
                        }
                    ]
                }
            }
        }
        
        with open(self.workflows_dir / "infrastructure-validation.yml", 'w') as f:
            yaml.dump(workflow, f, default_flow_style=False, sort_keys=False)
    
    def _generate_blue_green_workflow(self) -> None:
        """Generate blue-green deployment workflow."""
        workflow = {
            'name': 'Blue-Green Deployment',
            'on': {
                'workflow_dispatch': {
                    'inputs': {
                        'environment': {
                            'description': 'Environment for blue-green deployment',
                            'required': True,
                            'default': 'staging',
                            'type': 'choice',
                            'options': ['staging', 'prod']
                        },
                        'validation_timeout': {
                            'description': 'Validation timeout (seconds)',
                            'required': False,
                            'default': '300'
                        }
                    }
                }
            },
            'env': {
                'AWS_REGION': 'us-east-1',
                'CDK_DEFAULT_REGION': 'us-east-1'
            },
            'jobs': {
                'blue-green-deploy': {
                    'runs-on': 'ubuntu-latest',
                    'permissions': {
                        'id-token': 'write',
                        'contents': 'read'
                    },
                    'steps': [
                        {
                            'name': 'Checkout code',
                            'uses': 'actions/checkout@v4'
                        },
                        {
                            'name': 'Configure AWS credentials',
                            'uses': 'aws-actions/configure-aws-credentials@v4',
                            'with': {
                                'role-to-assume': '${{ secrets.AWS_ROLE_ARN }}',
                                'aws-region': '${{ env.AWS_REGION }}'
                            }
                        },
                        {
                            'name': 'Setup Python',
                            'uses': 'actions/setup-python@v4',
                            'with': {
                                'python-version': '3.11'
                            }
                        },
                        {
                            'name': 'Setup Node.js',
                            'uses': 'actions/setup-node@v4',
                            'with': {
                                'node-version': '18'
                            }
                        },
                        {
                            'name': 'Install CDK',
                            'run': 'npm install -g aws-cdk'
                        },
                        {
                            'name': 'Install Python dependencies',
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                pip install -r requirements.txt requests
                            '''
                        },
                        {
                            'name': 'Blue-Green Deployment',
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                python scripts/blue_green_deploy.py \\
                                  --environment ${{ github.event.inputs.environment }} \\
                                  --validation-timeout ${{ github.event.inputs.validation_timeout }}
                            '''
                        },
                        {
                            'name': 'Upload deployment artifacts',
                            'uses': 'actions/upload-artifact@v3',
                            'with': {
                                'name': 'blue-green-deployment-${{ github.event.inputs.environment }}',
                                'path': 'backend/infrastructure/aws/iac/deployment-*.json'
                            }
                        }
                    ]
                }
            }
        }
        
        with open(self.workflows_dir / "blue-green-deployment.yml", 'w') as f:
            yaml.dump(workflow, f, default_flow_style=False, sort_keys=False)
    
    def _generate_rollback_workflow(self) -> None:
        """Generate rollback workflow."""
        workflow = {
            'name': 'Infrastructure Rollback',
            'on': {
                'workflow_dispatch': {
                    'inputs': {
                        'environment': {
                            'description': 'Environment to rollback',
                            'required': True,
                            'type': 'choice',
                            'options': ['dev', 'staging', 'prod']
                        },
                        'backup_id': {
                            'description': 'Backup ID to rollback to',
                            'required': True
                        }
                    }
                }
            },
            'env': {
                'AWS_REGION': 'us-east-1',
                'CDK_DEFAULT_REGION': 'us-east-1'
            },
            'jobs': {
                'rollback': {
                    'runs-on': 'ubuntu-latest',
                    'permissions': {
                        'id-token': 'write',
                        'contents': 'read'
                    },
                    'steps': [
                        {
                            'name': 'Checkout code',
                            'uses': 'actions/checkout@v4'
                        },
                        {
                            'name': 'Configure AWS credentials',
                            'uses': 'aws-actions/configure-aws-credentials@v4',
                            'with': {
                                'role-to-assume': '${{ secrets.AWS_ROLE_ARN }}',
                                'aws-region': '${{ env.AWS_REGION }}'
                            }
                        },
                        {
                            'name': 'Setup Python',
                            'uses': 'actions/setup-python@v4',
                            'with': {
                                'python-version': '3.11'
                            }
                        },
                        {
                            'name': 'Setup Node.js',
                            'uses': 'actions/setup-node@v4',
                            'with': {
                                'node-version': '18'
                            }
                        },
                        {
                            'name': 'Install CDK',
                            'run': 'npm install -g aws-cdk'
                        },
                        {
                            'name': 'Install Python dependencies',
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                pip install -r requirements.txt
                            '''
                        },
                        {
                            'name': 'Confirm rollback',
                            'run': '''
                                echo "Rolling back environment: ${{ github.event.inputs.environment }}"
                                echo "Backup ID: ${{ github.event.inputs.backup_id }}"
                                echo "This action cannot be undone!"
                            '''
                        },
                        {
                            'name': 'Execute rollback',
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                python scripts/deploy.py rollback \\
                                  --environment ${{ github.event.inputs.environment }} \\
                                  --backup-id ${{ github.event.inputs.backup_id }}
                            '''
                        },
                        {
                            'name': 'Validate rollback',
                            'run': '''
                                cd backend/infrastructure/aws/iac
                                python scripts/deploy.py validate --environment ${{ github.event.inputs.environment }}
                            '''
                        }
                    ]
                }
            }
        }
        
        with open(self.workflows_dir / "infrastructure-rollback.yml", 'w') as f:
            yaml.dump(workflow, f, default_flow_style=False, sort_keys=False)
    
    def generate_gitlab_ci(self) -> bool:
        """Generate GitLab CI configuration."""
        print("Generating GitLab CI configuration...")
        
        try:
            gitlab_ci = {
                'stages': ['validate', 'deploy', 'test'],
                'variables': {
                    'AWS_DEFAULT_REGION': 'us-east-1',
                    'CDK_DEFAULT_REGION': 'us-east-1'
                },
                'before_script': [
                    'apt-get update -qq && apt-get install -y -qq git curl python3-pip nodejs npm',
                    'npm install -g aws-cdk',
                    'cd backend/infrastructure/aws/iac',
                    'pip install -r requirements.txt'
                ],
                'validate': {
                    'stage': 'validate',
                    'script': [
                        'python scripts/deploy.py synth --environment dev',
                        'cdk diff --context environment=dev || true'
                    ],
                    'only': ['merge_requests']
                },
                'deploy_dev': {
                    'stage': 'deploy',
                    'script': [
                        'python scripts/deploy.py bootstrap --environment dev',
                        'python scripts/deploy.py deploy --environment dev'
                    ],
                    'only': ['develop'],
                    'environment': {
                        'name': 'development',
                        'url': 'https://api-dev.infrarecovery.com'
                    }
                },
                'deploy_staging': {
                    'stage': 'deploy',
                    'script': [
                        'python scripts/deploy.py bootstrap --environment staging',
                        'python scripts/deploy.py deploy --environment staging'
                    ],
                    'only': ['staging'],
                    'environment': {
                        'name': 'staging',
                        'url': 'https://api-staging.infrarecovery.com'
                    }
                },
                'deploy_prod': {
                    'stage': 'deploy',
                    'script': [
                        'python scripts/blue_green_deploy.py --environment prod'
                    ],
                    'only': ['main'],
                    'when': 'manual',
                    'environment': {
                        'name': 'production',
                        'url': 'https://api.infrarecovery.com'
                    }
                },
                'test_deployment': {
                    'stage': 'test',
                    'script': [
                        'python scripts/deploy.py validate --environment $CI_ENVIRONMENT_NAME'
                    ],
                    'only': ['develop', 'staging', 'main']
                }
            }
            
            with open(self.gitlab_ci_file, 'w') as f:
                yaml.dump(gitlab_ci, f, default_flow_style=False, sort_keys=False)
            
            print("GitLab CI configuration generated successfully")
            return True
            
        except Exception as e:
            print(f"Error generating GitLab CI: {e}")
            return False
    
    def generate_makefile(self) -> bool:
        """Generate Makefile for local development."""
        print("Generating Makefile...")
        
        try:
            makefile_content = '''# Infrastructure Recovery CDK Makefile

.PHONY: help install bootstrap synth deploy destroy validate clean

# Default environment
ENV ?= dev
REGION ?= us-east-1

help: ## Show this help message
\t@echo "Available commands:"
\t@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\\033[36m%-20s\\033[0m %s\\n", $$1, $$2}'

install: ## Install dependencies
\tcd backend/infrastructure/aws/iac && pip install -r requirements.txt
\tnpm install -g aws-cdk

bootstrap: ## Bootstrap CDK
\tcd backend/infrastructure/aws/iac && python scripts/deploy.py bootstrap --environment $(ENV) --region $(REGION)

synth: ## Synthesize CDK templates
\tcd backend/infrastructure/aws/iac && python scripts/deploy.py synth --environment $(ENV) --region $(REGION)

deploy: ## Deploy infrastructure
\tcd backend/infrastructure/aws/iac && python scripts/deploy.py deploy --environment $(ENV) --region $(REGION)

deploy-bg: ## Deploy using blue-green strategy
\tcd backend/infrastructure/aws/iac && python scripts/blue_green_deploy.py --environment $(ENV) --region $(REGION)

destroy: ## Destroy infrastructure
\tcd backend/infrastructure/aws/iac && python scripts/deploy.py destroy --environment $(ENV) --region $(REGION)

validate: ## Validate deployment
\tcd backend/infrastructure/aws/iac && python scripts/deploy.py validate --environment $(ENV) --region $(REGION)

diff: ## Show CDK diff
\tcd backend/infrastructure/aws/iac && cdk diff --context environment=$(ENV)

clean: ## Clean generated files
\tcd backend/infrastructure/aws/iac && rm -f outputs-*.json deployment-*.json
\tcd backend/infrastructure/aws/iac && rm -rf cdk.out/

lint: ## Lint Python code
\tcd backend/infrastructure/aws/iac && flake8 . --max-line-length=120
\tcd backend/infrastructure/aws/iac && black --check .

format: ## Format Python code
\tcd backend/infrastructure/aws/iac && black .

security-scan: ## Run security scan
\tcd backend/infrastructure/aws/iac && bandit -r . -f json -o security-report.json

# Environment-specific shortcuts
dev-deploy: ## Deploy to dev environment
\t$(MAKE) deploy ENV=dev

staging-deploy: ## Deploy to staging environment
\t$(MAKE) deploy ENV=staging

prod-deploy: ## Deploy to production environment (blue-green)
\t$(MAKE) deploy-bg ENV=prod

# Rollback commands
rollback: ## Rollback deployment (requires BACKUP_ID)
\t@if [ -z "$(BACKUP_ID)" ]; then echo "Error: BACKUP_ID is required"; exit 1; fi
\tcd backend/infrastructure/aws/iac && python scripts/deploy.py rollback --environment $(ENV) --backup-id $(BACKUP_ID)

# Monitoring commands
logs: ## View CloudWatch logs
\taws logs describe-log-groups --log-group-name-prefix "/aws/lambda/infra-recovery-$(ENV)"

metrics: ## View CloudWatch metrics
\taws cloudwatch list-metrics --namespace "AWS/Lambda" --dimensions Name=FunctionName,Value=infra-recovery-$(ENV)

# Development commands
local-test: ## Run local tests
\tcd backend && python -m pytest tests/

docker-build: ## Build Docker images
\tdocker build -t infra-recovery-backend -f Dockerfile.backend .

docker-run: ## Run backend in Docker
\tdocker run -p 8000:8000 infra-recovery-backend
'''
            
            with open(self.project_root / "Makefile", 'w') as f:
                f.write(makefile_content)
            
            print("Makefile generated successfully")
            return True
            
        except Exception as e:
            print(f"Error generating Makefile: {e}")
            return False


def main():
    """Main entry point for CI/CD integration script."""
    parser = argparse.ArgumentParser(description='CI/CD Integration Generator')
    parser.add_argument('action', choices=['github', 'gitlab', 'makefile', 'all'])
    
    args = parser.parse_args()
    
    manager = CICDIntegrationManager()
    
    success = True
    
    if args.action in ['github', 'all']:
        success &= manager.generate_github_workflows()
    
    if args.action in ['gitlab', 'all']:
        success &= manager.generate_gitlab_ci()
    
    if args.action in ['makefile', 'all']:
        success &= manager.generate_makefile()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()