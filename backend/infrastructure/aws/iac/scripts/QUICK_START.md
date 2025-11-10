# LLM Service Deployment - Quick Start Guide

## Prerequisites

```bash
# Install required tools
pip install boto3 botocore

# Configure AWS CLI
aws configure
```

## 5-Minute Deployment

### Step 1: Deploy Infrastructure (2 minutes)

```bash
cd backend/infrastructure/aws/iac/scripts

# Deploy to production
python deploy_llm_infrastructure.py \
  --environment prod \
  --region us-east-1
```

**Expected output:**
```
✅ DEPLOYMENT COMPLETED SUCCESSFULLY
   - DynamoDB table created
   - ElastiCache cluster created
   - IAM resources created
   - Secrets configured
```

### Step 2: Update API Keys (1 minute)

```bash
# Update OpenAI API key
aws secretsmanager put-secret-value \
  --secret-id happyos/openai-api-key-prod \
  --secret-string "sk-YOUR_ACTUAL_OPENAI_KEY"

# Update Google API key (optional)
aws secretsmanager put-secret-value \
  --secret-id happyos/google-api-key-prod \
  --secret-string "YOUR_ACTUAL_GOOGLE_KEY"
```

### Step 3: Validate Deployment (1 minute)

```bash
# Run validation
python validate_llm_deployment.py \
  --environment prod \
  --region us-east-1
```

**Expected output:**
```
✅ ALL VALIDATION CHECKS PASSED
   LLM service infrastructure is properly deployed
```

### Step 4: Configure Application (1 minute)

Add to your `.env.production`:

```bash
# Copy from deployment output
DYNAMODB_LLM_USAGE_TABLE=happyos-llm-usage-prod
ELASTICACHE_CLUSTER=happyos-llm-cache-prod.abc123.0001.use1.cache.amazonaws.com:6379
AWS_REGION=us-east-1
```

### Step 5: Start Monitoring

```bash
# Monitor for 24 hours
python monitor_llm_deployment.py \
  --environment prod \
  --region us-east-1 \
  --duration 24 \
  --interval 5
```

## Quick Commands

### Check Status
```bash
python validate_llm_deployment.py --environment prod --region us-east-1
```

### View Metrics
```bash
python monitor_llm_deployment.py --environment prod --duration 1
```

### Emergency Rollback
```bash
# Disable LLM service (safest)
python rollback_llm_deployment.py --environment prod --action disable-llm

# Switch to OpenAI-only
python rollback_llm_deployment.py --environment prod --action openai-only
```

## Troubleshooting

### Issue: "API key not found"
```bash
# Check secret
aws secretsmanager get-secret-value --secret-id happyos/openai-api-key-prod

# Update secret
aws secretsmanager put-secret-value \
  --secret-id happyos/openai-api-key-prod \
  --secret-string "sk-YOUR_KEY"
```

### Issue: "Circuit breaker open"
```bash
# Switch to OpenAI-only mode
python rollback_llm_deployment.py --environment prod --action openai-only
```

### Issue: "High latency"
```bash
# Check cache hit rate
python monitor_llm_deployment.py --environment prod --duration 1

# Should see cache hit rate > 20%
```

## Success Criteria

After deployment, verify:
- ✓ Error rate < 1%
- ✓ P95 latency < 2 seconds
- ✓ Daily cost < $100
- ✓ Cache hit rate > 20%
- ✓ Circuit breaker CLOSED
- ✓ All agents functioning

## Next Steps

1. Deploy application code
2. Monitor for 24 hours
3. Review metrics and optimize
4. Set up CloudWatch alarms
5. Document any issues

## Support

- **Full Documentation**: [README_DEPLOYMENT.md](README_DEPLOYMENT.md)
- **Deployment Guide**: [docs/llm_deployment_guide.md](../../../../../docs/llm_deployment_guide.md)
- **GitHub Issues**: https://github.com/happyfuckingai/HappyOS-hackathon/issues
