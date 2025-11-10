# Context System - HappyOS Kontexthantering

Denna mapp innehåller kontextsystemet för HappyOS, som hanterar användarkontext, sessionshantering, kontextbevarande och intelligent kontextanalys.

## ⚠️ NUVARANDE STATUS - MOCK/SIMULATION

**Vad som är mockat/simulerat:**
- Grundläggande kontexthantering är implementerad
- Sessionshantering är enkel
- Kontextanalys är mockad
- Intelligent kontextbevarande saknas
- Cross-session context är begränsad
- Context compression är inte implementerad

**För att få systemet i full drift:**
1. Implementera AI-driven kontextanalys
2. Sätt upp intelligent kontextbevarande över sessioner
3. Konfigurera context compression för långtidslagring
4. Implementera context sharing mellan agenter
5. Sätt upp context-baserad personalisering
6. Konfigurera context security och privacy

## Komponenter

### Context Management
- **Session Context**: Hantering av sessionskontext
- **User Context**: Användarspecifik kontextinformation
- **Conversation Context**: Konversationskontext och historik
- **System Context**: Systemtillstånd och konfiguration

### Context Analysis
- **Relevance Scoring**: Bedömning av kontextrelevans
- **Context Summarization**: Sammanfattning av lång kontext
- **Pattern Recognition**: Igenkänning av kontextmönster
- **Context Prediction**: Förutsägelse av framtida kontextbehov

### Context Storage
- **Persistent Storage**: Beständig lagring av kontext
- **Context Indexing**: Indexering för snabb sökning
- **Context Compression**: Komprimering av gammal kontext
- **Context Archiving**: Arkivering av inaktiv kontext

## Användning

### Kontexthantering
```python
from app.core.context.manager import ContextManager

context_mgr = ContextManager()
context = await context_mgr.get_user_context(user_id)
await context_mgr.update_context(user_id, new_data)
```

### Sessionskontext
```python
from app.core.context.session import SessionContext

session = SessionContext(session_id)
session.add_interaction(user_message, bot_response)
relevant_history = session.get_relevant_history(query)
```

## Konfiguration

```json
{
  "context": {
    "max_context_length": 10000,
    "compression_threshold": 5000,
    "relevance_threshold": 0.7,
    "retention_days": 90
  }
}
```