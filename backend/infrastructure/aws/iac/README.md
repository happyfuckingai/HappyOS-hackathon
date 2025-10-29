# Infrastructure Recovery - AWS CDK

This directory contains the AWS CDK (Cloud Development Kit) infrastructure code for the Infrastructure Recovery multi-tenant agent platform.

## Overview

The CDK application provisions a complete AWS infrastructure with:
- Multi-tenant isolation
- Auto-scaling capabilities
- Circuit breaker patterns
- Blue-green deployment support
- Comprehensive monitoring

## Architecture

### Core Components

- **VPC Stack**: Network isolation with security groups
- **OpenSearch Stack**: Managed search with tenant indices
- **Lambda Stack**: Serverless compute for agent runtime
- **API Gateway Stack**: Request routing and throttling
- **ElastiCache Stack**: Redis caching layer
- **CloudWatch Stack**: Metrics and logging
- **KMS/Secrets Stack**: Key management and secrets
- **IAM Stack**: Role-based access control

### Multi-Tenant Design

Each tenant gets:
- Isolated OpenSearch indices with prefix: `{tenant}-`
- Dedicated Lambda functions: `{tenant}-{agent}`
- Separate cache namespaces: `{tenant}:`
- Tenant-specific IAM roles and policies

## Prerequisites

### Software Requirements

```bash
# Install Node.js (for CDK CLI)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install AWS CDK CLI
npm install -g aws-cdk

# Install Python dependencies
pip install -r requirements.txt
```

### AWS Configuration

```bash
# Configure AWS credentials
aws configure

# Set environment variables
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1
export CDK_ENVIRONMENT=dev  # or staging, prod
```

## Quick Start

### 1. Bootstrap CDK

```bash
# Bootstrap CDK in your AWS account
python scripts/deploy.py bootstrap --environment dev
```

### 2. Deploy Infrastructure

```bash
# Standard deployment
python scripts/deploy.py deploy --environment dev

# Blue-green deployment (for production)
python scripts/blue_green_deploy.py --environment prod
```

### 3. Validate Deployment

```bash
python scripts/deploy.py validate --environment dev
```

## Configuration

### Environment Configuration

Configuration is managed through `config/environment_config.py`:

```python
# Tenant configuration
tenants = {
    'meetmind': {
        'domain': 'meetmind.se',
        'agents': ['summarizer', 'pipeline'],
        'resource_limits': {'max_memory': 1024}
    }
}

# Network configuration per environment
network_configs = {
    'dev': NetworkConfig(
        vpc_cidr='10.0.0.0/16',
        availability_zones=['us-east-1a', 'us-east-1b']
    )
}
```

### Parameter Management

Parameters are defined in `config/parameters.py` and can be overridden via environment variables:

```bash
export CDK_PARAM_OPENSEARCH_INSTANCE_TYPE=t3.medium.search
export CDK_PARAM_LAMBDA_MEMORY_SIZE=1024
```

## Deployment Strategies

### Standard Deployment

For development and staging environments:

```bash
make deploy ENV=dev
```

### Blue-Green Deployment

For production zero-downtime deployments:

```bash
make deploy-bg ENV=prod
```

The blue-green process:
1. Deploys to inactive environment (blue/green)
2. Validates new deployment
3. Gradually switches traffic (10%, 25%, 50%, 75%, 100%)
4. Cleans up old environment

### Rollback

If deployment fails or issues are detected:

```bash
make rollback ENV=prod BACKUP_ID=prod-1234567890
```

## CI/CD Integration

### GitHub Actions

Generate workflows:

```bash
python scripts/ci_cd_integration.py github
```

This creates:
- `infrastructure-deployment.yml`: Main deployment workflow
- `infrastructure-validation.yml`: PR validation
- `blue-green-deployment.yml`: Production deployments
- `infrastructure-rollback.yml`: Emergency rollback

### GitLab CI

Generate GitLab CI configuration:

```bash
python scripts/ci_cd_integration.py gitlab
```

### Local Development

Use the generated Makefile:

```bash
python scripts/ci_cd_integration.py makefile

# Then use make commands
make help
make dev-deploy
make staging-deploy
make prod-deploy
```

## Monitoring and Observability

### CloudWatch Dashboards

