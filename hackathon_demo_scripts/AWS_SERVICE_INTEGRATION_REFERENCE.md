# AWS Service Integration Reference - Hackathon Demo Scripts

## Required Hackathon Services Integration

### AWS Bedrock - Primary LLM Hosting
**Requirement**: Large Language Model (LLM) hosted out of AWS Bedrock
**Models Used**: 
- **Amazon Nova Pro**: Primary reasoning LLM for autonomous decision-making
- **Amazon Nova Lite**: Cost-optimized processing for high-volume operations

**Integration Examples by Script**:

#### MeetMind Script
```python
# AWS Bedrock Nova for meeting intelligence reasoning
bedrock_client = boto3.client('bedrock-runtime')
response = bedrock_client.invoke_model(
    modelId='amazon.nova-pro-v1:0',
    body=json.dumps({
        'messages': [
            {"role": "system", "content": "You are an autonomous meeting intelligence agent..."},
            {"role": "user", "content": audio_transcript}
        ],
        'max_tokens': 2048,
        'temperature': 0.1
    })
)
```

#### Felicia's Finance Script
```python
# AWS Bedrock AgentCore for financial primitives
from aws_bedrock_agentcore import FinancialPrimitives, RiskAssessment
bedrock_agent = FinancialPrimitives(
    model_id='amazon.nova-pro-v1:0',
    agent_type='autonomous_trader'
)
```

#### Agent Svea Script
```python
# AWS Bedrock Nova for Swedish regulatory reasoning
response = bedrock_client.invoke_model(
    modelId='amazon.nova-pro-v1:0',
    body=json.dumps({
        'messages': [
            {"role": "system", "content": "You are Agent Svea, autonomous Swedish compliance expert..."},
            {"role": "user", "content": f"Transaction: {transaction_data}"}
        ]
    })
)
```

#### Happy OS Script
```python
# AWS Bedrock Nova across multiple isolated agents
class HappyOSMCPAgent:
    def __init__(self):
        self.bedrock_client = boto3.client('bedrock-runtime')
        # Each agent has independent Bedrock integration
```

### Amazon Bedrock AgentCore - Strongly Recommended
**Requirement**: At least 1 primitive (strongly recommended)
**Usage**: Specialized agent primitives for domain-specific reasoning

**AgentCore Primitives by Script**:

#### Felicia's Finance (Primary Usage)
- **FinancialPrimitives**: Market analysis and trading decisions
- **RiskAssessment**: Portfolio risk management
- **CompliancePrimitives**: Regulatory compliance automation
- **AutonomousDecisionMaker**: Trading execution decisions

#### Agent Svea (Compliance Focus)
- **CompliancePrimitives**: Swedish regulatory analysis
- **RegulatoryInterpreter**: BAS account classification
- **AutonomousDecisionMaker**: Compliance validation decisions

#### MeetMind (Meeting Intelligence)
- **MeetingPrimitives**: Audio processing and transcription
- **InsightExtractor**: Action item and decision identification
- **WorkflowOrchestrator**: Cross-agent coordination

### Amazon SageMaker AI - Alternative LLM Hosting
**Requirement**: Alternative to Bedrock for custom model deployment
**Usage**: Custom financial models, specialized compliance models

**SageMaker Integration Examples**:
```python
# Felicia's Finance custom trading models
sagemaker_client = boto3.client('sagemaker-runtime')
response = sagemaker_client.invoke_endpoint(
    EndpointName='finance-analysis-endpoint',
    ContentType='application/json',
    Body=json.dumps(market_data)
)
```

### Amazon Q - Intelligent Assistance
**Requirement**: Integration for business intelligence and assistance
**Usage**: Natural language queries, code assistance, documentation

**Amazon Q Integration Examples**:
```python
# MeetMind Amazon Q integration for business insights
q_client = boto3.client('q-business')
response = q_client.chat_sync(
    applicationId='meetmind-app',
    userMessage="Analyze meeting outcomes and suggest follow-up actions"
)
```

