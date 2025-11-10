# Implementation Plan: LLM Integration för Multiagent Teams

## Overview

Detta är implementation-planen för att integrera LLM-kapacitet i alla multiagent-team genom en centraliserad LLM-tjänst i core-infrastrukturen. Planen följer samma arkitekturmönster som befintliga core-tjänster (AgentCoreService, SearchService, etc.).

## Task List

- [x] 1. Core LLM Service Infrastructure
  - Skapa LLMService interface i core
  - Implementera base LLM service med provider-routing
  - Implementera caching och circuit breaker
  - _Requirements: 5.1, 5.2, 5.3, 5.6_

- [x] 1.1 Lägg till LLMService interface i core/interfaces.py
  - Definiera LLMService abstract class med metoder: generate_completion, generate_streaming_completion, get_usage_stats
  - Lägg till LLMRequest och LLMResponse dataclasses
  - Lägg till LLMUsageStats dataclass
  - Uppdatera ServiceFactory interface med create_llm_service metod
  - _Requirements: 5.1, 5.2_

- [x] 1.2 Skapa core/llm/ directory structure
  - Skapa backend/core/llm/__init__.py
  - Skapa backend/core/llm/llm_service.py (base implementation)
  - Skapa backend/core/llm/providers/ directory
  - Skapa backend/core/llm/cache_manager.py
  - _Requirements: 5.1_

- [x] 1.3 Implementera base LLMService i core/llm/llm_service.py
  - Implementera BaseLLMService class med provider routing-logik
  - Implementera _generate_cache_key metod
  - Implementera _log_usage metod för monitoring
  - Implementera error handling och retry-logik
  - _Requirements: 5.1, 5.2, 5.7_

- [x] 1.4 Implementera LLM cache manager
  - Skapa CacheManager class i core/llm/cache_manager.py
  - Implementera cache key generation med prompt hashing
  - Implementera TTL-baserad cache invalidation
  - Implementera cache hit/miss metrics
  - _Requirements: 5.5_

- [x] 2. LLM Provider Implementations
  - Implementera OpenAI provider
  - Implementera AWS Bedrock provider
  - Implementera Google GenAI provider
  - _Requirements: 5.2, 5.3_

- [x] 2.1 Implementera OpenAI provider
  - Skapa core/llm/providers/openai_provider.py
  - Implementera OpenAIProvider class med AsyncOpenAI
  - Implementera generate_completion metod
  - Implementera generate_streaming_completion metod
  - Implementera error handling för OpenAI-specifika fel
  - _Requirements: 5.2, 5.7_

- [x] 2.2 Implementera AWS Bedrock provider
  - Skapa core/llm/providers/bedrock_provider.py
  - Implementera BedrockProvider class med boto3 bedrock-runtime client
  - Implementera generate_completion metod för Claude-modeller
  - Implementera model ID mapping (claude-3-sonnet, claude-3-haiku, etc.)
  - Implementera error handling för Bedrock-specifika fel
  - _Requirements: 5.2, 5.3, 5.7_

- [x] 2.3 Implementera Google GenAI provider
  - Skapa core/llm/providers/google_genai_provider.py
  - Implementera GoogleGenAIProvider class med google.generativeai
  - Implementera generate_completion metod för Gemini-modeller
  - Implementera model mapping (gemini-1.5-flash, gemini-1.5-pro, etc.)
  - Implementera error handling för GenAI-specifika fel
  - _Requirements: 5.2, 5.7_

- [x] 3. AWS LLM Adapter Implementation
  - Skapa AWS LLM adapter med Bedrock + fallback
  - Integrera med ElastiCache för caching
  - Integrera med circuit breaker
  - _Requirements: 5.2, 5.3, 5.5, 5.6_

- [x] 3.1 Skapa AWS LLM adapter
  - Skapa infrastructure/aws/services/llm_adapter.py
  - Implementera AWSLLMAdapter class som implementerar LLMService interface
  - Initiera Bedrock client, OpenAI fallback, och ElastiCache
  - Implementera tenant isolation för cache keys
  - _Requirements: 5.2, 5.3_

- [x] 3.2 Implementera generate_completion i AWS adapter
  - Implementera cache lookup via ElastiCache
  - Implementera Bedrock call med circuit breaker
  - Implementera fallback till OpenAI vid Bedrock-fel
  - Implementera cache storage för successful responses
  - Implementera usage logging till DynamoDB
  - _Requirements: 5.2, 5.3, 5.5, 5.6, 5.8_

