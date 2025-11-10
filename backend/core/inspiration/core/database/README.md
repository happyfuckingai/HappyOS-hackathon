# Database System - HappyOS Data Persistence

Denna mapp innehåller databassystemet för HappyOS, som hanterar persistent lagring, datamodeller, migrationer och repository-mönster.

## ⚠️ NUVARANDE STATUS - MOCK/SIMULATION

**Vad som är mockat/simulerat:**
- `connection.py` - Grundläggande SQLite-anslutning, ingen avancerad pooling
- `models.py` - Enkla datamodeller, ingen avancerad ORM-funktionalitet
- `migrations.py` - Grundläggande migrationssystem
- `persistence_manager.py` - Enkel persistens, ingen caching eller optimering
- `repositories.py` - Grundläggande CRUD-operationer
- Avancerad indexering saknas
- Query-optimering är inte implementerad
- Distributed database stöd saknas

**För att få systemet i full drift:**
1. Konfigurera produktionsdatabas (PostgreSQL, MongoDB, etc.)
2. Implementera connection pooling och load balancing
3. Sätt upp avancerad indexering och query-optimering
4. Konfigurera automatiska backups och disaster recovery
5. Implementera caching-lager (Redis, Memcached)
6. Sätt upp database monitoring och alerting
7. Konfigurera read replicas för skalbarhet

## Filer

### `connection.py`
Databasanslutningshantering och konfiguration.

**Funktioner:**
- SQLite-anslutning för utveckling
- Grundläggande connection management
- Enkel konfigurationshantering

### `models.py`
Datamodeller för HappyOS-entiteter.

**Modeller:**
- Användardata
- Konversationshistorik
- Skill-metadata
- Systemkonfiguration

### `migrations.py`
Databasmigrationer och schemahantering.

**Funktioner:**
- Automatisk schemamigration
- Versionshantering av databas
- Rollback-funktionalitet

### `persistence_manager.py`
Hantering av datapersistens och caching.

**Funktioner:**
- Enhetligt persistens-API
- Grundläggande caching
- Data serialisering

### `repositories.py`
Repository-mönster för dataåtkomst.

**Repositories:**
- UserRepository
- ConversationRepository
- SkillRepository
- ConfigRepository

## Användning

### Databasanslutning
```python
from app.core.database.connection import get_db_connection

async with get_db_connection() as db:
    result = await db.execute("SELECT * FROM users")
```

### Repository-användning
```python
from app.core.database.repositories import UserRepository

user_repo = UserRepository()
user = await user_repo.create_user({
    "name": "John Doe",
    "email": "john@example.com"
})
```

## Konfiguration

```json
{
  "database": {
    "type": "sqlite",
    "url": "sqlite:///happyos.db",
    "pool_size": 10,
    "max_overflow": 20,
    "echo": false
  },
  "caching": {
    "enabled": true,
    "ttl": 3600,
    "max_size": 1000
  }
}
```

## Säkerhet

- **SQL Injection Protection**: Parametriserade queries
- **Access Control**: Rollbaserad åtkomstkontroll
- **Encryption**: Kryptering av känslig data
- **Audit Logging**: Spårning av alla databasoperationer