## Supporting AWS Services Architecture

### Core Infrastructure Services

#### AWS Lambda - Serverless Agent Execution
**Usage**: Event-driven agent processing, cost-effective scaling
```python
# Agent deployment as Lambda functions
def lambda_handler(event, context):
    agent = AgentSveaMCPServer()
    return agent.process_mcp_request(event)
```

#### Amazon DynamoDB - Agent State Management
**Usage**: High-performance NoSQL for agent data, automatic scaling
```python
# Agent state persistence
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('agent-state')
table.put_item(Item={
    'agent_id': 'agent_svea',
    'state': compliance_state,
    'timestamp': datetime.utcnow().isoformat()
})
```

#### Amazon API Gateway - MCP Protocol Endpoints
**Usage**: Secure, scalable API hosting for MCP communication
```yaml
# API Gateway configuration for MCP endpoints
Resources:
  MCPEndpoint:
    Type: AWS::ApiGateway::RestApi
    Properties:
      Name: HappyOS-MCP-Gateway
      EndpointConfiguration:
        Types: [REGIONAL]
```

### Monitoring and Observability

#### AWS CloudWatch - Comprehensive Monitoring
**Usage**: Real-time metrics, alerting, logging across all agents
```python
# CloudWatch metrics for agent performance
cloudwatch = boto3.client('cloudwatch')
cloudwatch.put_metric_data(
    Namespace='HappyOS/Agents',
    MetricData=[{
        'MetricName': 'ProcessingLatency',
        'Value': processing_time,
        'Unit': 'Milliseconds',
        'Dimensions': [{'Name': 'Agent', 'Value': 'agent_svea'}]
    }]
)
```

#### AWS X-Ray - Distributed Tracing
**Usage**: End-to-end workflow tracing across agents
```python
# X-Ray tracing for MCP workflows
from aws_xray_sdk.core import xray_recorder

@xray_recorder.capture('mcp_workflow')
async def process_cross_agent_workflow(workflow_data):
    # Trace complete workflow across agents
    pass
```

### Security and Networking

#### Amazon VPC - Secure Agent Communication
**Usage**: Network isolation, security controls for agent traffic
```yaml
# VPC configuration for agent isolation
VPC:
  Type: AWS::EC2::VPC
  Properties:
    CidrBlock: 10.0.0.0/16
    EnableDnsHostnames: true
    EnableDnsSupport: true
```

#### AWS IAM - Least Privilege Access
**Usage**: Fine-grained permissions for each agent
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "bedrock:InvokeModel",
      "dynamodb:GetItem",
      "dynamodb:PutItem"
    ],
    "Resource": "arn:aws:*:*:*:agent-svea-*"
  }]
}
```

## Circuit Breaker and Resilience Patterns

### AWS Service Failover Architecture
**Pattern**: Circuit breaker with local fallback for each AWS service
```python
class AWSCircuitBreaker:
    @circuit_breaker(failure_threshold=3, timeout=30)
    async def bedrock_with_fallback(self, data):
        try:
            return await self.bedrock_client.invoke_model(data)
        except (ClientError, TimeoutError):
            return await self.local_llm_fallback(data)
```

### Multi-Region Deployment
**Pattern**: Regional failover for critical services
```python
# Multi-region Bedrock deployment
regions = ['us-east-1', 'us-west-2', 'eu-west-1']
for region in regions:
    try:
        client = boto3.client('bedrock-runtime', region_name=region)
        return await client.invoke_model(model_data)
    except Exception:
        continue  # Try next region
