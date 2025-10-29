# AWS Migration Troubleshooting Guide

## Overview

This guide provides comprehensive troubleshooting procedures for both AWS managed services and custom infrastructure components during and after the migration process.

## Quick Diagnosis Commands

### System Health Check
```bash
# Check all service health
./scripts/health_check.sh

# Individual service checks
curl -f http://localhost:8000/health          # Backend
curl -f http://localhost:8001/health          # Kommunikationsagent  
curl -f http://localhost:8002/health          # Summarizer
curl -f https://api.dev.meetmind.se/health    # AWS Lambda
```

### AWS Service Status
```bash
# Check AWS service status
aws bedrock-agent get-agent --agent-id meetmind-kommunikation
aws es describe-elasticsearch-domain --domain-name meetmind-search-dev
aws lambda get-function --function-name meetmind-kommunikation
```

### Log Analysis
```bash
# Backend logs
tail -f backend/logs/app.log | grep ERROR

# AWS CloudWatch logs
aws logs tail /aws/lambda/meetmind-kommunikation --follow

# OpenSearch logs
aws es describe-elasticsearch-domain --domain-name meetmind-search-dev \
  --query 'DomainStatus.LogPublishingOptions'
```

## AWS Agent Core Issues

### Issue: Agent Core Memory Initialization Failures

**Symptoms:**
- `AgentCoreError: Failed to initialize agent` in logs
- Memory operations return 500 errors
- Automatic fallback to mem0 triggered

**Diagnosis:**
```bash
# Check agent status
aws bedrock-agent get-agent --agent-id meetmind-kommunikation

# Verify IAM permissions
aws sts get-caller-identity
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT:role/MeetMindLambdaRole \
  --action-names bedrock:InvokeAgent bedrock:RetrieveAndGenerate \
  --resource-arns "*"

# Check agent configuration
python -c "
from backend.services.aws.agent_core import AgentCoreMemory
try:
    memory = AgentCoreMemory('meetmind-kommunikation')
    print('Agent Core accessible')
except Exception as e:
    print(f'Agent Core error: {e}')
"
```

**Solutions:**

1. **Fix IAM Permissions:**
```bash
# Attach required policies
aws iam attach-role-policy \
  --role-name MeetMindLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

# Create custom policy if needed
cat > agent-core-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeAgent",
        "bedrock:RetrieveAndGenerate",
        "bedrock:GetAgent",
        "bedrock:ListAgents"
      ],
      "Resource": "*"
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name MeetMindAgentCorePolicy \
  --policy-document file://agent-core-policy.json
```

2. **Recreate Agent:**
```bash
# Delete and recreate agent
aws bedrock-agent delete-agent --agent-id meetmind-kommunikation
aws bedrock-agent create-agent \
  --agent-name "meetmind-kommunikation" \
  --description "MeetMind Communication Agent" \
  --foundation-model "anthropic.claude-3-sonnet-20240229-v1:0"
```

3. **Enable Fallback Mode:**
```bash
# Temporary fallback to mem0
echo "FALLBACK_TO_MEM0=true" >> backend/kommunikationsagent/.env
echo "AGENT_CORE_RETRY_ATTEMPTS=3" >> backend/kommunikationsagent/.env
cd backend/kommunikationsagent && python agent.py
```

### Issue: Agent Core Session Management Problems

**Symptoms:**
- User contexts (Marcus, Pella) not persisting
- Session data lost between requests
- Memory retrieval returns empty results

**Diagnosis:**
```bash
# Check session data
aws bedrock-agent list-agent-memory-sessions \
  --agent-id meetmind-kommunikation

# Test memory operations
python -c "
from backend.services.aws.agent_core import AgentCoreMemory
memory = AgentCoreMemory('meetmind-kommunikation')
result = memory.add_memory('Test memory', 'marcus')
print(f'Memory add result: {result}')
"
```

**Solutions:**

