# MeetMind AI Agent Operating System - Design Document

## Overview

The MeetMind AI Agent Operating System is a revolutionary multi-layered AI platform that demonstrates the next evolution of intelligent systems. It combines self-managing infrastructure agents, specialized business domain agents, and intelligent communication orchestration into a unified, autonomous platform that runs on AWS while showcasing deep technical understanding through custom infrastructure implementations.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AWS Native Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │ Kommunikations- │    │   Summarizer    │                    │
│  │     Agent       │◄──►│     Agent       │                    │
│  │  (Lambda)       │    │   (Lambda)      │                    │
│  └─────────────────┘    └─────────────────┘                    │
│           │                       │                             │
│           ▼                       ▼                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              AWS Agent Core                                 │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │ │
│  │  │   Memory    │ │   Gateway   │ │ Observability│          │ │
│  │  │ (Personal)  │ │   (MCP)     │ │  (Metrics)   │          │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                AWS OpenSearch                               │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │ │
│  │  │ Transcripts │ │   Chunks    │ │  Summaries  │          │ │
│  │  │   Index     │ │    Index    │ │    Index    │          │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              Preserved Components                           │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │ │
│  │  │ A2A Protocol│ │ ADK Agents  │ │ MCP UI Hub  │          │ │
│  │  │ (Unchanged) │ │(Unchanged)  │ │ (Enhanced)  │          │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘          │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Custom Infrastructure Reference                    │
├─────────────────────────────────────────────────────────────────┤
│  backend/services/infrastructure/ (Preserved as Reference)     │
│  ├── rate_limiter.py      → API Gateway Throttling             │
│  ├── load_balancer.py     → Application Load Balancer          │
│  ├── cache_manager.py     → ElastiCache + DynamoDB DAX         │
│  ├── performance_monitor.py → CloudWatch                       │
│  └── ...                  → Other AWS Services                 │
└─────────────────────────────────────────────────────────────────┘
```

### Migration Strategy

The migration follows a **gradual replacement** approach:

1. **Phase 1**: Memory Migration (mem0 → AWS Agent Core)
2. **Phase 2**: Vector Storage Migration (Custom → OpenSearch)  
3. **Phase 3**: Runtime Migration (Docker → Lambda)
4. **Phase 4**: Infrastructure Documentation and Reference Setup

## Components and Interfaces

### 1. AWS Agent Core Integration

#### Memory Management
```python
# Before (mem0)
from mem0 import AsyncMemoryClient
memory = AsyncMemoryClient()
await memory.add("Marcus är programmerare", user_id="marcus")

# After (AWS Agent Core)
import boto3
agent_core = boto3.client('bedrock-agent-runtime')
response = agent_core.invoke_agent(
    agentId='kommunikation-agent',
    sessionId='marcus',
    inputText="Kom ihåg: Marcus är programmerare"
)
```

#### Agent Runtime
```python
# AWS Agent Core Runtime Configuration
class AgentCoreConfig:
    agent_id: str = "meetmind-kommunikation"
    agent_alias: str = "DRAFT"
    session_timeout: int = 3600
    memory_type: str = "SESSION_SUMMARY"
    
    # Integration with existing A2A protocol
    a2a_enabled: bool = True
    adk_integration: bool = True
```

### 2. OpenSearch Storage Service Integration

#### Replaces Custom Vector Storage
```python
# Before: backend/services/storage/vector_service.py
class VectorService:
    def __init__(self, cache_manager):
        self.cache_manager = cache_manager
    
    async def store_document(self, content, embedding, metadata):
        # Custom cache-based storage
        pass

# After: backend/services/storage/opensearch_service.py
class OpenSearchStorageService:
    def __init__(self, config: OpenSearchConfig):
        self.client = OpenSearch(...)
        self.cache_manager = cache_manager  # Fallback
    
    async def store_document(self, doc_type, content, embedding, tenant_id, metadata):
        # AWS OpenSearch with cache fallback
        if self._should_use_opensearch():
            return await self._store_opensearch_document(...)
        else:
            return await self._store_cache_document(...)