```

## Performance Optimization Patterns

### Cost Optimization Strategies
1. **Reserved Capacity**: Bedrock Nova reserved instances for predictable workloads
2. **Spot Instances**: SageMaker spot instances for batch processing
3. **Auto Scaling**: DynamoDB on-demand scaling for variable loads
4. **Regional Optimization**: Deploy agents in optimal AWS regions

### Latency Optimization
1. **Edge Deployment**: CloudFront for global agent access
2. **Connection Pooling**: Reuse AWS service connections
3. **Async Processing**: Non-blocking MCP communication
4. **Caching**: ElastiCache for frequently accessed data

## Hackathon Compliance Verification

### Required Service Checklist
- [ ] **AWS Bedrock or SageMaker AI**: ✅ All scripts use Bedrock Nova
- [ ] **Autonomous Decision-Making**: ✅ All agents make independent decisions
- [ ] **API Integration**: ✅ MCP protocol, external APIs (Skatteverket, LiveKit)
- [ ] **Database Access**: ✅ DynamoDB, ERPNext integration
- [ ] **External Tools**: ✅ LiveKit, BAS validators, trading APIs

### Architecture Documentation Requirements
- [ ] **System Architecture Diagram**: ✅ Included in each script
- [ ] **AWS Service Integration**: ✅ Detailed in technical demonstrations
- [ ] **Agent Isolation**: ✅ Verified with zero backend.* imports
- [ ] **End-to-End Workflow**: ✅ Complete business process automation

### Deployment Requirements
- [ ] **Public Repository**: ✅ GitHub repositories for each script
- [ ] **Working Deployment**: ✅ Live demos available for evaluation
- [ ] **Installation Instructions**: ✅ One-click AWS CDK deployment
- [ ] **Architecture Diagram**: ✅ Visual representation of AWS integration

## Script-Specific AWS Integration Highlights

### MeetMind Script AWS Focus
- **Primary**: Bedrock Nova for meeting intelligence
- **Secondary**: Lambda for serverless processing, DynamoDB for meeting state
- **Unique**: Circuit breaker resilience with sub-5-second failover
- **Demo**: Live failover simulation showing AWS→Local→AWS recovery

### Felicia's Finance Script AWS Focus
- **Primary**: Bedrock AgentCore financial primitives
- **Secondary**: SageMaker for custom trading models, Timestream for market data
- **Unique**: Real-time financial compliance with AWS integration
- **Demo**: Live trading with integrated AWS compliance validation

### Agent Svea Script AWS Focus
- **Primary**: Bedrock AgentCore compliance primitives
- **Secondary**: API Gateway for Skatteverket integration, DynamoDB for BAS data
- **Unique**: Swedish regulatory automation with AWS infrastructure
- **Demo**: Real-time BAS validation with AWS-powered compliance engine

### Happy OS Script AWS Focus
- **Primary**: Bedrock Nova across multiple isolated agents
- **Secondary**: Complete AWS stack (Lambda, DynamoDB, API Gateway, CloudWatch)
- **Unique**: Multi-agent AWS optimization with independent scaling
- **Demo**: End-to-end AWS elasticity across isolated agent ecosystem

## Deployment Architecture Examples

### Single-Agent AWS Deployment
```yaml
# Agent Svea AWS CDK Stack
Resources:
  AgentSveaFunction:
    Type: AWS::Lambda::Function
    Properties:
      Runtime: python3.10
      Handler: svea_mcp_server.handler
      Environment:
        Variables:
          BEDROCK_REGION: us-east-1
          DYNAMODB_TABLE: !Ref AgentSveaTable
  
  AgentSveaTable:
    Type: AWS::DynamoDB::Table
    Properties:
      BillingMode: ON_DEMAND
      AttributeDefinitions:
        - AttributeName: agent_id
          AttributeType: S
```

### Multi-Agent AWS Architecture
```yaml
# Happy OS Complete AWS Stack
Resources:
  # Individual agent Lambda functions
  MeetMindFunction: !Ref MeetMindLambda
  AgentSveaFunction: !Ref AgentSveaLambda
  FeliciasFinanceFunction: !Ref FeliciasFinanceLambda
  
  # Shared infrastructure
  MCPGateway: !Ref APIGateway
  SharedMonitoring: !Ref CloudWatchDashboard
  CrossAgentVPC: !Ref AgentVPC
```

This comprehensive AWS integration ensures all hackathon requirements are met while showcasing the full power of AWS services in autonomous agent architectures.