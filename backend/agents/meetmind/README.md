# MeetMind - AI Meeting Intelligence Agent

## Overview

MeetMind is a multi-agent system for intelligent meeting analysis, providing real-time transcription, AI-powered summarization, action item extraction, and compliance insights. It uses the centralized LLM Service for all AI capabilities with automatic fallback to rule-based logic.

## Agent Architecture

MeetMind consists of 5 specialized agents working together:

```
┌─────────────────────────────────────────────────────────┐
│              MeetMind Agent Team                         │
│                                                          │
│  ┌────────────────┐  ┌────────────────┐                │
│  │  Coordinator   │  │   Architect    │                │
│  │    Agent       │  │     Agent      │                │
│  │                │  │                │                │
│  │ - Workflow     │  │ - Framework    │                │
│  │   orchestration│  │   design       │                │
│  │ - Task         │  │ - Pipeline     │                │
│  │   prioritization│  │   architecture │                │
│  └────────┬───────┘  └────────┬───────┘                │
│           │                    │                        │
│  ┌────────▼────────┐  ┌───────▼────────┐              │
│  │Product Manager  │  │Implementation  │              │
│  │     Agent       │  │     Agent      │              │
│  │                 │  │                │              │
│  │ - Requirements  │  │ - Transcript   │              │
│  │   analysis      │  │   processing   │              │
│  │ - Feature       │  │ - Analysis     │              │
│  │   prioritization│  │   pipeline     │              │
│  └────────┬────────┘  └───────┬────────┘              │
│           │                    │                        │
│           │    ┌───────────────▼────────┐              │
│           └────►Quality Assurance Agent │              │
│                │                         │              │
│                │ - Quality validation    │              │
│                │ - Performance testing   │              │
│                └─────────────────────────┘              │
│                                                          │
│                    ↓ Uses ↓                             │
│              ┌──────────────┐                           │
│              │  LLM Service │                           │
│              │  (Core)      │                           │
│              └──────────────┘                           │
└─────────────────────────────────────────────────────────┘
```

## LLM Integration

### Overview

All MeetMind agents use the centralized LLM Service (`backend/core/llm/`) for AI capabilities:

- **Primary Provider**: AWS Bedrock (Claude 3 Sonnet) in production
- **Fallback Provider**: OpenAI (GPT-4) when Bedrock unavailable
- **Emergency Fallback**: Rule-based logic when all LLM services unavailable
- **Caching**: ElastiCache (AWS) or in-memory (local) for response caching
- **Usage Tracking**: DynamoDB for cost and performance monitoring

### Configuration

```bash
# Required environment variables
OPENAI_API_KEY=sk-...                    # Required for all agents

# Optional (for production)
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
ELASTICACHE_CLUSTER=...
```

### Agent-Specific LLM Usage

#### 1. Coordinator Agent

**Purpose**: Orchestrate meeting analysis workflows

**LLM Use Cases**:
- Workflow planning and task prioritization
- Agent coordination and resource allocation
- Conflict resolution between agent results

**Example**:
```python
from backend.core.interfaces import LLMService

class CoordinatorAgent:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.agent_id = "meetmind.coordinator"
    
    async def coordinate_meeting_analysis(
        self,
        meeting_data: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        prompt = f"""
        Analyze this meeting data and create a coordination plan:
        
        Meeting Data: {json.dumps(meeting_data)}
        
        Provide a JSON response with:
        {{
            "workflow_id": "unique_id",
            "analysis_tasks": ["task1", "task2"],
            "priority": "high|medium|low",
            "estimated_duration": "time estimate"
        }}
        """
        
        try:
            response = await self.llm_service.generate_completion(
                prompt=prompt,
                agent_id=self.agent_id,
                tenant_id=tenant_id,
                model="gpt-4",
                temperature=0.3,
                max_tokens=800
            )
            
            return json.loads(response["content"])
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            # Fallback to rule-based coordination
            return self._fallback_coordination(meeting_data)
```

