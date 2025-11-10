# CAMEL System - Legacy Multi-Agent Framework

Denna mapp innehåller CAMEL (Communicative Agents for Mind Exploration of Large Scale Language Model Society) systemet för HappyOS.

## ⚠️ DEPRECATED - ERSÄTTS AV A2A PROTOCOL

**Status:**
- CAMEL-systemet är deprecated och ersätts av A2A Protocol
- Filerna finns kvar för bakåtkompatibilitet
- Ny utveckling ska använda A2A Protocol istället
- Planerad borttagning i framtida versioner

**Vad som är mockat/simulerat:**
- `camel_client.py` - Grundläggande CAMEL-integration, inte fullt funktionell
- `agent_factory.py` - Enkel agentfactory, begränsad funktionalitet
- `camel_config.py` - Grundläggande konfiguration
- `camel_helpers.py` - Hjälpfunktioner för CAMEL-integration
- Multi-agent kommunikation är mockad
- Role-playing agents är inte implementerade

**Migration till A2A Protocol:**
1. Ersätt CAMEL-anrop med A2A Protocol
2. Migrera agent-definitioner till A2A-format
3. Uppdatera kommunikationsprotokoll
4. Testa kompatibilitet med nya systemet

## Komponenter (Legacy)

### CAMEL Client
- Grundläggande CAMEL-integration
- Agent kommunikation
- Role-playing funktionalitet

### Agent Factory
- Skapande av CAMEL-agenter
- Agent konfiguration
- Role assignment

## Migration Guide

### Från CAMEL till A2A
```python
# Gammalt CAMEL-sätt
from app.core.camel.camel_client import CAMELClient
camel_client = CAMELClient()

# Nytt A2A-sätt
from app.a2a_protocol.core.orchestrator import A2AProtocolManager
a2a_manager = A2AProtocolManager()
```

## Rekommendation

**Använd A2A Protocol för all ny utveckling:**
- Bättre prestanda
- Modernare arkitektur
- Aktivt underhåll
- Bättre säkerhet