```

#### Index Design for Historical Memory
```python
# OpenSearch Index Mappings for Document Storage
OPENSEARCH_MAPPINGS = {
    "meetmind_transcript_{tenant_id}": {
        "mappings": {
            "properties": {
                "tenant_id": {"type": "keyword"},
                "content": {"type": "text", "analyzer": "standard"},
                "doc_type": {"type": "keyword"},
                "timestamp": {"type": "date"},
                "metadata": {"type": "object"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1536,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib"
                    }
                }
            }
        }
    }
}
```

#### Storage Service with Fallback
```python
# backend/services/storage/opensearch_service.py
class OpenSearchStorageService:
    def __init__(self, config: OpenSearchConfig):
        self.client = OpenSearch(...)
        self.cache_manager = None  # Fallback to existing cache
        self.fallback_enabled = True
    
    async def search_documents(self, query_text: str, 
                             query_embedding: Optional[List[float]] = None,
                             doc_types: Optional[List[DocumentType]] = None,
                             tenant_id: str = "",
                             filters: Optional[Dict[str, Any]] = None,
                             limit: int = 10) -> List[Dict[str, Any]]:
        """Search with hybrid BM25 + kNN, fallback to cache"""
        try:
            if self._should_use_opensearch():
                return await self._search_opensearch(...)
            else:
                return await self._search_cache(...)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            if self.fallback_enabled:
                return await self._search_cache(...)
            return []
    
    def _should_use_opensearch(self) -> bool:
        """Circuit breaker logic for AWS service availability"""
        return (self.client is not None and 
                not self.circuit_open and 
                self.failure_count < 3)
```

### 3. Lambda Runtime Integration

#### Kommunikationsagent Lambda
```python
# lambda_kommunikationsagent.py
import json
import asyncio
from typing import Dict, Any

# Preserve existing imports
from backend.kommunikationsagent.agent import KommunikationsAgent
from backend.services.aws.agent_core import AgentCoreMemory
from backend.services.aws.opensearch import OpenSearchManager