Access the generated dashboard:
- URL: `https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards`
- Dashboard name: `infra-recovery-{environment}-dashboard`

### Key Metrics

- Lambda function invocations and errors
- API Gateway request counts and latency
- OpenSearch cluster health
- ElastiCache performance
- Circuit breaker status

### Alarms

Automatic alarms for:
- Lambda error rates > 10 errors/5min
- API Gateway 4xx errors > 50/5min
- High resource utilization

### Logs

Centralized logging in CloudWatch:
- Application logs: `/aws/lambda/infra-recovery-{env}-{function}`
- API Gateway logs: `/aws/apigateway/infra-recovery-{env}-api`
- Circuit breaker logs: `/aws/lambda/infra-recovery-{env}-circuit-breaker`

## Security

### IAM Roles

- **Lambda Execution Role**: Minimal permissions for function execution
- **Tenant Roles**: Isolated access per tenant
- **Service Roles**: Specific permissions for each AWS service

### Encryption

- **KMS Keys**: Separate keys for general encryption and secrets
- **Secrets Manager**: Encrypted storage for sensitive configuration
- **Transit Encryption**: HTTPS/TLS for all communications

### Network Security

- **VPC**: Isolated network with private subnets
- **Security Groups**: Restrictive ingress/egress rules
- **VPC Endpoints**: Private communication with AWS services

## Troubleshooting

### Common Issues

1. **CDK Bootstrap Failed**
   ```bash
   # Ensure AWS credentials are configured
   aws sts get-caller-identity
   
   # Check CDK version
   cdk --version
   ```

2. **Deployment Timeout**
   ```bash
   # Check CloudFormation events
   aws cloudformation describe-stack-events --stack-name InfraRecovery-dev-Vpc
   ```

3. **Lambda Function Errors**
   ```bash
   # View function logs
   aws logs tail /aws/lambda/infra-recovery-dev-meetmind-summarizer --follow
   ```

### Debug Commands

```bash
# CDK diff to see changes
cdk diff --context environment=dev

# List all stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE

# Describe specific stack
aws cloudformation describe-stacks --stack-name InfraRecovery-dev-Lambda
```

## Development

### Project Structure

```
backend/infrastructure/aws/iac/
├── app.py                 # CDK app entry point
├── cdk.json              # CDK configuration
├── requirements.txt      # Python dependencies
├── config/
│   ├── environment_config.py  # Environment settings
│   └── parameters.py          # Parameter management
├── stacks/
│   ├── base_stack.py         # Base stack class
│   ├── vpc_stack.py          # VPC and networking
│   ├── lambda_stack.py       # Lambda functions
│   ├── api_gateway_stack.py  # API Gateway
│   ├── opensearch_stack.py   # OpenSearch cluster
│   ├── elasticache_stack.py  # ElastiCache Redis
│   ├── cloudwatch_stack.py   # Monitoring
│   ├── kms_secrets_stack.py  # Security
│   └── iam_stack.py          # IAM roles
└── scripts/
    ├── deploy.py             # Deployment automation
    ├── blue_green_deploy.py  # Blue-green deployments
    └── ci_cd_integration.py  # CI/CD generation
```

### Adding New Stacks

1. Create new stack class inheriting from `BaseStack`
2. Add to `app.py` with proper dependencies
3. Update configuration if needed
4. Test with `cdk synth`

### Testing

```bash
# Lint code
make lint

# Security scan
make security-scan

# Synthesize templates
make synth ENV=dev

# Deploy to dev for testing
make dev-deploy
```

## Cost Optimization

### Environment Sizing

- **Dev**: Minimal resources, single AZ
- **Staging**: Medium resources, multi-AZ
- **Prod**: Full resources, high availability

### Auto-scaling

- Lambda: Automatic based on demand
- OpenSearch: Manual scaling based on usage
- ElastiCache: Fixed size per environment

### Cost Monitoring

Set up billing alerts:
```bash
aws budgets create-budget --account-id $CDK_DEFAULT_ACCOUNT --budget file://budget.json
```

## Support

For issues and questions:
1. Check CloudWatch logs and metrics
2. Review CloudFormation events
3. Validate configuration parameters
4. Test with smaller deployments first

## License

This infrastructure code is part of the Infrastructure Recovery project.