- [x] 3.3 Implementera streaming completion i AWS adapter
  - Implementera streaming från Bedrock
  - Implementera fallback till OpenAI streaming
  - Implementera error handling för streaming
  - _Requirements: 5.2, 5.3_

- [x] 3.4 Implementera usage tracking i AWS adapter
  - Skapa DynamoDB table för LLM usage logs
  - Implementera _log_usage metod som skriver till DynamoDB
  - Implementera get_usage_stats metod som läser från DynamoDB
  - Implementera cost calculation baserat på tokens och model
  - _Requirements: 5.8_

- [x] 4. Local LLM Service Implementation
  - Skapa local LLM service för development
  - Implementera in-memory caching
  - Implementera OpenAI-only fallback
  - _Requirements: 5.2, 5.6_

- [x] 4.1 Skapa local LLM service
  - Skapa infrastructure/local/services/llm_service.py
  - Implementera LocalLLMService class som implementerar LLMService interface
  - Initiera AsyncOpenAI client med miljövariabel
  - Implementera simple in-memory cache (dict)
  - _Requirements: 5.2, 5.6_

- [x] 4.2 Implementera generate_completion i local service
  - Implementera cache lookup från in-memory dict
  - Implementera OpenAI call
  - Implementera cache storage
  - Implementera basic usage logging till fil
  - _Requirements: 5.2, 5.6_

- [x] 5. Service Facade Integration
  - Uppdatera ServiceFacade för LLM service
  - Implementera circuit breaker för LLM
  - Implementera automatic failover AWS -> Local
  - _Requirements: 5.3, 5.6_

- [x] 5.1 Uppdatera ServiceFacade med LLM service
  - Lägg till create_llm_service metod i ServiceFacade
  - Implementera LLM service initialization i __init__
  - Implementera mode-baserad routing (AWS vs Local)
  - Lägg till LLM health check i service health monitoring
  - _Requirements: 5.3, 5.6_

- [x] 5.2 Implementera LLM circuit breaker
  - Skapa LLMCircuitBreaker i core/circuit_breaker/
  - Implementera failure threshold detection
  - Implementera automatic failover till local service
  - Implementera half-open state för recovery testing
  - _Requirements: 5.3, 5.6_