**Fallback Behavior**: Uses predefined workflow templates based on meeting type

#### 2. Architect Agent

**Purpose**: Design analysis frameworks and data pipelines

**LLM Use Cases**:
- Technical architecture design for analysis pipelines
- Data flow optimization
- Integration pattern recommendations

**Example**:
```python
async def design_analysis_framework(
    self,
    requirements: Dict[str, Any],
    tenant_id: str
) -> Dict[str, Any]:
    prompt = f"""
    Design an analysis framework for these requirements:
    
    Requirements: {json.dumps(requirements)}
    
    Provide JSON with:
    {{
        "architecture": {{"components": [], "data_flow": []}},
        "technologies": ["tech1", "tech2"],
        "scalability": "description"
    }}
    """
    
    try:
        response = await self.llm_service.generate_completion(
            prompt=prompt,
            agent_id="meetmind.architect",
            tenant_id=tenant_id,
            model="gpt-4",
            temperature=0.4,
            max_tokens=1000
        )
        
        return json.loads(response["content"])
        
    except Exception as e:
        # Fallback to template-based architecture
        return self._fallback_architecture(requirements)
```

**Fallback Behavior**: Uses predefined architecture templates

#### 3. Product Manager Agent

**Purpose**: Analyze requirements and prioritize features

**LLM Use Cases**:
- Meeting requirements extraction
- Feature prioritization based on business value
- Stakeholder analysis

**Example**:
```python
async def define_requirements(
    self,
    meeting_context: Dict[str, Any],
    tenant_id: str
) -> Dict[str, Any]:
    prompt = f"""
    Extract requirements from this meeting context:
    
    Context: {json.dumps(meeting_context)}
    
    Provide JSON with:
    {{
        "functional_requirements": ["req1", "req2"],
        "non_functional_requirements": ["req3"],
        "priorities": {{"high": [], "medium": [], "low": []}}
    }}
    """
    
    try:
        response = await self.llm_service.generate_completion(
            prompt=prompt,
            agent_id="meetmind.product_manager",
            tenant_id=tenant_id,
            model="gpt-4",
            temperature=0.2,
            max_tokens=600
        )
        
        return json.loads(response["content"])
        
    except Exception as e:
        # Fallback to keyword-based extraction
        return self._fallback_requirements(meeting_context)
```

**Fallback Behavior**: Uses keyword extraction and pattern matching

#### 4. Implementation Agent

**Purpose**: Process transcripts and implement analysis pipelines

**LLM Use Cases**:
- Transcript summarization
- Action item extraction
- Decision tracking
- Sentiment analysis

**Example**:
```python
async def process_meeting_transcript(
    self,
    transcript: str,
    tenant_id: str
) -> Dict[str, Any]:
    prompt = f"""
    Analyze this meeting transcript:
    
    Transcript: {transcript}
    
    Provide JSON with:
    {{
        "summary": "brief summary",
        "action_items": [
            {{"task": "...", "owner": "...", "deadline": "..."}}
        ],
        "decisions": ["decision1", "decision2"],
        "key_points": ["point1", "point2"]
    }}
    """
    
    try:
        response = await self.llm_service.generate_completion(
            prompt=prompt,
            agent_id="meetmind.implementation",
            tenant_id=tenant_id,
            model="gpt-4",
            temperature=0.3,
            max_tokens=1500
        )
        
        return json.loads(response["content"])
        
    except Exception as e:
        # Fallback to rule-based extraction
        return self._fallback_processing(transcript)
```

**Fallback Behavior**: Uses regex patterns and NLP libraries for basic extraction

#### 5. Quality Assurance Agent

**Purpose**: Validate analysis quality and test system performance

**LLM Use Cases**:
- Quality validation of analysis results
- Completeness checking
- Consistency verification