1. **Fix Session Configuration:**
```bash
# Update session settings
echo "AGENT_CORE_SESSION_TIMEOUT=3600" >> backend/.env
echo "AGENT_CORE_MEMORY_TYPE=SESSION_SUMMARY" >> backend/.env
```

2. **Clear and Reinitialize Sessions:**
```bash
# Clear existing sessions
python scripts/clear_agent_sessions.py --agent-id meetmind-kommunikation

# Reinitialize with test data
python scripts/init_agent_memory.py --agent-id meetmind-kommunikation
```

## OpenSearch Issues

### Issue: OpenSearch Connection Timeouts

**Symptoms:**
- `OpenSearchError: Connection timeout` in logs
- Search queries fail after 30 seconds
- Circuit breaker opens frequently

**Diagnosis:**
```bash
# Check OpenSearch cluster health
curl -X GET "https://OPENSEARCH_ENDPOINT/_cluster/health?pretty"

# Check network connectivity
aws ec2 describe-vpc-endpoints \
  --filters Name=service-name,Values=com.amazonaws.region.es

# Test direct connection
python -c "
from opensearchpy import OpenSearch
client = OpenSearch([{'host': 'OPENSEARCH_ENDPOINT', 'port': 443}])
try:
    info = client.info()
    print(f'OpenSearch version: {info[\"version\"][\"number\"]}')
except Exception as e:
    print(f'Connection error: {e}')
"
```

**Solutions:**

1. **Fix Network Configuration:**
```bash
# Update security group rules
aws ec2 authorize-security-group-ingress \
  --group-id sg-opensearch \
  --protocol tcp \
  --port 443 \
  --source-group sg-lambda

# Check VPC configuration
aws es describe-elasticsearch-domain \
  --domain-name meetmind-search-dev \
  --query 'DomainStatus.VPCOptions'
```

2. **Increase Timeout Settings:**
```bash
# Update timeout configuration
echo "OPENSEARCH_TIMEOUT=60" >> backend/.env
echo "OPENSEARCH_RETRY_ATTEMPTS=3" >> backend/.env
echo "OPENSEARCH_CIRCUIT_BREAKER_THRESHOLD=5" >> backend/.env
```

3. **Enable Fallback Mode:**
```bash
# Temporary fallback to cache
echo "FALLBACK_TO_CACHE=true" >> backend/.env
echo "OPENSEARCH_CIRCUIT_BREAKER_OPEN=true" >> backend/.env
cd backend && python main.py
```

### Issue: OpenSearch Index Creation Failures

**Symptoms:**
- `IndexCreationError: Failed to create index` in logs
- Search operations return 404 errors
- Index mappings not applied correctly

**Diagnosis:**
```bash
# Check existing indices
curl -X GET "https://OPENSEARCH_ENDPOINT/_cat/indices?v"

# Check index mappings
curl -X GET "https://OPENSEARCH_ENDPOINT/meetmind_transcript_*/_mapping?pretty"

# Check index settings
curl -X GET "https://OPENSEARCH_ENDPOINT/meetmind_transcript_*/_settings?pretty"
```

**Solutions:**

1. **Recreate Indices:**
```bash
# Delete existing indices
curl -X DELETE "https://OPENSEARCH_ENDPOINT/meetmind_*"

# Recreate with correct mappings
python -c "
from backend.services.storage.opensearch_service import OpenSearchStorageService
service = OpenSearchStorageService()
service.initialize_indices()
print('Indices recreated successfully')
"
```

2. **Fix Index Templates:**
```bash
# Apply index templates
curl -X PUT "https://OPENSEARCH_ENDPOINT/_index_template/meetmind_template" \
  -H "Content-Type: application/json" \
  -d @backend/services/storage/opensearch_templates.json
```

### Issue: OpenSearch Data Migration Problems

**Symptoms:**
- Migration script fails with data loss
- Inconsistent document counts between systems
- Search results differ between custom and OpenSearch

