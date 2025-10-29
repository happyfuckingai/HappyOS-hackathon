graph TB
    subgraph "AWS Infrastructure"
        subgraph "Core AWS Services"
            Bedrock[Amazon Bedrock<br/>Claude 3.5 + Titan]
            Lambda[AWS Lambda<br/>Serverless Runtime]
            DynamoDB[Amazon DynamoDB<br/>Multi-Tenant Storage]
            OpenSearch[Amazon OpenSearch<br/>Semantic Memory]
            EventBridge[Amazon EventBridge<br/>Event Coordination]
            APIGateway[AWS API Gateway<br/>MCP Routing]
        end
        
        subgraph "Circuit Breaker Layer"
            CB[Circuit Breakers<br/>AWS ↔ Local Failover]
            Cache[L1/L2/L3 Cache<br/>Latency Optimization]
            Fallback[Local Infrastructure<br/>Outage Resilience]
        end
    end
    
    subgraph "MCP Agent Ecosystem"
        CommAgent[Communications Agent<br/>LiveKit + Google Realtime<br/>Workflow Orchestration]
        
        subgraph "Isolated MCP Servers"
            AgentSvea[Agent Svea MCP Server<br/>Swedish ERP + Compliance<br/>Construction Industry]
            Felicia[Felicia's Finance MCP Server<br/>Hybrid TradFi-DeFi Banking<br/>AWS Managed Blockchain]
            MeetMind[MeetMind MCP Server<br/>Meeting Intelligence + Fan-In<br/>Result Aggregation]
        end
        
        MCPUIHub[MCP UI Hub<br/>Platform Services<br/>Real-time Updates]
    end
    
    subgraph "User Interface"
        Frontend[React Frontend<br/>Real-time UI Updates<br/>Multi-Tenant Dashboard]
        Mobile[Mobile Apps<br/>iOS + Android<br/>Offline Capability]
    end
    
    subgraph "Tools Store & AWS Marketplace"
        ToolsStore[HappyOS Tools Store<br/>MCP-Compatible Packages<br/>Security Audited]
        AWSMarketplace[AWS Marketplace<br/>Native Billing + Distribution<br/>Enterprise Procurement]
    end
    
    %% MCP Communication Flow
    CommAgent -->|MCP Calls + Reply-To| AgentSvea
    CommAgent -->|MCP Calls + Reply-To| Felicia
    AgentSvea -->|Async Callback| MeetMind
    Felicia -->|Async Callback| MeetMind
    MeetMind -->|Fan-In Results| MCPUIHub
    MCPUIHub -->|Real-time Updates| Frontend
    MCPUIHub -->|Mobile Sync| Mobile
    
    %% AWS Service Integration
    AgentSvea -.->|Uses| Bedrock
    Felicia -.->|Uses| Bedrock
    MeetMind -.->|Uses| Bedrock
    CommAgent -.->|Uses| Lambda
    AgentSvea -.->|Stores| DynamoDB
    Felicia -.->|Stores| DynamoDB
    MeetMind -.->|Searches| OpenSearch
    MCPUIHub -.->|Routes via| APIGateway
    
    %% Circuit Breaker Protection
    CB -.->|Protects| AgentSvea
    CB -.->|Protects| Felicia
    CB -.->|Protects| MeetMind
    Cache -.->|Accelerates| OpenSearch
    Fallback -.->|Backup for| Bedrock
    
    %% Tools Store Integration
    ToolsStore -.->|Deploys to| AgentSvea
    ToolsStore -.->|Deploys to| Felicia
    ToolsStore -.->|Deploys to| MeetMind
    AWSMarketplace -.->|Distributes| ToolsStore
    
    classDef awsService fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef mcpServer fill:#4CAF50,stroke:#2E7D32,stroke-width:2px,color:#fff
    classDef userInterface fill:#2196F3,stroke:#1565C0,stroke-width:2px,color:#fff
    classDef infrastructure fill:#9C27B0,stroke:#6A1B9A,stroke-width:2px,color:#fff
    classDef marketplace fill:#FF5722,stroke:#D84315,stroke-width:2px,color:#fff
    
    class Bedrock,Lambda,DynamoDB,OpenSearch,EventBridge,APIGateway awsService
    class AgentSvea,Felicia,MeetMind,CommAgent,MCPUIHub mcpServer
    class Frontend,Mobile userInterface
    class CB,Cache,Fallback infrastructure
    class ToolsStore,AWSMarketplace marketplace