# Service Manager - HappyOS Tjänstehantering

Denna mapp innehåller tjänstehanteringssystemet för HappyOS, som hanterar livscykeln för alla systemtjänster, dependency injection och service discovery.

## ⚠️ NUVARANDE STATUS - MOCK/SIMULATION

**Vad som är mockat/simulerat:**
- Grundläggande service lifecycle management
- Enkel dependency injection
- Service discovery är mockad
- Health checks är grundläggande
- Service orchestration är begränsad
- Auto-scaling saknas

**För att få systemet i full drift:**
1. Implementera robust service discovery (Consul, etcd)
2. Sätt upp comprehensive health checking
3. Konfigurera service mesh för kommunikation
4. Implementera auto-scaling baserat på load
5. Sätt upp service monitoring och alerting
6. Konfigurera graceful shutdown och restart

## Komponenter

### Service Lifecycle
- **Service Registration**: Registrering av tjänster
- **Startup/Shutdown**: Kontrollerad start och stopp
- **Health Monitoring**: Kontinuerlig hälsoövervakning
- **Dependency Management**: Hantering av tjänsteberoenden

### Service Discovery
- **Service Registry**: Register över tillgängliga tjänster
- **Load Balancing**: Lastbalansering mellan tjänster
- **Failover**: Automatisk failover vid fel
- **Service Mesh**: Kommunikation mellan tjänster

### Dependency Injection
- **Container Management**: Hantering av DI-container
- **Lifecycle Scopes**: Olika livscykler för objekt
- **Configuration Injection**: Injektion av konfiguration
- **Interface Binding**: Bindning av interfaces till implementationer

## Användning

### Service Registration
```python
from app.core.service_manager.manager import ServiceManager

service_manager = ServiceManager()
await service_manager.register_service("chat_agent", ChatAgent())
```

### Dependency Injection
```python
from app.core.service_manager.di import inject, Injectable

@Injectable
class MyService:
    def __init__(self, config: Config = inject()):
        self.config = config
```

## Konfiguration

```json
{
  "service_manager": {
    "auto_discovery": true,
    "health_check_interval": 30,
    "restart_on_failure": true,
    "max_restart_attempts": 3
  }
}
```