**Diagnosis:**
```bash
# Compare document counts
python scripts/compare_storage_systems.py --source custom --target opensearch

# Validate migrated data
python scripts/validate_migration.py --tenant-id all --check-integrity

# Check migration logs
tail -f backend/logs/migration.log | grep ERROR
```

**Solutions:**

1. **Restart Migration with Validation:**
```bash
# Clean migration state
python scripts/reset_migration.py --component vector-storage

# Restart with validation
python backend/services/migration/opensearch_migration.py \
  --source custom \
  --target opensearch \
  --validate \
  --batch-size 100
```

2. **Manual Data Verification:**
```bash
# Export and compare data
python scripts/export_vector_data.py --source custom --output custom_data.json
python scripts/export_vector_data.py --source opensearch --output opensearch_data.json
diff custom_data.json opensearch_data.json
```

## Lambda Runtime Issues

### Issue: Lambda Cold Start Performance

**Symptoms:**
- First requests take >2 seconds to respond
- Intermittent timeouts during low traffic periods
- User experience degradation

**Diagnosis:**
```bash
# Check Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=meetmind-kommunikation \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum

# Check cold start frequency
aws logs filter-log-events \
  --log-group-name /aws/lambda/meetmind-kommunikation \
  --filter-pattern "REPORT RequestId" \
  --start-time $(date -d '1 hour ago' +%s)000
```

**Solutions:**

1. **Enable Provisioned Concurrency:**
```bash
# Configure provisioned concurrency
aws lambda put-provisioned-concurrency-config \
  --function-name meetmind-kommunikation \
  --qualifier LIVE \
  --provisioned-concurrency-config ProvisionedConcurrencyConfigs=2

# Update serverless configuration
cat >> backend/lambda/serverless.yml << EOF
functions:
  kommunikationsagent:
    provisionedConcurrency: 2
    reservedConcurrency: 10
EOF
```

2. **Optimize Lambda Package:**
```bash
# Reduce package size
cd backend/lambda
pip install --target ./package -r requirements.txt --no-deps
zip -r deployment-package.zip package/ lambda_function.py

# Update function code
aws lambda update-function-code \
  --function-name meetmind-kommunikation \
  --zip-file fileb://deployment-package.zip
```

3. **Implement Warming Strategy:**
```bash
# Create warming function
cat > lambda_warmer.py << EOF
import json
import boto3

def lambda_handler(event, context):
    lambda_client = boto3.client('lambda')
    
    functions = [
        'meetmind-kommunikation',
        'meetmind-summarizer'
    ]
    
    for function_name in functions:
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',
            Payload=json.dumps({'warm': True})
        )
    
    return {'statusCode': 200}
EOF

# Schedule warming every 5 minutes
aws events put-rule \
  --name lambda-warmer \
  --schedule-expression "rate(5 minutes)"
```

### Issue: Lambda Memory and Timeout Errors

**Symptoms:**
- Lambda functions timeout after 30 seconds
- Out of memory errors in CloudWatch logs
- Incomplete request processing

**Diagnosis:**
```bash
# Check memory usage
aws logs filter-log-events \
  --log-group-name /aws/lambda/meetmind-kommunikation \
  --filter-pattern "Max Memory Used" \
  --start-time $(date -d '1 hour ago' +%s)000

# Check timeout patterns
aws logs filter-log-events \
  --log-group-name /aws/lambda/meetmind-kommunikation \
  --filter-pattern "Task timed out" \
  --start-time $(date -d '1 hour ago' +%s)000
```

**Solutions:**

1. **Increase Memory and Timeout:**
```bash
# Update function configuration
aws lambda update-function-configuration \
  --function-name meetmind-kommunikation \
  --memory-size 1024 \
  --timeout 60

# Update serverless configuration
cat >> backend/lambda/serverless.yml << EOF
functions:
  kommunikationsagent:
    memorySize: 1024
    timeout: 60
  summarizer:
    memorySize: 2048
    timeout: 120
EOF
```