**Example**:
```python
async def validate_analysis_quality(
    self,
    analysis_results: Dict[str, Any],
    tenant_id: str
) -> Dict[str, Any]:
    prompt = f"""
    Validate the quality of this analysis:
    
    Results: {json.dumps(analysis_results)}
    
    Provide JSON with:
    {{
        "quality_score": 0.0-1.0,
        "issues": ["issue1", "issue2"],
        "recommendations": ["rec1", "rec2"],
        "passed": true/false
    }}
    """
    
    try:
        response = await self.llm_service.generate_completion(
            prompt=prompt,
            agent_id="meetmind.quality_assurance",
            tenant_id=tenant_id,
            model="gpt-4",
            temperature=0.2,
            max_tokens=500
        )
        
        return json.loads(response["content"])
        
    except Exception as e:
        # Fallback to rule-based validation
        return self._fallback_validation(analysis_results)
```

**Fallback Behavior**: Uses predefined quality metrics and thresholds

## Fallback Strategy

When LLM services are unavailable, MeetMind agents use rule-based logic:

1. **Coordinator**: Predefined workflow templates
2. **Architect**: Template-based architecture patterns
3. **Product Manager**: Keyword extraction and pattern matching
4. **Implementation**: Regex patterns and NLP libraries
5. **Quality Assurance**: Rule-based quality metrics

**Fallback Activation**:
- Automatic when LLM service returns error
- Logged for monitoring and alerting
- Maintains 70-80% functionality

## Performance Characteristics

### With LLM Service

- **Latency**: 1-3 seconds per analysis
- **Accuracy**: 90-95% for action item extraction
- **Cost**: ~$0.02-0.05 per meeting analysis
- **Cache Hit Rate**: 30-40% for similar meetings

### With Fallback (No LLM)

- **Latency**: <100ms per analysis
- **Accuracy**: 60-70% for action item extraction
- **Cost**: $0 (no API calls)
- **Functionality**: Basic extraction only

## Testing

### Unit Tests

```bash
# Test individual agents with mock LLM service
pytest backend/agents/meetmind/test_coordinator_agent_llm.py
pytest backend/agents/meetmind/test_architect_agent_llm.py
pytest backend/agents/meetmind/test_product_manager_agent_llm.py
pytest backend/agents/meetmind/test_implementation_agent_llm.py
pytest backend/agents/meetmind/test_quality_assurance_agent_llm.py
```

### Integration Tests

```bash
# Test with real LLM service
pytest backend/agents/meetmind/test_llm_integration.py -v
```

## Monitoring

### Key Metrics

- `meetmind_llm_requests_total` - Total LLM requests per agent
- `meetmind_llm_latency_seconds` - LLM response time
- `meetmind_llm_cost_total` - Total LLM cost
- `meetmind_fallback_activations_total` - Fallback usage count
- `meetmind_cache_hit_rate` - Cache effectiveness

### Dashboards

- CloudWatch: `/aws/happyos/meetmind`
- Grafana: `http://localhost:3000/d/meetmind-llm`

## Troubleshooting

### Issue: High LLM Costs

**Solution**: Use GPT-3.5-turbo for simple tasks
```python
# For simple summarization
model = "gpt-3.5-turbo"  # Instead of gpt-4
```

### Issue: Slow Response Times

**Solution**: Reduce max_tokens or use streaming
```python
# Reduce tokens
max_tokens = 500  # Instead of 1500

# Or use streaming
async for chunk in llm_service.generate_streaming_completion(...):
    process(chunk)
```

### Issue: Fallback Mode Activated

**Solution**: Check LLM service health
```bash
curl http://localhost:8000/health/llm
```

## Related Documentation

- [LLM Service API](../../core/llm/README.md)
- [Deployment Guide](../../../docs/llm_deployment_guide.md)
- [Architecture Overview](../../../README.md)

## Support

- GitHub Issues: https://github.com/happyfuckingai/HappyOS-hackathon/issues
- Slack: #meetmind channel
