# Generators System - Automatisk Kodgenerering

Denna mapp innehåller systemet för automatisk generering av kod och komponenter i HappyOS.

## ⚠️ NUVARANDE STATUS - MOCK/SIMULATION

**Vad som är mockat/simulerat:**
- `skill_auto_generator.py` - LLM-integration är mockad, genererar inte verklig kod
- AI-driven kodgenerering är simulerad
- Kodvalidering och testning är grundläggande
- Template-system är inte implementerat
- Säker kod-exekvering saknas

**För att få systemet i full drift:**
1. Konfigurera LLM-klienter (OpenAI GPT-4, Claude, etc.)
2. Implementera säker kod-exekvering i sandbox
3. Sätt upp automatisk kodvalidering och testning
4. Implementera template-system för kodgenerering
5. Konfigurera code review och kvalitetskontroll
6. Sätt upp automatisk dokumentationsgenerering

## Filer

### `skill_auto_generator.py`
Huvudkomponent för automatisk generering av nya skills och komponenter.

**Funktioner:**
- LLM-baserad kodgenerering (mockad)
- Automatisk filskapande och registrering
- Grundläggande kodvalidering
- Integration med skill registry

**Användning:**
```python
from app.core.self_building.generators.skill_auto_generator import SkillAutoGenerator

generator = SkillAutoGenerator()

# Generera en ny skill
skill_code = await generator.generate_skill(
    skill_name="data_processor",
    description="Process CSV data and generate reports",
    requirements=["pandas", "matplotlib"]
)

# Spara och registrera skill
await generator.save_and_register_skill(skill_code)
```

### `examples.py`
Demonstrationsexempel för kod-generering.

## Konfiguration

```json
{
  "llm_provider": "openai",
  "model": "gpt-4",
  "max_tokens": 4000,
  "temperature": 0.1,
  "generated_skills_directory": "app/skills/generated/",
  "validation_enabled": true,
  "auto_testing": true
}
```

## Säkerhet

- **Sandbox Execution**: All genererad kod körs i isolerad miljö
- **Code Review**: Automatisk granskning av genererad kod
- **Validation**: Omfattande validering innan integration
- **Rollback**: Möjlighet att återställa vid problem