2. **Optimize Memory Usage:**
```bash
# Profile memory usage
python -c "
import tracemalloc
tracemalloc.start()

# Your Lambda code here
from lambda_kommunikationsagent import lambda_handler
result = lambda_handler({'test': True}, None)

current, peak = tracemalloc.get_traced_memory()
print(f'Current memory usage: {current / 1024 / 1024:.1f} MB')
print(f'Peak memory usage: {peak / 1024 / 1024:.1f} MB')
tracemalloc.stop()
"
```

### Issue: Lambda Integration with LiveKit

**Symptoms:**
- WebSocket connections fail from Lambda
- LiveKit room creation errors
- Real-time communication broken

**Diagnosis:**
```bash
# Check LiveKit connectivity
python -c "
import asyncio
from livekit import api

async def test_livekit():
    try:
        token = api.AccessToken()
        print('LiveKit token created successfully')
    except Exception as e:
        print(f'LiveKit error: {e}')

asyncio.run(test_livekit())
"

# Check Lambda VPC configuration
aws lambda get-function-configuration \
  --function-name meetmind-kommunikation \
  --query 'VpcConfig'
```

**Solutions:**

1. **Configure VPC for Lambda:**
```bash
# Update Lambda VPC configuration
aws lambda update-function-configuration \
  --function-name meetmind-kommunikation \
  --vpc-config SubnetIds=subnet-12345,SecurityGroupIds=sg-livekit

# Ensure NAT Gateway for internet access
aws ec2 describe-nat-gateways \
  --filter Name=vpc-id,Values=vpc-12345
```

2. **Use API Gateway WebSocket:**
```bash
# Create WebSocket API
aws apigatewayv2 create-api \
  --name meetmind-websocket \
  --protocol-type WEBSOCKET \
  --route-selection-expression '$request.body.action'

# Connect to Lambda
aws apigatewayv2 create-integration \
  --api-id API_ID \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:region:account:function:meetmind-kommunikation
```

## Custom Infrastructure Issues

### Issue: Custom Rate Limiter Performance

**Symptoms:**
- High latency on rate-limited endpoints
- Redis connection timeouts
- Rate limit counters inconsistent

**Diagnosis:**
```bash
# Check Redis connectivity
redis-cli ping

# Monitor rate limiter performance
python -c "
from backend.services.infrastructure.rate_limiter import RateLimiter
limiter = RateLimiter()
print(f'Rate limiter status: {limiter.get_status()}')
"

# Check rate limit metrics
curl http://localhost:8000/metrics | grep rate_limit
```

**Solutions:**

1. **Optimize Redis Configuration:**
```bash
# Update Redis settings
echo "maxmemory 256mb" >> /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" >> /etc/redis/redis.conf
systemctl restart redis
```

2. **Tune Rate Limiter:**
```bash
# Update rate limiter configuration
echo "RATE_LIMIT_WINDOW=60" >> backend/.env
echo "RATE_LIMIT_MAX_REQUESTS=1000" >> backend/.env
echo "RATE_LIMIT_REDIS_POOL_SIZE=20" >> backend/.env
```

### Issue: Custom Load Balancer Health Checks

**Symptoms:**
- Services marked unhealthy incorrectly
- Traffic not distributed evenly
- Health check failures during high load

**Diagnosis:**
```bash
# Check load balancer status
python -c "
from backend.services.infrastructure.load_balancer import LoadBalancer
lb = LoadBalancer()
print(f'Load balancer status: {lb.get_health_status()}')
"

# Monitor backend health
for port in 8000 8001 8002; do
  curl -f http://localhost:$port/health || echo "Port $port unhealthy"
done
```

**Solutions:**

1. **Adjust Health Check Parameters:**
```bash
# Update health check configuration
echo "HEALTH_CHECK_INTERVAL=10" >> backend/.env
echo "HEALTH_CHECK_TIMEOUT=5" >> backend/.env
echo "HEALTH_CHECK_RETRIES=3" >> backend/.env
```