async def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Lambda handler for Kommunikationsagent"""
    try:
        # Initialize AWS services
        agent_memory = AgentCoreMemory(
            agent_id="kommunikation-agent",
            session_id=event.get("session_id")
        )
        
        opensearch = OpenSearchManager(
            endpoint=os.environ["OPENSEARCH_ENDPOINT"],
            region=os.environ["AWS_REGION"]
        )
        
        # Create agent with AWS integrations
        agent = KommunikationsAgent(
            memory_client=agent_memory,
            vector_search=opensearch,
            # Preserve existing A2A and ADK integrations
            a2a_enabled=True,
            adk_integration=True
        )
        
        # Process request
        response = await agent.process_request(event)
        
        return {
            "statusCode": 200,
            "body": json.dumps(response),
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
```

#### Serverless Configuration
```yaml
# serverless.yml
service: meetmind-agents

provider:
  name: aws
  runtime: python3.11
  region: ${env:AWS_REGION, 'us-east-1'}
  
  environment:
    OPENSEARCH_ENDPOINT: ${env:OPENSEARCH_ENDPOINT}
    AGENT_CORE_AGENT_ID: ${env:AGENT_CORE_AGENT_ID}
    
  iamRoleStatements:
    - Effect: Allow
      Action:
        - bedrock:InvokeAgent
        - bedrock:RetrieveAndGenerate
        - es:ESHttpGet
        - es:ESHttpPost
      Resource: "*"

functions:
  kommunikationsagent:
    handler: lambda_kommunikationsagent.lambda_handler
    timeout: 30
    memorySize: 1024
    events:
      - http:
          path: /chat
          method: post
          cors: true
    
  summarizer:
    handler: lambda_summarizer.lambda_handler
    timeout: 60
    memorySize: 2048
    events:
      - http:
          path: /summarize
          method: post
          cors: true

plugins:
  - serverless-python-requirements
  - serverless-offline

custom:
  pythonRequirements:
    dockerizePip: true
    layer: true
```

### 4. Custom Infrastructure Preservation

#### Reference Directory Structure
```
backend/services/
├── aws/                          # AWS Agent Core integrations only
│   ├── __init__.py
│   ├── agent_core.py            # AWS Agent Core wrapper
│   ├── agent_runtime.py         # Agent runtime management
│   ├── agent_gateway.py         # MCP gateway integration
│   └── README.md                # AWS Agent Core documentation
│
├── storage/                     # Storage services
│   ├── __init__.py
│   ├── vector_service.py        # Original custom vector storage (preserved)
│   ├── opensearch_service.py    # NEW: AWS OpenSearch replacement
│   ├── realtime_store.py        # Existing realtime storage
│   └── README.md                # Storage services documentation
│
├── infrastructure/               # Preserved custom infrastructure
│   ├── README.md                # "Custom Infrastructure Reference"
│   ├── rate_limiter.py          # → API Gateway throttling
│   ├── load_balancer.py         # → Application Load Balancer
│   ├── cache_manager.py         # → ElastiCache + DynamoDB DAX
│   ├── performance_monitor.py   # → CloudWatch
│   ├── horizontal_scaler.py     # → Lambda auto-scaling
│   ├── audit_logger.py          # → CloudTrail
│   └── ...                      # Other custom components
│
└── migration/                   # Migration utilities
    ├── __init__.py
    ├── opensearch_migration.py  # Migrate vector storage to OpenSearch
    ├── config_converter.py      # Convert configs for AWS
    └── rollback_manager.py      # Rollback to custom infrastructure
```

#### Custom Infrastructure README
```markdown
# Custom Infrastructure Reference

This directory contains production-ready infrastructure components built from scratch to demonstrate comprehensive system architecture knowledge.

## Components Overview

### Rate Limiting (`rate_limiter.py`)
- **Custom Implementation**: Redis-based sliding window rate limiting
- **AWS Equivalent**: API Gateway throttling
- **Features**: Multi-level limits, circuit breaker, monitoring
- **Lines of Code**: 500+

### Load Balancing (`load_balancer.py`)
- **Custom Implementation**: Advanced load balancing with health checks
- **AWS Equivalent**: Application Load Balancer
- **Features**: Multiple algorithms, session affinity, auto-scaling integration
- **Lines of Code**: 800+

### Caching (`cache_manager.py`)
- **Custom Implementation**: Multi-level caching with intelligent invalidation
- **AWS Equivalent**: ElastiCache + DynamoDB DAX
- **Features**: Compression, distributed coordination, performance monitoring
- **Lines of Code**: 600+

## Why We Migrated to AWS

1. **Operational Efficiency**: Reduce maintenance overhead
2. **Scalability**: Auto-scaling and managed capacity
3. **Reliability**: AWS SLA and built-in redundancy
4. **Cost Optimization**: Pay-per-use pricing model
5. **Focus on Business Logic**: More time for feature development

## Technical Demonstration Value

This custom infrastructure demonstrates:
- Deep understanding of distributed systems
- Production-ready code with monitoring and error handling
- Scalability patterns and performance optimization
- System architecture and design patterns
- Ability to build what cloud providers offer

## Usage in Presentations

"We chose AWS managed services for production deployment, but we've also built equivalent infrastructure from scratch to demonstrate our deep technical understanding of these systems."
```

## Data Models

### AWS Agent Core Memory Model
```python
@dataclass
class AgentMemoryEntry:
    agent_id: str
    session_id: str
    memory_type: str  # "SESSION_SUMMARY", "USER_CONTEXT", "CONVERSATION_HISTORY"
    content: str
    metadata: Dict[str, Any]
    timestamp: datetime
    ttl: Optional[int] = None
```

### OpenSearch Document Model
```python
@dataclass
class OpenSearchDocument:
    tenant_id: str
    meeting_id: str
    document_id: str
    document_type: str  # "transcript", "chunk", "summary"
    text: str
    embedding: List[float]
    metadata: Dict[str, Any]
    timestamp: datetime
    
    def to_opensearch_doc(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "meeting_id": self.meeting_id,
            "document_id": self.document_id,
            "document_type": self.document_type,
            "text": self.text,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "@timestamp": self.timestamp.isoformat()
        }
```

### Migration State Model
```python
@dataclass
class MigrationState:
    component: str
    status: str  # "not_started", "in_progress", "completed", "rolled_back"
    aws_resource_arn: Optional[str] = None
    custom_resource_active: bool = True
    migration_timestamp: Optional[datetime] = None
    rollback_data: Optional[Dict[str, Any]] = None
```

## Error Handling

### AWS Service Error Handling
```python
class AWSServiceError(Exception):
    """Base exception for AWS service errors"""
    pass

class AgentCoreError(AWSServiceError):
    """AWS Agent Core specific errors"""
    pass

class OpenSearchError(AWSServiceError):
    """OpenSearch specific errors"""
    pass

class MigrationError(Exception):
    """Migration process errors"""
    pass

# Error handling with fallback to custom infrastructure
async def with_fallback(aws_operation: Callable, custom_operation: Callable):
    """Execute AWS operation with fallback to custom infrastructure"""
    try:
        return await aws_operation()
    except AWSServiceError as e:
        logger.warning(f"AWS operation failed, falling back to custom: {e}")
        return await custom_operation()
```

### Circuit Breaker for AWS Services
```python
class AWSCircuitBreaker:
    """Circuit breaker for AWS service calls with custom fallback"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, aws_func: Callable, fallback_func: Callable):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                logger.info("Circuit breaker OPEN, using custom fallback")
                return await fallback_func()
        
        try:
            result = await aws_func()
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")
            
            logger.warning(f"AWS service failed, using custom fallback: {e}")
            return await fallback_func()
