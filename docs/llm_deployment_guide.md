# LLM Service Deployment Guide

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Local Development Setup](#local-development-setup)
4. [AWS Infrastructure Setup](#aws-infrastructure-setup)
5. [Production Deployment](#production-deployment)
6. [Monitoring Setup](#monitoring-setup)
7. [Troubleshooting](#troubleshooting)
8. [Rollback Procedures](#rollback-procedures)

---

## Overview

This guide covers the complete deployment process for the HappyOS LLM Service, from local development to production AWS deployment. The LLM Service provides centralized AI capabilities to all agents (MeetMind, Agent Svea, Felicia's Finance) with automatic failover and caching.

### Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Production Stack                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Application Layer                        │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐    │  │
│  │  │  MeetMind  │  │Agent Svea  │  │  Felicia's │    │  │
│  │  │   Agents   │  │   Agents   │  │   Finance  │    │  │
│  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘    │  │
│  │        └────────────────┼────────────────┘           │  │
│  └────────────────────────┼──────────────────────────────┘  │
│                           │                                 │
│  ┌────────────────────────▼──────────────────────────────┐  │
│  │           LLM Service (Core Infrastructure)           │  │
│  │  ┌──────────────────────────────────────────────┐    │  │
│  │  │  AWS LLM Adapter (AWSLLMAdapter)             │    │  │
│  │  │  - Bedrock Integration                       │    │  │
│  │  │  - Circuit Breaker                           │    │  │
│  │  │  - OpenAI Fallback                           │    │  │
│  │  └──────────────────────────────────────────────┘    │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              AWS Infrastructure                       │  │
│  │                                                       │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │  │
│  │  │AWS Bedrock   │  │ElastiCache   │  │ DynamoDB  │ │  │
│  │  │(LLM Provider)│  │(Caching)     │  │(Usage Log)│ │  │
│  │  └──────────────┘  └──────────────┘  └───────────┘ │  │
│  │                                                       │  │
│  │  ┌──────────────┐  ┌──────────────┐                 │  │
│  │  │CloudWatch    │  │Secrets Mgr   │                 │  │
│  │  │(Monitoring)  │  │(API Keys)    │                 │  │
│  │  └──────────────┘  └──────────────┘                 │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Deployment Modes

| Mode | LLM Provider | Cache | Usage Tracking | Use Case |
|------|-------------|-------|----------------|----------|
| **Local Dev** | OpenAI | In-Memory | File | Development & Testing |
| **Staging** | Bedrock + OpenAI | ElastiCache | DynamoDB | Pre-production Testing |
| **Production** | Bedrock + OpenAI | ElastiCache | DynamoDB | Live System |

---

## Prerequisites

### Required Tools

```bash
# Python 3.10+
python --version  # Should be 3.10 or higher

# AWS CLI (for production deployment)
aws --version

# Docker & Docker Compose (optional, for containerized deployment)
docker --version
docker-compose --version

# Make (for convenience commands)
make --version
```

### Required Accounts & API Keys

1. **OpenAI Account** (Required)
   - Sign up at https://platform.openai.com
   - Create API key at https://platform.openai.com/api-keys
   - Add billing information

2. **Google Cloud Account** (Optional - for Banking Agent)
   - Sign up at https://cloud.google.com
   - Enable Generative AI API
   - Create API key at https://makersuite.google.com/app/apikey

3. **AWS Account** (Required for Production)
   - Sign up at https://aws.amazon.com
   - Configure IAM user with appropriate permissions
   - Enable AWS Bedrock in your region



---

## Local Development Setup

### Step 1: Clone and Setup Repository

```bash
# Clone the repository
git clone https://github.com/happyfuckingai/HappyOS-hackathon.git
cd HappyOS-hackathon

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
cd backend
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env file with your API keys
nano .env  # or use your preferred editor
```

**Minimum Required Configuration for Local Development:**

```bash
# .env file
OPENAI_API_KEY=sk-...                    # Required
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# Optional (for Banking Agent)
GOOGLE_API_KEY=...
```

### Step 3: Verify LLM Service Configuration

```bash
# Test OpenAI connection
python -c "
from openai import AsyncOpenAI
import asyncio
import os

async def test():
    client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = await client.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=[{'role': 'user', 'content': 'Hello'}],
        max_tokens=10
    )
    print('✅ OpenAI connection successful')
    print(f'Response: {response.choices[0].message.content}')

asyncio.run(test())
"
```

### Step 4: Start Backend Services

```bash
# Start the backend server
cd backend
python main.py

# Or use uvicorn directly with hot reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     LLM Service initialized (mode: local)
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 5: Verify LLM Service Health

```bash
# Check health endpoint
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "services": {
    "llm_service": "healthy",
    "cache": "in-memory",
    "provider": "openai"
  }
}

# Test LLM service directly
curl -X POST http://localhost:8000/api/llm/test \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Say hello",
    "agent_id": "test.agent",
    "tenant_id": "test_tenant"
  }'
```

### Step 6: Start Frontend (Optional)

```bash
# In a new terminal
cd frontend
npm install
npm start

# Frontend will be available at http://localhost:3000
```

### Local Development Checklist

- [ ] Python 3.10+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created with OPENAI_API_KEY
- [ ] Backend server starts without errors
- [ ] Health check returns "healthy"
- [ ] Test LLM call succeeds
- [ ] Frontend connects to backend (optional)

---

## AWS Infrastructure Setup

### Step 1: Configure AWS CLI

```bash
# Configure AWS credentials
aws configure

# Enter your credentials:
# AWS Access Key ID: ...
# AWS Secret Access Key: ...
# Default region name: us-east-1
# Default output format: json

# Verify configuration
aws sts get-caller-identity
```

### Step 2: Enable AWS Bedrock

```bash
# Check if Bedrock is available in your region
aws bedrock list-foundation-models --region us-east-1

# Request access to Claude models (if needed)
# Go to AWS Console > Bedrock > Model access
# Request access to:
# - Claude 3 Opus
# - Claude 3 Sonnet
# - Claude 3 Haiku
```

### Step 3: Create ElastiCache Cluster

```bash
# Create Redis cluster for LLM caching
aws elasticache create-cache-cluster \
  --cache-cluster-id happyos-llm-cache \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1 \
  --region us-east-1

# Wait for cluster to be available
aws elasticache describe-cache-clusters \
  --cache-cluster-id happyos-llm-cache \
  --show-cache-node-info

# Note the endpoint address (e.g., happyos-llm-cache.abc123.0001.use1.cache.amazonaws.com)
```

### Step 4: Create DynamoDB Table

```bash
# Create table for LLM usage tracking
aws dynamodb create-table \
  --table-name happyos-llm-usage \
  --attribute-definitions \
    AttributeName=request_id,AttributeType=S \
    AttributeName=timestamp,AttributeType=S \
    AttributeName=tenant_id,AttributeType=S \
    AttributeName=agent_id,AttributeType=S \
  --key-schema \
    AttributeName=request_id,KeyType=HASH \
    AttributeName=timestamp,KeyType=RANGE \
  --global-secondary-indexes \
    "[
      {
        \"IndexName\": \"tenant-timestamp-index\",
        \"KeySchema\": [
          {\"AttributeName\":\"tenant_id\",\"KeyType\":\"HASH\"},
          {\"AttributeName\":\"timestamp\",\"KeyType\":\"RANGE\"}
        ],
        \"Projection\": {\"ProjectionType\":\"ALL\"},
        \"ProvisionedThroughput\": {\"ReadCapacityUnits\":5,\"WriteCapacityUnits\":5}
      },
      {
        \"IndexName\": \"agent-timestamp-index\",
        \"KeySchema\": [
          {\"AttributeName\":\"agent_id\",\"KeyType\":\"HASH\"},
          {\"AttributeName\":\"timestamp\",\"KeyType\":\"RANGE\"}
        ],
        \"Projection\": {\"ProjectionType\":\"ALL\"},
        \"ProvisionedThroughput\": {\"ReadCapacityUnits\":5,\"WriteCapacityUnits\":5}
      }
    ]" \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
  --region us-east-1

# Wait for table to be active
aws dynamodb describe-table --table-name happyos-llm-usage
```

### Step 5: Store API Keys in Secrets Manager

```bash
# Store OpenAI API key
aws secretsmanager create-secret \
  --name happyos/openai-api-key \
  --secret-string  "REMOVED_SECRET"\
  --region us-east-1

# Store Google API key (optional)
aws secretsmanager create-secret \
  --name happyos/google-api-key \
  --secret-string "..." \
  --region us-east-1

# Verify secrets
aws secretsmanager list-secrets --region us-east-1
```

### Step 6: Create IAM Role for LLM Service

```bash
# Create IAM policy for LLM service
cat > llm-service-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*:*:foundation-model/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "elasticache:DescribeCacheClusters",
        "elasticache:DescribeCacheSubnetGroups"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/happyos-llm-usage",
        "arn:aws:dynamodb:*:*:table/happyos-llm-usage/index/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:*:secret:happyos/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/happyos/*"
    }
  ]
}
EOF

# Create the policy
aws iam create-policy \
  --policy-name HappyOSLLMServicePolicy \
  --policy-document file://llm-service-policy.json

# Create IAM role and attach policy
aws iam create-role \
  --role-name HappyOSLLMServiceRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach policy to role
aws iam attach-role-policy \
  --role-name HappyOSLLMServiceRole \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/HappyOSLLMServicePolicy
```

### AWS Infrastructure Checklist

- [ ] AWS CLI configured with credentials
- [ ] Bedrock access enabled for Claude models
- [ ] ElastiCache Redis cluster created
- [ ] DynamoDB table created with GSIs
- [ ] API keys stored in Secrets Manager
- [ ] IAM role and policy created
- [ ] Security groups configured (if using VPC)



---

## Production Deployment

### Step 1: Update Production Environment Variables

```bash
# Create production .env file
cat > .env.production <<EOF
# LLM Service Configuration
OPENAI_API_KEY=\${OPENAI_API_KEY_FROM_SECRETS_MANAGER}
GOOGLE_API_KEY=\${GOOGLE_API_KEY_FROM_SECRETS_MANAGER}

# AWS Configuration
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# ElastiCache
ELASTICACHE_CLUSTER=happyos-llm-cache.abc123.0001.use1.cache.amazonaws.com:6379
ELASTICACHE_TTL=3600

# DynamoDB
DYNAMODB_TABLE_PREFIX=happyos-
DYNAMODB_LLM_USAGE_TABLE=happyos-llm-usage

# Application
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Security
JWT_SECRET_KEY=\${SECURE_JWT_SECRET}
MCP_API_KEY=\${SECURE_MCP_KEY}
EOF
```

### Step 2: Build Docker Images

```bash
# Build backend image
docker build -t happyos-backend:latest -f backend/Dockerfile .

# Build agent images
docker build -t happyos-meetmind:latest -f backend/agents/meetmind/Dockerfile .
docker build -t happyos-agent-svea:latest -f backend/agents/agent_svea/Dockerfile .
docker build -t happyos-felicias-finance:latest -f backend/agents/felicias_finance/Dockerfile .

# Tag images for ECR (replace with your ECR repository)
docker tag happyos-backend:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/happyos-backend:latest
docker tag happyos-meetmind:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/happyos-meetmind:latest
docker tag happyos-agent-svea:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/happyos-agent-svea:latest
docker tag happyos-felicias-finance:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/happyos-felicias-finance:latest
```

### Step 3: Push Images to ECR

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Create ECR repositories (if not exists)
aws ecr create-repository --repository-name happyos-backend --region us-east-1
aws ecr create-repository --repository-name happyos-meetmind --region us-east-1
aws ecr create-repository --repository-name happyos-agent-svea --region us-east-1
aws ecr create-repository --repository-name happyos-felicias-finance --region us-east-1

# Push images
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/happyos-backend:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/happyos-meetmind:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/happyos-agent-svea:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/happyos-felicias-finance:latest
```

### Step 4: Deploy with AWS CDK (Recommended)

```bash
# Navigate to CDK directory
cd backend/infrastructure/aws/iac

# Install CDK dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-1

# Synthesize CloudFormation template
cdk synth

# Deploy infrastructure
cdk deploy --all --require-approval never

# Expected output:
# ✅ HappyOSLLMServiceStack
# ✅ HappyOSBackendStack
# ✅ HappyOSAgentsStack
```

### Step 5: Deploy with Docker Compose (Alternative)

```bash
# Use production docker-compose file
docker-compose -f docker-compose.prod.yml up -d

# Check service status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### Step 6: Verify Production Deployment

```bash
# Check health endpoint
curl https://api.happyos.ai/health

# Expected response:
{
  "status": "healthy",
  "services": {
    "llm_service": "healthy",
    "cache": "elasticache",
    "provider": "bedrock",
    "fallback": "openai"
  },
  "version": "1.0.0",
  "environment": "production"
}

# Test LLM service with authentication
curl -X POST https://api.happyos.ai/api/llm/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "prompt": "Test production LLM",
    "agent_id": "test.agent",
    "tenant_id": "production_tenant"
  }'

# Check usage stats
curl https://api.happyos.ai/api/llm/usage/stats \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Step 7: Configure Auto-Scaling (Optional)

```bash
# Create Auto Scaling group for backend
aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name happyos-backend-asg \
  --launch-template LaunchTemplateName=happyos-backend-lt \
  --min-size 2 \
  --max-size 10 \
  --desired-capacity 2 \
  --target-group-arns arn:aws:elasticloadbalancing:us-east-1:YOUR_ACCOUNT_ID:targetgroup/happyos-backend-tg/... \
  --health-check-type ELB \
  --health-check-grace-period 300

# Create scaling policies based on LLM request rate
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name happyos-backend-asg \
  --policy-name scale-on-llm-requests \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration '{
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ALBRequestCountPerTarget",
      "ResourceLabel": "app/happyos-alb/..."
    },
    "TargetValue": 1000.0
  }'
```

### Production Deployment Checklist

- [ ] Production environment variables configured
- [ ] Docker images built and tested
- [ ] Images pushed to ECR
- [ ] AWS infrastructure deployed (CDK or manual)
- [ ] Health checks passing
- [ ] LLM service responding correctly
- [ ] SSL/TLS certificates configured
- [ ] Auto-scaling configured (optional)
- [ ] Backup and disaster recovery plan in place

---

## Monitoring Setup

### Step 1: Configure CloudWatch Dashboards

```bash
# Create CloudWatch dashboard for LLM service
aws cloudwatch put-dashboard \
  --dashboard-name HappyOS-LLM-Service \
  --dashboard-body file://backend/modules/observability/dashboards/llm_usage_dashboard.json
```

### Step 2: Set Up CloudWatch Alarms

```bash
# Alarm for high error rate
aws cloudwatch put-metric-alarm \
  --alarm-name happyos-llm-high-error-rate \
  --alarm-description "Alert when LLM error rate exceeds 5%" \
  --metric-name llm_errors_total \
  --namespace HappyOS/LLM \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:happyos-alerts

# Alarm for high cost
aws cloudwatch put-metric-alarm \
  --alarm-name happyos-llm-high-cost \
  --alarm-description "Alert when daily LLM cost exceeds $100" \
  --metric-name llm_cost_total \
  --namespace HappyOS/LLM \
  --statistic Sum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:happyos-alerts

# Alarm for circuit breaker open
aws cloudwatch put-metric-alarm \
  --alarm-name happyos-llm-circuit-breaker-open \
  --alarm-description "Alert when LLM circuit breaker is open" \
  --metric-name circuit_breaker_state \
  --namespace HappyOS/LLM \
  --statistic Maximum \
  --period 60 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --alarm-actions arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:happyos-alerts
```

### Step 3: Configure Prometheus & Grafana (Optional)

```bash
# Start Prometheus
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

# Start Grafana
docker run -d \
  --name grafana \
  -p 3000:3000 \
  -e "GF_SECURITY_ADMIN_PASSWORD=admin" \
  grafana/grafana

# Import LLM dashboard
# Go to http://localhost:3000
# Login with admin/admin
# Import dashboard from backend/modules/observability/dashboards/llm_usage_dashboard.json
```

### Step 4: Configure Log Aggregation

```bash
# Create CloudWatch log group
aws logs create-log-group \
  --log-group-name /aws/happyos/llm-service \
  --region us-east-1

# Set retention policy
aws logs put-retention-policy \
  --log-group-name /aws/happyos/llm-service \
  --retention-in-days 30

# Create metric filters for key events
aws logs put-metric-filter \
  --log-group-name /aws/happyos/llm-service \
  --filter-name llm-errors \
  --filter-pattern "[timestamp, level=ERROR, ...]" \
  --metric-transformations \
    metricName=llm_errors,metricNamespace=HappyOS/LLM,metricValue=1
```

### Monitoring Checklist

- [ ] CloudWatch dashboard created
- [ ] CloudWatch alarms configured
- [ ] SNS topic for alerts created
- [ ] Prometheus metrics exposed (optional)
- [ ] Grafana dashboard imported (optional)
- [ ] Log aggregation configured
- [ ] Metric filters created

---

## Troubleshooting

### Issue 1: "API key not found" Error

**Symptoms:**
```
ERROR: LLM service initialization failed: API key not found
```

**Solutions:**

1. Check environment variable:
```bash
echo $OPENAI_API_KEY
```

2. Verify .env file:
```bash
cat .env | grep OPENAI_API_KEY
```

3. Check Secrets Manager (production):
```bash
aws secretsmanager get-secret-value \
  --secret-id happyos/openai-api-key \
  --query SecretString \
  --output text
```

4. Restart service after setting variable:
```bash
export OPENAI_API_KEY=sk-...
python main.py
```

### Issue 2: "Circuit breaker open" Error

**Symptoms:**
```
WARNING: Circuit breaker open for LLM service, using fallback
```

**Solutions:**

1. Check circuit breaker status:
```bash
curl http://localhost:8000/health/circuit-breaker
```

2. Check AWS Bedrock status:
```bash
aws bedrock list-foundation-models --region us-east-1
```

3. Manually reset circuit breaker:
```bash
curl -X POST http://localhost:8000/admin/circuit-breaker/reset
```

4. Check error logs:
```bash
tail -f backend/logs/llm_service.log | grep ERROR
```

### Issue 3: High Latency

**Symptoms:**
```
WARNING: LLM request took 15000ms (threshold: 5000ms)
```

**Solutions:**

1. Check cache hit rate:
```bash
curl http://localhost:8000/api/llm/usage/stats | jq '.cache_hit_rate'
```

2. Use faster model:
```python
# Change from gpt-4 to gpt-3.5-turbo
response = await llm_service.generate_completion(
    model="gpt-3.5-turbo",  # 10x faster
    ...
)
```

3. Reduce max_tokens:
```python
response = await llm_service.generate_completion(
    max_tokens=300,  # Instead of 1000
    ...
)
```

4. Check ElastiCache connectivity:
```bash
redis-cli -h happyos-llm-cache.abc123.0001.use1.cache.amazonaws.com ping
```

### Issue 4: High Costs

**Symptoms:**
```
ALERT: Daily LLM cost exceeded $100 threshold
```

**Solutions:**

1. Check cost breakdown:
```bash
curl http://localhost:8000/api/llm/usage/stats?time_range=24h | jq '.total_cost'
```

2. Identify expensive agents:
```bash
curl http://localhost:8000/api/llm/usage/stats | jq '.agent_breakdown'
```

3. Optimize model selection:
```python
# Use cheaper models for simple tasks
if task_complexity == "simple":
    model = "gpt-3.5-turbo"  # $0.0005/1K tokens
else:
    model = "gpt-4"  # $0.03/1K tokens
```

4. Increase cache TTL:
```bash
# In .env
ELASTICACHE_TTL=7200  # 2 hours instead of 1 hour
```

### Issue 5: ElastiCache Connection Failed

**Symptoms:**
```
ERROR: Failed to connect to ElastiCache: Connection timeout
```

**Solutions:**

1. Check security group rules:
```bash
aws ec2 describe-security-groups \
  --group-ids sg-... \
  --query 'SecurityGroups[0].IpPermissions'
```

2. Verify VPC configuration:
```bash
aws elasticache describe-cache-clusters \
  --cache-cluster-id happyos-llm-cache \
  --show-cache-node-info
```

3. Test connectivity from EC2 instance:
```bash
telnet happyos-llm-cache.abc123.0001.use1.cache.amazonaws.com 6379
```

4. Fallback to in-memory cache:
```python
# Service automatically falls back to in-memory cache
# Check logs for fallback message
```

### Issue 6: DynamoDB Throttling

**Symptoms:**
```
ERROR: DynamoDB ProvisionedThroughputExceededException
```

**Solutions:**

1. Check current capacity:
```bash
aws dynamodb describe-table \
  --table-name happyos-llm-usage \
  --query 'Table.ProvisionedThroughput'
```

2. Increase provisioned capacity:
```bash
aws dynamodb update-table \
  --table-name happyos-llm-usage \
  --provisioned-throughput ReadCapacityUnits=10,WriteCapacityUnits=10
```

3. Enable auto-scaling:
```bash
aws application-autoscaling register-scalable-target \
  --service-namespace dynamodb \
  --resource-id table/happyos-llm-usage \
  --scalable-dimension dynamodb:table:WriteCapacityUnits \
  --min-capacity 5 \
  --max-capacity 100
```

---

## Rollback Procedures

### Scenario 1: Rollback to Previous Version

```bash
# List previous deployments
aws cloudformation describe-stacks \
  --stack-name HappyOSLLMServiceStack \
  --query 'Stacks[0].Tags'

# Rollback using CDK
cd backend/infrastructure/aws/iac
cdk deploy --rollback

# Or rollback using CloudFormation
aws cloudformation cancel-update-stack \
  --stack-name HappyOSLLMServiceStack
```

### Scenario 2: Emergency Disable LLM Service

```bash
# Disable LLM service, use fallback only
curl -X POST http://localhost:8000/admin/llm/disable \
  -H "Authorization: Bearer ADMIN_TOKEN"

# All agents will use rule-based fallback logic
```

### Scenario 3: Switch to OpenAI Only

```bash
# Disable Bedrock, use OpenAI only
export BEDROCK_ENABLED=false
export OPENAI_ONLY=true

# Restart services
docker-compose restart backend
```

### Scenario 4: Restore from Backup

```bash
# Restore DynamoDB table from backup
aws dynamodb restore-table-from-backup \
  --target-table-name happyos-llm-usage \
  --backup-arn arn:aws:dynamodb:us-east-1:YOUR_ACCOUNT_ID:table/happyos-llm-usage/backup/...

# Restore ElastiCache from snapshot
aws elasticache create-cache-cluster \
  --cache-cluster-id happyos-llm-cache-restored \
  --snapshot-name happyos-llm-cache-snapshot-...
```

---

## Production Deployment Checklist

### Pre-Deployment

- [ ] All tests passing (unit, integration, load)
- [ ] Code reviewed and approved
- [ ] Environment variables configured
- [ ] AWS infrastructure provisioned
- [ ] API keys stored in Secrets Manager
- [ ] Backup and rollback plan documented
- [ ] Monitoring and alerts configured
- [ ] Load testing completed
- [ ] Security audit completed

### Deployment

- [ ] Docker images built and tagged
- [ ] Images pushed to ECR
- [ ] CDK deployment successful
- [ ] Health checks passing
- [ ] LLM service responding correctly
- [ ] All agents connected to LLM service
- [ ] Cache hit rate > 20%
- [ ] Error rate < 1%
- [ ] Latency < 2 seconds (p95)

### Post-Deployment

- [ ] Monitor for 1 hour after deployment
- [ ] Check CloudWatch metrics
- [ ] Verify cost tracking
- [ ] Test failover scenarios
- [ ] Update documentation
- [ ] Notify team of successful deployment
- [ ] Schedule post-deployment review

---

## Support and Resources

### Documentation

- **LLM Service API**: [backend/core/llm/README.md](../backend/core/llm/README.md)
- **Architecture Overview**: [README.md](../README.md)
- **AWS CDK Guide**: [backend/infrastructure/aws/iac/README.md](../backend/infrastructure/aws/iac/README.md)

### Monitoring Dashboards

- **CloudWatch**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=HappyOS-LLM-Service
- **Grafana**: http://localhost:3000/d/llm-usage (local)

### Contact

- **GitHub Issues**: https://github.com/happyfuckingai/HappyOS-hackathon/issues
- **Slack**: #llm-service channel
- **Email**: support@happyos.ai

---

**Last Updated**: 2024-01-15  
**Version**: 1.0.0  
**Maintained By**: HappyOS Team
