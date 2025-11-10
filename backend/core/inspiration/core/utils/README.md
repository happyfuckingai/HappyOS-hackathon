# Utils System - HappyOS Verktyg och Hjälpfunktioner

Denna mapp innehåller verktyg och hjälpfunktioner för HappyOS, inklusive datavalidering, formatering, kryptering och allmänna utilities.

## ⚠️ NUVARANDE STATUS - MOCK/SIMULATION

**Vad som är mockat/simulerat:**
- Grundläggande utility-funktioner är implementerade
- Datavalidering är enkel
- Krypteringsverktyg använder enkla metoder
- Formatering är grundläggande
- Async utilities är begränsade
- Testing utilities saknas

**För att få systemet i full drift:**
1. Implementera robusta datavaliderings-schemas
2. Sätt upp säkra krypteringsverktyg
3. Utöka async utilities för bättre prestanda
4. Implementera comprehensive testing utilities
5. Lägg till data transformation utilities
6. Sätt upp internationalization (i18n) utilities

## Komponenter

### Data Validation
- **Schema Validation**: Validering mot definierade schemas
- **Type Checking**: Typsäker datavalidering
- **Input Sanitization**: Rensning av användarinput
- **Format Validation**: Validering av dataformat

### Encryption & Security
- **Data Encryption**: Kryptering av känslig data
- **Hash Functions**: Säkra hash-funktioner
- **Token Generation**: Generering av säkra tokens
- **Password Utilities**: Lösenordshantering

### Async Utilities
- **Async Helpers**: Hjälpfunktioner för async-programmering
- **Concurrency Control**: Kontroll av samtidiga operationer
- **Rate Limiting**: Begränsning av operationshastighet
- **Timeout Management**: Hantering av timeouts

### Data Processing
- **JSON Utilities**: JSON-bearbetning och validering
- **Date/Time Utilities**: Datum- och tidshantering
- **String Processing**: Strängbearbetning och formatering
- **File Operations**: Filoperationer och hantering

## Användning

### Datavalidering
```python
from app.core.utils.validation import validate_data, ValidationSchema

schema = ValidationSchema({
    "name": {"type": "string", "required": True},
    "age": {"type": "integer", "min": 0, "max": 150}
})

result = validate_data(user_data, schema)
```

### Kryptering
```python
from app.core.utils.encryption import encrypt_data, decrypt_data

encrypted = encrypt_data("sensitive information")
decrypted = decrypt_data(encrypted)
```

### Async utilities
```python
from app.core.utils.async_helpers import run_with_timeout, batch_process

result = await run_with_timeout(slow_operation(), timeout=30)
results = await batch_process(items, process_item, batch_size=10)
```

## Konfiguration

```json
{
  "utils": {
    "validation": {
      "strict_mode": true,
      "custom_validators": true
    },
    "encryption": {
      "algorithm": "AES-256-GCM",
      "key_rotation": true
    },
    "async": {
      "default_timeout": 30,
      "max_concurrency": 100
    }
  }
}
```