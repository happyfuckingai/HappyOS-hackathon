#!/bin/bash

# Gå till app/core
cd "$(dirname "$0")"

# Skapa mappar om de saknas
mkdir -p agent orchestrator

# Flytta MrHappyAgent
if [ -f mr_happy_agent.py ]; then
  mv mr_happy_agent.py agent/
fi

# Flytta self_building_orchestrator
if [ -f self_building_orchestrator.py ]; then
  mv self_building_orchestrator.py orchestrator/
fi

# Flytta skill_registry och skill_generator till skills/
if [ -f skill_registry.py ]; then
  mv skill_registry.py skills/
fi
if [ -f skill_generator.py ]; then
  mv skill_generator.py skills/
fi

# Flytta performance till performance/
if [ -f performance.py ]; then
  mv performance.py performance/
fi

# Flytta error_handler till utils/
if [ -f error_handler.py ]; then
  mv error_handler.py utils/
fi

# Flytta memory_manager till memory/
if [ -f memory_manager.py ]; then
  mv memory_manager.py memory/
fi

# Flytta intent_router till nlp/
if [ -f mcp_intent_router.py ]; then
  mv mcp_intent_router.py nlp/
fi

echo "✅ Strukturen är nu flyttad och uppdelad!"
