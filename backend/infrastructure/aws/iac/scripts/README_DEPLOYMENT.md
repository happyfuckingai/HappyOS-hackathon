# LLM Service Production Deployment Scripts

This directory contains comprehensive scripts for deploying, validating, monitoring, and rolling back the LLM service infrastructure in AWS.

## Overview

The LLM service deployment consists of:
- **DynamoDB**: Usage logging and cost tracking
- **ElastiCache**: Response caching for performance
- **AWS Bedrock**: Primary LLM provider (Claude models)
- **Secrets Manager**: Secure API key storage
- **IAM**: Roles and policies for service access
- **CloudWatch**: Logging and monitoring

## Scripts

### 1. deploy_llm_infrastructure.py

Deploy all LLM service infrastructure to AWS.

**Usage:**
```bash
# Deploy to production
python deploy_llm_infrastructure.py --environment prod --region us-east-1

# Deploy to staging
python deploy_llm_infrastructure.py --environment staging --region us-east-1

# Dry run (show what would be deployed)
python deploy_llm_infrastructure.py --environment prod --region us-east-1 --dry-run

# Test connectivity only
python deploy_llm_infrastructure.py --environment prod --region us-east-1 --test-only
```

**What it deploys:**
- DynamoDB table with GSIs for tenant and agent queries
- ElastiCache Redis cluster for caching
- IAM role and policy for service access
- Secrets Manager placeholders for API keys
- CloudWatch log group with retention policy

**After deployment:**
1. Update Secrets Manager with actual API keys
2. Configure environment variables in your application
3. Deploy application code
4. Run validation script

### 2. validate_llm_deployment.py

Validate that all infrastructure is properly deployed and configured.

**Usage:**
```bash
# Validate production deployment
python validate_llm_deployment.py --environment prod --region us-east-1

# Validate staging
python validate_llm_deployment.py --environment staging --region us-east-1
```

**Checks performed:**
- ✓ DynamoDB table exists and is ACTIVE
- ✓ Global Secondary Indexes are configured
- ✓ ElastiCache cluster is available
- ✓ IAM role and policies are attached
- ✓ Bedrock access is configured
- ✓ Secrets Manager secrets exist
- ✓ CloudWatch log group is configured

**Exit codes:**
- 0: All checks passed
- 1: One or more checks failed

### 3. monitor_llm_deployment.py

Monitor LLM service deployment in real-time.

**Usage:**
```bash
# Monitor for 24 hours (default)
python monitor_llm_deployment.py --environment prod --region us-east-1

# Monitor for 1 hour with 1-minute intervals
python monitor_llm_deployment.py --environment prod --region us-east-1 --duration 1 --interval 1

# Monitor for 48 hours
python monitor_llm_deployment.py --environment prod --region us-east-1 --duration 48
```

**Metrics tracked:**
- 📊 Request count and rate
- ⏱️ Latency (min, avg, p50, p95, p99, max)
- ❌ Error rate
- 💰 Cost per hour and estimated daily cost
- 🔄 Cache hit rate
- 🔌 Circuit breaker state
- 🤖 Per-agent metrics

**Alerts triggered for:**
- Error rate > 5%
- P95 latency > 5000ms
- Daily cost > $100
- Cache hit rate < 20%
- Circuit breaker OPEN

### 4. rollback_llm_deployment.py

Rollback procedures for deployment issues.

**Usage:**

#### Disable LLM Service (Safest)
```bash
# All agents will use fallback logic
python rollback_llm_deployment.py --environment prod --action disable-llm
```

#### Switch to OpenAI-Only Mode
```bash
# Disable Bedrock, use OpenAI as primary
python rollback_llm_deployment.py --environment prod --action openai-only
```

#### List Available Backups
```bash
python rollback_llm_deployment.py --environment prod --action list-backups
```

#### Restore from Backup
```bash
python rollback_llm_deployment.py --environment prod --action restore --backup-arn <ARN>
```

#### Create Incident Response Plan
```bash
python rollback_llm_deployment.py --environment prod --action create-plan
```

#### Complete Teardown (Emergency Only)
```bash
# WARNING: This deletes all infrastructure!
python rollback_llm_deployment.py --environment prod --action teardown --confirm
```

## Deployment Workflow

### Initial Deployment

```bash
# 1. Deploy infrastructure
python deploy_llm_infrastructure.py --environment prod --region us-east-1

# 2. Update API keys in Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id happyos/openai-api-key-prod \
  --secret-string "OPENAI_KEY_HERE"

# 3. Validate deployment
python validate_llm_deployment.py --environment prod --region us-east-1

# 4. Deploy application code
# (Use your CI/CD pipeline or manual deployment)

# 5. Start monitoring
python monitor_llm_deployment.py --environment prod --region us-east-1 --duration 24
```

### Monitoring Production

```bash
# Real-time monitoring (recommended for first 24 hours)
python monitor_llm_deployment.py --environment prod --region us-east-1 --duration 24 --interval 5

# Quick health check
python validate_llm_deployment.py --environment prod --region us-east-1

# View CloudWatch logs
aws logs tail /aws/happyos/llm-service-prod --follow

# Check metrics
aws cloudwatch get-metric-statistics \
  --namespace HappyOS/LLM \
  --metric-name llm_requests_total \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### Handling Issues

#### High Error Rate
```bash
# 1. Check logs for errors
aws logs tail /aws/happyos/llm-service-prod --filter-pattern "ERROR"

# 2. Validate infrastructure
python validate_llm_deployment.py --environment prod

# 3. If Bedrock issues, switch to OpenAI-only
python rollback_llm_deployment.py --environment prod --action openai-only

# 4. If all providers failing, disable LLM
python rollback_llm_deployment.py --environment prod --action disable-llm
```

#### High Latency
```bash
# 1. Check cache hit rate
python monitor_llm_deployment.py --environment prod --duration 1

