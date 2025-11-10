# Logging System - HappyOS Loggning och Spårning

Denna mapp innehåller loggningssystemet för HappyOS, som hanterar strukturerad loggning, log aggregation, analys och spårning.

## ⚠️ NUVARANDE STATUS - MOCK/SIMULATION

**Vad som är mockat/simulerat:**
- Grundläggande Python logging är implementerat
- Strukturerad loggning är enkel
- Log rotation är grundläggande
- Centraliserad loggning saknas
- Log analysis och alerting är mockad
- Distributed tracing saknas
- Performance logging är begränsad

**För att få systemet i full drift:**
1. Sätt upp ELK Stack (Elasticsearch, Logstash, Kibana)
2. Implementera strukturerad JSON-loggning
3. Konfigurera centraliserad log aggregation
4. Sätt upp log-baserade alerting och monitoring
5. Implementera distributed tracing (Jaeger/Zipkin)
6. Konfigurera log retention och archiving
7. Sätt upp log analysis och machine learning

## Komponenter

### Structured Logging
- **JSON Format**: Strukturerade loggar i JSON-format
- **Contextual Information**: Automatisk kontext i alla loggar
- **Correlation IDs**: Spårning av requests genom systemet
- **Metadata Enrichment**: Automatisk anrikning med metadata

### Log Levels
- **DEBUG**: Detaljerad debug-information
- **INFO**: Allmän informationsloggning
- **WARNING**: Varningar och potentiella problem
- **ERROR**: Fel som kräver uppmärksamhet
- **CRITICAL**: Kritiska fel som påverkar systemet

### Log Aggregation
- **Centralized Collection**: Centraliserad insamling av alla loggar
- **Real-time Processing**: Realtidsbearbetning av loggar
- **Filtering and Routing**: Filtrering och routing av loggar
- **Storage Optimization**: Optimerad lagring av loggdata

### Log Analysis
- **Search and Query**: Avancerad sökning i loggar
- **Pattern Recognition**: Automatisk igenkänning av mönster
- **Anomaly Detection**: Detektering av avvikelser i loggar
- **Trend Analysis**: Analys av trender över tid

## Användning

### Grundläggande loggning
```python
import logging

logger = logging.getLogger(__name__)

logger.info("User logged in", extra={
    "user_id": "12345",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
})
```

### Strukturerad loggning
```python
from app.core.logging.structured import StructuredLogger

logger = StructuredLogger(__name__)

logger.log_event("skill_executed", {
    "skill_name": "data_processor",
    "execution_time": 1.23,
    "success": True,
    "user_id": "12345"
})
```

### Correlation tracking
```python
from app.core.logging.correlation import with_correlation_id

@with_correlation_id
async def process_request(request):
    logger.info("Processing request")  # Automatisk correlation ID
```

## Log Format

### Standard JSON Format
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "logger": "app.core.agent.chat_agent",
  "message": "User message processed",
  "correlation_id": "req-12345-67890",
  "user_id": "user123",
  "execution_time": 0.045,
  "metadata": {
    "skill_used": "text_processor",
    "tokens_used": 150
  }
}
```

### Error Format
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "ERROR",
  "logger": "app.core.skills.skill_executor",
  "message": "Skill execution failed",
  "correlation_id": "req-12345-67890",
  "error": {
    "type": "SkillExecutionError",
    "message": "Invalid input parameters",
    "stack_trace": "...",
    "context": {
      "skill_name": "data_processor",
      "input_size": 1024
    }
  }
}
```

## Konfiguration

```json
{
  "logging": {
    "level": "INFO",
    "format": "json",
    "handlers": {
      "console": {
        "enabled": true,
        "level": "INFO"
      },
      "file": {
        "enabled": true,
        "level": "DEBUG",
        "filename": "logs/happyos.log",
        "max_size": "100MB",
        "backup_count": 5
      },
      "elasticsearch": {
        "enabled": true,
        "hosts": ["localhost:9200"],
        "index": "happyos-logs"
      }
    }
  }
}
```

## Log Categories

### System Logs
- Systemstart och shutdown
- Konfigurationsändringar
- Resursanvändning
- Prestanda-metrics

### Application Logs
- Användarinteraktioner
- Skill-exekvering
- API-anrop
- Databearbetning

### Security Logs
- Autentiseringsförsök
- Auktoriseringsfel
- Säkerhetsincidenter
- Åtkomstloggar

### Audit Logs
- Administrativa åtgärder
- Dataändringar
- Systemkonfiguration
- Compliance-händelser

## Log Retention

### Retention Policies
- **DEBUG logs**: 7 dagar
- **INFO logs**: 30 dagar
- **WARNING logs**: 90 dagar
- **ERROR logs**: 1 år
- **CRITICAL logs**: Permanent

### Archiving
- Automatisk arkivering av gamla loggar
- Komprimering för lagringsutrymme
- Cold storage för långtidslagring
- Compliance med datalagringskrav

## Monitoring och Alerting

### Log-based Alerts
- Hög error rate
- Kritiska fel
- Säkerhetsincidenter
- Prestandaproblem

### Dashboards
- Real-time log streams
- Error rate trends
- Performance metrics
- Security events