2. **Implement Circuit Breaker:**
```bash
# Enable circuit breaker for health checks
echo "CIRCUIT_BREAKER_ENABLED=true" >> backend/.env
echo "CIRCUIT_BREAKER_FAILURE_THRESHOLD=5" >> backend/.env
```

### Issue: Custom Cache Manager Memory Issues

**Symptoms:**
- Cache hit ratio below 80%
- Memory usage continuously increasing
- Cache eviction errors

**Diagnosis:**
```bash
# Check cache statistics
python -c "
from backend.services.infrastructure.cache_manager import CacheManager
cache = CacheManager()
stats = cache.get_statistics()
print(f'Cache hit ratio: {stats[\"hit_ratio\"]}%')
print(f'Memory usage: {stats[\"memory_usage\"]}MB')
"

# Monitor Redis memory
redis-cli info memory
```

**Solutions:**

1. **Optimize Cache Configuration:**
```bash
# Update cache settings
echo "CACHE_MAX_MEMORY=512MB" >> backend/.env
echo "CACHE_TTL_DEFAULT=3600" >> backend/.env
echo "CACHE_COMPRESSION_ENABLED=true" >> backend/.env
```

2. **Implement Cache Warming:**
```bash
# Warm cache with frequently accessed data
python scripts/warm_cache.py --preload-users --preload-sessions
```

## Circuit Breaker and Fallback Issues

### Issue: Circuit Breaker Not Triggering

**Symptoms:**
- AWS service failures not triggering fallback
- Circuit breaker remains closed during outages
- No automatic recovery to custom infrastructure

**Diagnosis:**
```bash
# Check circuit breaker status
python -c "
from backend.services.aws.circuit_breaker import AWSCircuitBreaker
cb = AWSCircuitBreaker()
print(f'Circuit breaker state: {cb.state}')
print(f'Failure count: {cb.failure_count}')
"

# Monitor failure patterns
grep "AWS.*failed" backend/logs/app.log | tail -20
```

**Solutions:**

1. **Adjust Circuit Breaker Thresholds:**
```bash
# Update circuit breaker configuration
echo "CIRCUIT_BREAKER_FAILURE_THRESHOLD=3" >> backend/.env
echo "CIRCUIT_BREAKER_TIMEOUT=30" >> backend/.env
echo "CIRCUIT_BREAKER_HALF_OPEN_TIMEOUT=10" >> backend/.env
```

2. **Test Circuit Breaker Manually:**
```bash
# Force circuit breaker open for testing
python -c "
from backend.services.aws.circuit_breaker import AWSCircuitBreaker
cb = AWSCircuitBreaker()
cb.force_open()
print('Circuit breaker forced open for testing')
"
```

### Issue: Fallback Performance Degradation

**Symptoms:**
- Fallback to custom infrastructure is slow
- Data inconsistency between AWS and custom systems
- Users experience service interruption during fallback

**Diagnosis:**
```bash
# Compare performance between systems
python scripts/performance_comparison.py \
  --test-duration 60 \
  --concurrent-users 10

# Check data synchronization
python scripts/data_sync_check.py --compare-all
```

**Solutions:**

1. **Optimize Fallback Performance:**
```bash
# Pre-warm custom infrastructure
python scripts/warm_custom_infrastructure.py

# Update fallback configuration
echo "FALLBACK_WARMUP_ENABLED=true" >> backend/.env
echo "FALLBACK_SYNC_INTERVAL=30" >> backend/.env
```

2. **Implement Gradual Fallback:**
```bash
# Enable gradual traffic shifting
echo "GRADUAL_FALLBACK_ENABLED=true" >> backend/.env
echo "FALLBACK_TRAFFIC_PERCENTAGE=10" >> backend/.env
```

## Monitoring and Alerting Issues

### Issue: Missing AWS Service Metrics