- [ ] 6. MeetMind Team LLM Integration (BEHÖVER REFAKTORERING)
  - **PROBLEM**: MeetMind använder fortfarande direkt AsyncOpenAI istället för centraliserad LLMService
  - **ÅTGÄRD**: Refaktorera alla 5 MeetMind-agenter från AsyncOpenAI till LLMService (samma som Agent Svea och Felicia's Finance)
  - Migrera från direkt AsyncOpenAI till centraliserad backend/core/llm LLMService
  - Implementera fallback-logik
  - Testa LLM-integration
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [ ] 6.1 Refaktorera MeetMind Coordinator Agent till LLMService
  - **TA BORT**: `from openai import AsyncOpenAI` och `self.llm_client = AsyncOpenAI(api_key=api_key)`
  - **LÄGG TILL**: LLMService dependency injection i __init__ (samma pattern som Agent Svea)
  - **ERSÄTT**: `self.llm_client.chat.completions.create()` med `self.llm_service.generate_completion()`
  - Uppdatera alla LLM-anrop till att använda centraliserad LLMService
  - Behåll befintlig prompt-struktur och fallback-logik
  - Testa att workflow coordination fungerar med LLMService
  - _Requirements: 3.1, 3.6_

- [ ] 6.2 Refaktorera MeetMind Architect Agent till LLMService
  - **TA BORT**: Direkt AsyncOpenAI import och initialisering
  - **LÄGG TILL**: LLMService dependency injection i __init__
  - **ERSÄTT**: Alla AsyncOpenAI-anrop med llm_service.generate_completion()
  - Implementera LLM-baserad framework design i design_analysis_framework
  - Implementera structured prompts för technical architecture
  - Implementera fallback till regelbaserad logik vid LLM-fel
  - Testa med centraliserad LLM service
  - _Requirements: 3.2, 3.6_

- [ ] 6.3 Refaktorera MeetMind Product Manager Agent till LLMService
  - **TA BORT**: Direkt AsyncOpenAI import och initialisering
  - **LÄGG TILL**: LLMService dependency injection i __init__
  - **ERSÄTT**: Alla AsyncOpenAI-anrop med llm_service.generate_completion()
  - Implementera LLM-baserad requirements analysis i define_requirements
  - Implementera LLM-baserad feature prioritization i prioritize_features
  - Implementera structured prompts för product management
  - Implementera fallback till regelbaserad logik vid LLM-fel
  - Testa med centraliserad LLM service
  - _Requirements: 3.3, 3.6_

- [ ] 6.4 Refaktorera MeetMind Implementation Agent till LLMService
  - **TA BORT**: Direkt AsyncOpenAI import och initialisering
  - **LÄGG TILL**: LLMService dependency injection i __init__
  - **ERSÄTT**: Alla AsyncOpenAI-anrop med llm_service.generate_completion()
  - Implementera LLM-baserad pipeline implementation i implement_analysis_pipeline
  - Implementera LLM-baserad transcript processing i process_meeting_transcript
  - Implementera structured prompts för implementation
  - Implementera fallback till regelbaserad logik vid LLM-fel
  - Testa med centraliserad LLM service
  - _Requirements: 3.4, 3.6_

- [ ] 6.5 Refaktorera MeetMind Quality Assurance Agent till LLMService
  - **TA BORT**: Direkt AsyncOpenAI import och initialisering
  - **LÄGG TILL**: LLMService dependency injection i __init__
  - **ERSÄTT**: Alla AsyncOpenAI-anrop med llm_service.generate_completion()
  - Implementera LLM-baserad quality validation i validate_analysis_quality
  - Implementera LLM-baserad performance testing i test_system_performance
  - Implementera structured prompts för QA
  - Implementera fallback till regelbaserad logik vid LLM-fel
  - Testa med centraliserad LLM service
  - _Requirements: 3.5, 3.6_

- [x] 7. Agent Svea Team LLM Integration
  - Integrera alla 5 Agent Svea-agenter med LLM service
  - Implementera svenskfokuserade prompts
  - Testa LLM-integration med svenska texter
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [x] 7.1 Integrera Agent Svea Coordinator Agent
  - Lägg till LLMService dependency injection i __init__
  - Implementera LLM-baserad compliance workflow coordination
  - Implementera svenskfokuserade prompts för svenska regelverket
  - Implementera fallback till befintlig MCP server-logik vid LLM-fel
  - Testa med svenska compliance-scenarios
  - _Requirements: 4.1, 4.6, 4.7_

- [x] 7.2 Integrera Agent Svea Architect Agent
  - Lägg till LLMService dependency injection i __init__
  - Implementera LLM-baserad ERPNext architecture design
  - Implementera svenskfokuserade prompts för svensk systemdesign
  - Implementera fallback till befintlig design-logik vid LLM-fel
  - Testa med svenska ERP-scenarios
  - _Requirements: 4.2, 4.6, 4.7_

- [x] 7.3 Integrera Agent Svea Product Manager Agent
  - Lägg till LLMService dependency injection i __init__
  - Implementera LLM-baserad regulatory requirements analysis
  - Implementera svenskfokuserade prompts för svenska regulatoriska krav
  - Implementera fallback till befintlig analys-logik vid LLM-fel
  - Testa med svenska regelverks-scenarios (GDPR, BFL, etc.)
  - _Requirements: 4.3, 4.6, 4.7_

- [x] 7.4 Integrera Agent Svea Implementation Agent
  - Lägg till LLMService dependency injection i __init__
  - Implementera LLM-baserad ERP customization implementation
  - Implementera svenskfokuserade prompts för svensk bokföringslogik
  - Implementera fallback till befintlig implementation-logik vid LLM-fel
  - Testa med svenska ERP-customization-scenarios
  - _Requirements: 4.4, 4.6, 4.7_

- [x] 7.5 Integrera Agent Svea Quality Assurance Agent
  - Lägg till LLMService dependency injection i __init__
  - Implementera LLM-baserad compliance accuracy validation
  - Implementera svenskfokuserade prompts för svensk compliance-testning
  - Implementera fallback till befintlig validering-logik vid LLM-fel
  - Testa med svenska compliance-test-scenarios
  - _Requirements: 4.5, 4.6, 4.7_

- [x] 8. Felicia's Finance Refactoring
  - Refaktorera alla 6 Felicia's Finance-agenter till LLM service
  - Migrera från direkt AsyncOpenAI till centraliserad service
  - Testa att befintlig funktionalitet fungerar
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 8.1 Refaktorera Felicia's Finance Coordinator Agent
  - Ersätt direkt AsyncOpenAI med LLMService dependency injection
  - Uppdatera alla LLM-anrop till att använda llm_service.generate_completion
  - Behåll befintlig prompt-struktur och logik
  - Testa att workflow execution fungerar som tidigare
  - _Requirements: 2.1, 2.7_

- [x] 8.2 Refaktorera Felicia's Finance Architect Agent
  - Ersätt direkt AsyncOpenAI med LLMService dependency injection
  - Uppdatera alla LLM-anrop till att använda llm_service.generate_completion
  - Behåll befintlig technical design-logik
  - Testa att design generation fungerar som tidigare
  - _Requirements: 2.2, 2.7_

- [x] 8.3 Refaktorera Felicia's Finance Product Manager Agent
  - Ersätt direkt AsyncOpenAI med LLMService dependency injection
  - Uppdatera alla LLM-anrop till att använda llm_service.generate_completion
  - Behåll befintlig strategy-logik
  - Testa att mission analysis fungerar som tidigare
  - _Requirements: 2.3, 2.7_

- [x] 8.4 Refaktorera Felicia's Finance Implementation Agent
  - Ersätt direkt AsyncOpenAI med LLMService dependency injection
  - Uppdatera alla LLM-anrop till att använda llm_service.generate_completion
  - Behåll befintlig execution planning-logik
  - Testa att trading plan execution fungerar som tidigare
  - _Requirements: 2.4, 2.7_

- [x] 8.5 Refaktorera Felicia's Finance Quality Assurance Agent
  - Ersätt direkt AsyncOpenAI med LLMService dependency injection
  - Uppdatera alla LLM-anrop till att använda llm_service.generate_completion
  - Behåll befintlig validation-logik
  - Testa att execution validation fungerar som tidigare
  - _Requirements: 2.5, 2.7_

- [x] 8.6 Refaktorera Felicia's Finance Banking Agent
  - Ersätt direkt Google GenAI med LLMService dependency injection
  - Uppdatera alla LLM-anrop till att använda llm_service.generate_completion med gemini-model
  - Behåll befintlig banking operations-logik
  - Testa att banking requests fungerar som tidigare
  - _Requirements: 2.6, 2.7_

- [x] 9. Monitoring och Observability
  - Implementera LLM usage metrics
  - Implementera cost tracking
  - Implementera performance monitoring
  - _Requirements: 5.8_

- [x] 9.1 Implementera Prometheus metrics för LLM
  - Skapa core/llm/metrics.py med Prometheus counters och histograms
  - Implementera llm_requests_total counter (per agent, model, provider)
  - Implementera llm_request_duration_seconds histogram
  - Implementera llm_tokens_used_total counter
  - Implementera llm_cache_hits_total och llm_cache_misses_total counters
  - Implementera llm_errors_total counter (per error type)
  - _Requirements: 5.8_

- [x] 9.2 Implementera cost tracking
  - Skapa core/llm/cost_calculator.py
  - Implementera token-to-cost mapping för olika modeller (GPT-4, Claude, Gemini)
  - Implementera calculate_cost metod baserat på tokens och model
  - Implementera daily cost aggregation
  - Implementera budget alert threshold checking
  - _Requirements: 5.8_

- [x] 9.3 Implementera LLM usage dashboard
  - Skapa observability/dashboards/llm_usage_dashboard.json (Grafana)
  - Implementera panels för requests per agent
  - Implementera panels för cost per team
  - Implementera panels för latency distribution
  - Implementera panels för cache hit rate
  - Implementera panels för error rate per provider
  - _Requirements: 5.8_

- [x] 10. Testing och Validation
  - Skriva unit tests för LLM service
  - Skriva integration tests
  - Skriva performance tests
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

- [x] 10.1 Unit tests för core LLM service
  - Testa BaseLLMService med mock providers
  - Testa cache key generation
  - Testa provider routing-logik
  - Testa error handling och retry-logik
  - _Requirements: 10.1, 10.2_

- [x] 10.2 Unit tests för LLM providers
  - Testa OpenAIProvider med mock AsyncOpenAI
  - Testa BedrockProvider med mock boto3 client
  - Testa GoogleGenAIProvider med mock genai client
  - Testa error handling för varje provider
  - _Requirements: 10.1, 10.2_

- [x] 10.3 Integration tests för AWS LLM adapter
  - Testa AWSLLMAdapter med riktiga AWS-tjänster (test environment)
  - Testa Bedrock integration
  - Testa ElastiCache caching
  - Testa circuit breaker failover
  - Testa fallback till OpenAI
  - _Requirements: 10.2, 10.3, 10.5_

- [x] 10.4 Integration tests för agent LLM usage
  - Testa MeetMind Coordinator med LLM service
  - Testa Agent Svea Product Manager med svenska prompts
  - Testa Felicia's Finance Architect med refactored code
  - Testa fallback-funktionalitet när LLM är otillgänglig
  - _Requirements: 10.2, 10.4, 10.6_

- [ ] 10.5 Performance tests för LLM service
  - Testa latency för olika providers (Bedrock vs OpenAI vs Gemini)
  - Testa cache hit rate med realistic workload
  - Testa concurrent requests (100+ simultaneous)
  - Testa cost per 1000 requests
  - _Requirements: 10.6_

- [x] 10.6 Load tests för production readiness
  - Testa 1000 requests/minute sustained load
  - Testa circuit breaker under high error rate
  - Testa failover time från AWS till Local
  - Testa memory usage under load
  - _Requirements: 10.6, 10.7_

- [x] 11. Documentation och Deployment
  - Dokumentera LLM service API
  - Uppdatera README med LLM-konfiguration
  - Skapa deployment guide
  - _Requirements: 5.8, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

- [x] 11.1 Dokumentera LLM Service API
  - Skapa backend/core/llm/README.md
  - Dokumentera LLMService interface methods
  - Dokumentera provider configuration
  - Dokumentera cache configuration
  - Dokumentera usage tracking
  - Inkludera code examples för varje agent-typ
  - _Requirements: 5.8_

- [x] 11.2 Uppdatera miljövariabel-dokumentation
  - Uppdatera root README.md med LLM environment variables
  - Dokumentera OPENAI_API_KEY requirement
  - Dokumentera GOOGLE_API_KEY requirement (optional)
  - Dokumentera AWS credentials för Bedrock
  - Skapa .env.example med alla LLM-variabler
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 11.3 Skapa deployment guide
  - Skapa docs/llm_deployment_guide.md
  - Dokumentera AWS infrastructure setup (Bedrock, ElastiCache, DynamoDB)
  - Dokumentera local development setup
  - Dokumentera production deployment checklist
  - Dokumentera monitoring setup
  - Dokumentera troubleshooting guide
  - _Requirements: 9.6, 9.7_

- [x] 11.4 Uppdatera agent-specifik dokumentation
  - Uppdatera backend/agents/meetmind/README.md med LLM usage
  - Uppdatera backend/agents/agent_svea/README.md med LLM usage
  - Uppdatera backend/agents/felicias_finance/README.md med LLM changes
  - Dokumentera fallback-beteende för varje agent
  - _Requirements: 5.8_

- [x] 12. Production Deployment
  - Deploy LLM service till AWS
  - Migrera alla agenter till production
  - Övervaka initial deployment
  - _Requirements: 5.8, 9.6, 9.7_

- [x] 12.1 Deploy AWS infrastructure för LLM service
  - Deploy DynamoDB table för LLM usage logs
  - Deploy ElastiCache cluster för LLM caching
  - Konfigurera AWS Bedrock access och permissions
  - Konfigurera API keys i AWS Secrets Manager
  - Testa infrastructure connectivity
  - _Requirements: 9.6, 9.7_

- [x] 12.2 Deploy LLM service till production
  - Deploy updated backend code med LLM service
  - Deploy updated agent code (MeetMind, Agent Svea, Felicia's Finance)
  - Konfigurera environment variables i production
  - Verifiera health checks för LLM service
  - _Requirements: 9.6, 9.7_

- [x] 12.3 Övervaka initial production deployment
  - Övervaka LLM request latency första 24h
  - Övervaka error rate och circuit breaker state
  - Övervaka cost per hour
  - Övervaka cache hit rate
  - Verifiera att alla agenter fungerar korrekt
  - _Requirements: 5.8, 9.6_

- [x] 12.4 Production validation och rollback plan
  - Testa alla agent-typer i production
  - Verifiera fallback-funktionalitet
  - Dokumentera rollback procedure om problem uppstår
  - Skapa incident response plan för LLM outages
  - _Requirements: 9.6, 9.7_