# 2. Verify ElastiCache connectivity
aws elasticache describe-cache-clusters --cache-cluster-id happyos-llm-cache-prod

# 3. Consider scaling ElastiCache
aws elasticache modify-cache-cluster \
  --cache-cluster-id happyos-llm-cache-prod \
  --cache-node-type cache.r6g.xlarge
```

#### High Cost
```bash
# 1. Identify high-usage agents
python monitor_llm_deployment.py --environment prod --duration 1

# 2. Review agent prompts for optimization
# 3. Increase cache TTL in application config
# 4. Consider using cheaper models (gpt-3.5-turbo)
```

#### Data Loss
```bash
# 1. List available backups
python rollback_llm_deployment.py --environment prod --action list-backups

# 2. Restore from backup
python rollback_llm_deployment.py --environment prod --action restore --backup-arn <ARN>

# 3. Update application config with restored table name
```

## Environment Variables

After deployment, configure these environment variables in your application:

```bash
# AWS Configuration
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# DynamoDB
DYNAMODB_LLM_USAGE_TABLE=happyos-llm-usage-prod

# ElastiCache
ELASTICACHE_CLUSTER=happyos-llm-cache-prod.abc123.0001.use1.cache.amazonaws.com:6379
ELASTICACHE_TTL=3600

# API Keys (from Secrets Manager)
OPENAI_API_KEY=${OPENAI_API_KEY_FROM_SECRETS}
GOOGLE_API_KEY=${GOOGLE_API_KEY_FROM_SECRETS}

# Application
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

## Monitoring Dashboards

### CloudWatch Dashboard
```bash
# View dashboard
aws cloudwatch get-dashboard --dashboard-name HappyOS-LLM-Service
```

### Grafana Dashboard (Optional)
```bash
# Import dashboard
# File: backend/modules/observability/dashboards/llm_usage_dashboard.json
```

## Alerts

Configure CloudWatch alarms for:

```bash
# High error rate
aws cloudwatch put-metric-alarm \
  --alarm-name happyos-llm-high-error-rate \
  --metric-name llm_errors_total \
  --namespace HappyOS/LLM \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold

# High cost
aws cloudwatch put-metric-alarm \
  --alarm-name happyos-llm-high-cost \
  --metric-name llm_cost_total \
  --namespace HappyOS/LLM \
  --statistic Sum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold

# Circuit breaker open
aws cloudwatch put-metric-alarm \
  --alarm-name happyos-llm-circuit-breaker-open \
  --metric-name circuit_breaker_state \
  --namespace HappyOS/LLM \
  --statistic Maximum \
  --period 60 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold
```

## Troubleshooting

### Script Errors

**"Table already exists"**
- This is normal if re-running deployment
- Script will skip creation and verify existing table

**"Cluster not found"**
- ElastiCache cluster may still be creating
- Wait 5-10 minutes and run validation again

**"Access denied"**
- Verify AWS credentials are configured
- Check IAM permissions for your user/role

**"Bedrock not available"**
- Bedrock may not be available in your region
- Request model access in AWS Console
- LLM service will use OpenAI fallback

### Application Issues

**"API key not found"**
```bash
# Verify secret exists
aws secretsmanager get-secret-value --secret-id happyos/openai-api-key-prod

# Update if needed
aws secretsmanager put-secret-value \
  --secret-id happyos/openai-api-key-prod \
  --secret-string "sk-YOUR_KEY"
```

**"Circuit breaker open"**
```bash
# Check circuit breaker state
python monitor_llm_deployment.py --environment prod --duration 1

# Switch to OpenAI-only if Bedrock issues
python rollback_llm_deployment.py --environment prod --action openai-only
```

**"High latency"**
```bash
# Check cache hit rate
python monitor_llm_deployment.py --environment prod --duration 1

# Verify ElastiCache connectivity
redis-cli -h happyos-llm-cache-prod.abc123.0001.use1.cache.amazonaws.com ping
```

## Best Practices

### Deployment
- ✓ Always run dry-run first
- ✓ Deploy to staging before production
- ✓ Validate after deployment
- ✓ Monitor for 24 hours after deployment
- ✓ Have rollback plan ready

### Monitoring
- ✓ Monitor continuously for first 24 hours
- ✓ Set up CloudWatch alarms
- ✓ Review metrics daily
- ✓ Track cost trends
- ✓ Optimize based on usage patterns

### Security
- ✓ Store API keys in Secrets Manager
- ✓ Rotate keys regularly
- ✓ Use different keys per environment
- ✓ Enable CloudTrail logging
- ✓ Review IAM policies regularly

### Cost Optimization
- ✓ Monitor daily costs
- ✓ Optimize cache TTL
- ✓ Use cheaper models when appropriate
- ✓ Implement rate limiting
- ✓ Review and optimize prompts

## Support

### Documentation
- **LLM Service API**: [backend/core/llm/README.md](../../../core/llm/README.md)
- **Deployment Guide**: [docs/llm_deployment_guide.md](../../../../../docs/llm_deployment_guide.md)
- **Architecture**: [README.md](../../../../../README.md)

### Resources
- **AWS Bedrock**: https://aws.amazon.com/bedrock/
- **OpenAI API**: https://platform.openai.com/docs
- **ElastiCache**: https://aws.amazon.com/elasticache/
- **DynamoDB**: https://aws.amazon.com/dynamodb/

### Contact
- **GitHub Issues**: https://github.com/happyfuckingai/HappyOS-hackathon/issues
- **Team Slack**: #llm-service
- **Email**: support@happyos.ai

---

**Last Updated**: 2024-01-15  
**Version**: 1.0.0  
**Maintained By**: HappyOS Team