**Symptoms:**
- CloudWatch dashboards show no data
- Alerts not triggering for service failures
- Performance metrics unavailable

**Diagnosis:**
```bash
# Check CloudWatch metrics
aws cloudwatch list-metrics \
  --namespace AWS/Lambda \
  --metric-name Duration

# Verify metric filters
aws logs describe-metric-filters \
  --log-group-name /aws/lambda/meetmind-kommunikation
```

**Solutions:**

1. **Configure CloudWatch Metrics:**
```bash
# Create custom metrics
aws cloudwatch put-metric-data \
  --namespace MeetMind/Migration \
  --metric-data MetricName=MigrationHealth,Value=1,Unit=Count

# Set up metric filters
aws logs put-metric-filter \
  --log-group-name /aws/lambda/meetmind-kommunikation \
  --filter-name ErrorCount \
  --filter-pattern "ERROR" \
  --metric-transformations \
    metricName=LambdaErrors,metricNamespace=MeetMind,metricValue=1
```

2. **Create CloudWatch Alarms:**
```bash
# Create error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "Lambda-Error-Rate" \
  --alarm-description "Lambda error rate too high" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

## Emergency Procedures

### Complete System Recovery

If all systems fail:

```bash
#!/bin/bash
# emergency_recovery.sh

echo "EMERGENCY: Starting complete system recovery"

# Step 1: Stop all services
pkill -f "python.*main.py"
pkill -f "python.*agent.py"

# Step 2: Reset to known good state
git checkout main
git pull origin main

# Step 3: Disable all AWS integrations
cat > backend/.env.emergency << EOF
USE_AGENT_CORE_MEMORY=false
USE_OPENSEARCH_STORAGE=false
USE_LAMBDA_RUNTIME=false
FALLBACK_TO_CUSTOM=true
EMERGENCY_MODE=true
EOF

cp backend/.env.emergency backend/.env

# Step 4: Start custom infrastructure only
cd backend
python main.py &
sleep 5

cd kommunikationsagent
python agent.py &
sleep 5

cd ../summarizer
python summarizer_agent.py &
sleep 5

# Step 5: Validate recovery
curl -f http://localhost:8000/health || {
  echo "CRITICAL: Recovery failed"
  exit 1
}

echo "RECOVERY: System restored to custom infrastructure"
echo "Next steps: Investigate root cause and plan re-migration"
```

### Data Backup and Recovery

```bash
#!/bin/bash
# backup_recovery.sh

# Backup all critical data
mkdir -p backups/$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=backups/$(date +%Y%m%d_%H%M%S)

# Backup databases
sqlite3 backend/meetings.db ".backup $BACKUP_DIR/meetings.db"

# Backup configuration
cp backend/.env $BACKUP_DIR/
cp backend/kommunikationsagent/.env $BACKUP_DIR/kommunikationsagent.env

# Backup logs
cp -r backend/logs $BACKUP_DIR/

# Export AWS data if accessible
if aws sts get-caller-identity &>/dev/null; then
  aws bedrock-agent list-agents > $BACKUP_DIR/agents.json
  # Add other AWS exports as needed
fi

echo "Backup completed: $BACKUP_DIR"
```

## Support Escalation

### Internal Escalation Path
1. **Level 1**: Development team self-service using this guide
2. **Level 2**: Senior developer review and advanced troubleshooting
3. **Level 3**: Architecture team for design-level issues
4. **Level 4**: AWS support for managed service issues

### External Support Resources
- **AWS Support**: For managed service issues
- **Community Forums**: For open-source component issues
- **Vendor Support**: For third-party service issues

### Emergency Contacts
- **On-call Developer**: Available 24/7 for critical issues
- **AWS TAM**: For escalated AWS service issues
- **Infrastructure Team**: For network and security issues

Remember: When in doubt, prioritize system stability and user experience. It's better to run on custom infrastructure temporarily than to have a broken system.