```

## Testing Strategy

### Parallel Testing Approach
```python
class ParallelTester:
    """Test both AWS and custom implementations in parallel"""
    
    def __init__(self, aws_service, custom_service):
        self.aws_service = aws_service
        self.custom_service = custom_service
    
    async def compare_implementations(self, test_data: List[Dict]):
        """Compare AWS and custom implementations"""
        results = {
            "aws_results": [],
            "custom_results": [],
            "discrepancies": [],
            "performance_comparison": {}
        }
        
        for data in test_data:
            # Test AWS implementation
            aws_start = time.time()
            try:
                aws_result = await self.aws_service.process(data)
                aws_duration = time.time() - aws_start
                results["aws_results"].append({
                    "input": data,
                    "output": aws_result,
                    "duration": aws_duration,
                    "success": True
                })
            except Exception as e:
                results["aws_results"].append({
                    "input": data,
                    "error": str(e),
                    "success": False
                })
            
            # Test custom implementation
            custom_start = time.time()
            try:
                custom_result = await self.custom_service.process(data)
                custom_duration = time.time() - custom_start
                results["custom_results"].append({
                    "input": data,
                    "output": custom_result,
                    "duration": custom_duration,
                    "success": True
                })
            except Exception as e:
                results["custom_results"].append({
                    "input": data,
                    "error": str(e),
                    "success": False
                })
        
        return results
```

### Migration Testing
```python
class MigrationTester:
    """Test migration process and rollback capabilities"""
    
    async def test_migration_phase(self, phase: str) -> Dict[str, Any]:
        """Test specific migration phase"""
        test_results = {
            "phase": phase,
            "pre_migration_state": None,
            "post_migration_state": None,
            "rollback_successful": False,
            "data_integrity": True,
            "performance_impact": {}
        }
        
        # Capture pre-migration state
        test_results["pre_migration_state"] = await self._capture_system_state()
        
        # Execute migration
        migration_success = await self._execute_migration_phase(phase)
        
        # Capture post-migration state
        test_results["post_migration_state"] = await self._capture_system_state()
        
        # Test rollback
        if migration_success:
            rollback_success = await self._test_rollback(phase)
            test_results["rollback_successful"] = rollback_success
        
        return test_results
```

## Deployment Strategy

### Infrastructure as Code
```yaml
# cloudformation/opensearch.yml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'OpenSearch cluster for MeetMind semantic search'

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]

Resources:
  OpenSearchDomain:
    Type: AWS::OpenSearch::Domain
    Properties:
      DomainName: !Sub 'meetmind-search-${Environment}'
      EngineVersion: 'OpenSearch_2.3'
      ClusterConfig:
        InstanceType: t3.small.search
        InstanceCount: 3
        DedicatedMasterEnabled: true
        MasterInstanceType: t3.small.search
        MasterInstanceCount: 3
      
      EBSOptions:
        EBSEnabled: true
        VolumeType: gp3
        VolumeSize: 20
      
      VPCOptions:
        SecurityGroupIds:
          - !Ref OpenSearchSecurityGroup
        SubnetIds:
          - !Ref PrivateSubnet1
          - !Ref PrivateSubnet2
      
      AccessPolicies:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              AWS: !Sub 'arn:aws:iam::${AWS::AccountId}:role/MeetMindLambdaRole'
            Action: 'es:*'
            Resource: !Sub 'arn:aws:es:${AWS::Region}:${AWS::AccountId}:domain/meetmind-search-${Environment}/*'

Outputs:
  OpenSearchEndpoint:
    Description: 'OpenSearch domain endpoint'
    Value: !GetAtt OpenSearchDomain.DomainEndpoint
    Export:
      Name: !Sub '${AWS::StackName}-OpenSearchEndpoint'
```

### Deployment Pipeline
```yaml
# .github/workflows/aws-migration.yml
name: AWS Migration Deployment

on:
  push:
    branches: [aws-migration]
  pull_request:
    branches: [main]

jobs:
  test-parallel:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      
      - name: Run parallel tests
        run: |
          python -m pytest tests/migration/test_parallel_implementations.py
          python -m pytest tests/migration/test_migration_phases.py
      
      - name: Generate comparison report
        run: |
          python scripts/generate_migration_report.py

  deploy-aws:
    needs: test-parallel
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/aws-migration'
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Deploy OpenSearch
        run: |
          aws cloudformation deploy \
            --template-file cloudformation/opensearch.yml \
            --stack-name meetmind-opensearch-dev \
            --parameter-overrides Environment=dev \
            --capabilities CAPABILITY_IAM
      
      - name: Deploy Lambda functions
        run: |
          npm install -g serverless
          serverless deploy --stage dev
      
      - name: Run migration
        run: |
          python scripts/migrate_to_aws.py --phase memory
          python scripts/migrate_to_aws.py --phase vector-storage
          python scripts/migrate_to_aws.py --phase runtime
```

This design provides a comprehensive migration strategy that preserves your impressive custom infrastructure while leveraging AWS managed services for production deployment. The gradual migration approach minimizes risk while the preserved custom code serves as a powerful technical demonstration for the hackathon.