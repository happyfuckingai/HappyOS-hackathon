"""
Natural Language Understanding (NLU) Service for HappyOS.

This service provides intent recognition, entity extraction, and semantic understanding
for user requests in the conversational AI-driven interface.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from app.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class IntentType:
    """Intent types for user requests."""

    CREATE_COMPONENT = "create_component"
    MODIFY_COMPONENT = "modify_component"
    DELETE_COMPONENT = "delete_component"
    QUERY_SYSTEM = "query_system"
    NAVIGATE = "navigate"
    CONFIGURE = "configure"
    HELP = "help"
    UNKNOWN = "unknown"


class EntityType:
    """Entity types for extracting information from user requests."""

    COMPONENT_TYPE = "component_type"
    COMPONENT_NAME = "component_name"
    PROPERTY = "property"
    VALUE = "value"
    ACTION = "action"
    LOCATION = "location"
    SIZE = "size"
    COLOR = "color"
    DATA_SOURCE = "data_source"


class NLUService:
    """
    Natural Language Understanding Service.

    Analyzes user input to extract intent, entities, and semantic meaning
    to enable intelligent component generation and system interaction.
    """

    def __init__(self):
        self.llm_client = OpenRouterClient()
        self.intent_patterns = self._load_intent_patterns()
        self.component_types = self._load_component_types()

    def _load_intent_patterns(self) -> Dict[str, List[str]]:
        """Load regex patterns for intent recognition."""
        return {
            IntentType.CREATE_COMPONENT: [
                r"skapa\s+(?:en\s+)?(.+)",
                r"gör\s+(?:en\s+)?(.+)",
                r"bygg\s+(?:en\s+)?(.+)",
                r"jag\s+vill\s+ha\s+(?:en\s+)?(.+)",
                r"visa\s+mig\s+(?:en\s+)?(.+)",
                r"generera\s+(?:en\s+)?(.+)",
                r"create\s+(?:a\s+)?(.+)",
                r"make\s+(?:a\s+)?(.+)"
            ],
            IntentType.MODIFY_COMPONENT: [
                r"ändra\s+(.+)",
                r"modifiera\s+(.+)",
                r"uppdatera\s+(.+)",
                r"ändra\s+färg\s+på\s+(.+)",
                r"gör\s+(.+)\s+(?:större|mindre|bredare|smalare)",
                r"change\s+(.+)",
                r"modify\s+(.+)",
                r"update\s+(.+)"
            ],
            IntentType.DELETE_COMPONENT: [
                r"ta\s+bort\s+(.+)",
                r"radera\s+(.+)",
                r"delete\s+(.+)",
                r"remove\s+(.+)"
            ],
            IntentType.QUERY_SYSTEM: [
                r"vad\s+kan\s+du\s+göra",
                r"hjälp\s+mig",
                r"hur\s+fungerar\s+detta",
                r"what\s+can\s+you\s+do",
                r"help\s+me",
                r"how\s+does\s+this\s+work"
            ],
            IntentType.CONFIGURE: [
                r"ställ\s+in\s+(.+)",
                r"konfigurera\s+(.+)",
                r"configure\s+(.+)",
                r"set\s+up\s+(.+)"
            ]
        }

    def _load_component_types(self) -> List[str]:
        """Load supported component types."""
        return [
            "dashboard", "form", "chart", "table", "button", "input",
            "card", "modal", "sidebar", "header", "footer", "list",
            "calendar", "map", "player", "viewer", "editor", "terminal",
            "calculator", "timer", "progress", "tabs", "accordion",
            "carousel", "gallery", "menu", "toolbar", "status", "badge"
        ]

    async def analyze_request(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze user input to extract intent, entities, and generate response plan.

        Args:
            user_input: The user's natural language request
            context: Previous conversation context

        Returns:
            Analysis result with intent, entities, confidence, and action plan
        """
        try:
            # Step 1: Extract intent using pattern matching and LLM
            intent_result = await self._extract_intent(user_input)

            # Step 2: Extract entities
            entities = await self._extract_entities(user_input, intent_result["intent"])

            # Step 3: Determine component type if creating
            component_type = None
            if intent_result["intent"] == IntentType.CREATE_COMPONENT:
                component_type = self._classify_component_type(user_input, entities)

            # Step 4: Generate action plan
            action_plan = await self._generate_action_plan(
                intent_result, entities, component_type, context
            )

            return {
                "success": True,
                "intent": intent_result,
                "entities": entities,
                "component_type": component_type,
                "action_plan": action_plan,
                "confidence": intent_result["confidence"],
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error analyzing request: {e}")
            return {
                "success": False,
                "error": str(e),
                "intent": {"type": IntentType.UNKNOWN, "confidence": 0.0},
                "entities": [],
                "action_plan": {"action": "error_recovery"}
            }

    async def _extract_intent(self, user_input: str) -> Dict[str, Any]:
        """Extract intent from user input using pattern matching and LLM."""
        user_input_lower = user_input.lower()

        # Check regex patterns first
        for intent_type, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, user_input_lower):
                    return {
                        "type": intent_type,
                        "confidence": 0.8,
                        "method": "pattern_match",
                        "pattern": pattern
                    }

        # Use LLM for complex cases
        try:
            intent_prompt = f"""
            Analyze this user request and determine the intent. Choose from:
            - create_component: User wants to create/generate something
            - modify_component: User wants to change/modify something existing
            - delete_component: User wants to remove/delete something
            - query_system: User is asking about capabilities or help
            - configure: User wants to configure or set up something
            - navigate: User wants to navigate or move somewhere
            - help: User needs assistance
            - unknown: Cannot determine intent

            User request: "{user_input}"

            Return only the intent type and confidence score (0.0-1.0) in JSON format:
            {{"intent": "intent_type", "confidence": 0.85}}
            """

            response = await self.llm_client.generate(
                messages=[{"role": "user", "content": intent_prompt}],
                temperature=0.1,
                max_tokens=100
            )

            # Parse LLM response
            try:
                import json
                llm_result = json.loads(response["text"])
                return {
                    "type": llm_result.get("intent", IntentType.UNKNOWN),
                    "confidence": llm_result.get("confidence", 0.5),
                    "method": "llm_analysis"
                }
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM intent response: {response['text']}")

        except Exception as e:
            logger.error(f"LLM intent extraction failed: {e}")

        return {
            "type": IntentType.UNKNOWN,
            "confidence": 0.0,
            "method": "fallback"
        }

    async def _extract_entities(self, user_input: str, intent: str) -> List[Dict[str, Any]]:
        """Extract entities from user input."""
        entities = []

        # Component type extraction
        for comp_type in self.component_types:
            if comp_type in user_input.lower():
                entities.append({
                    "type": EntityType.COMPONENT_TYPE,
                    "value": comp_type,
                    "confidence": 0.9
                })

        # Color extraction
        colors = ["röd", "blå", "grön", "gul", "svart", "vit", "grå", "orange", "lila", "rosa",
                 "red", "blue", "green", "yellow", "black", "white", "gray", "orange", "purple", "pink"]
        for color in colors:
            if color in user_input.lower():
                entities.append({
                    "type": EntityType.COLOR,
                    "value": color,
                    "confidence": 0.8
                })

        # Size extraction
        sizes = ["liten", "stor", "medelstor", "bred", "smal", "hög", "låg",
                "small", "large", "medium", "wide", "narrow", "tall", "short"]
        for size in sizes:
            if size in user_input.lower():
                entities.append({
                    "type": EntityType.SIZE,
                    "value": size,
                    "confidence": 0.7
                })

        # Property extraction (simple keyword matching)
        properties = ["namn", "titel", "text", "innehåll", "data", "värde",
                     "name", "title", "text", "content", "data", "value"]
        for prop in properties:
            if prop in user_input.lower():
                entities.append({
                    "type": EntityType.PROPERTY,
                    "value": prop,
                    "confidence": 0.6
                })

        return entities

    def _classify_component_type(self, user_input: str, entities: List[Dict]) -> str:
        """Classify the type of component the user wants to create."""
        user_input_lower = user_input.lower()

        # Check entities first
        for entity in entities:
            if entity["type"] == EntityType.COMPONENT_TYPE:
                return entity["value"]

        # Keyword-based classification
        type_keywords = {
            "dashboard": ["dashboard", "översikt", "panel", "instrumentbräda"],
            "form": ["formulär", "form", "input", "inmatning"],
            "chart": ["diagram", "graf", "chart", "visualisering"],
            "table": ["tabell", "table", "lista", "data"],
            "button": ["knapp", "button", "tryck"],
            "card": ["kort", "card", "panel"],
            "modal": ["modal", "popup", "dialog"],
            "sidebar": ["sidofält", "sidebar", "meny"],
            "calendar": ["kalender", "calendar", "datum"],
            "map": ["karta", "map", "kart"],
            "calculator": ["kalkylator", "calculator", "räknare"],
            "editor": ["editor", "redigerare", "text"],
            "terminal": ["terminal", "kommand", "cmd"],
            "gallery": ["galleri", "gallery", "bilder"],
            "player": ["spelare", "player", "media"]
        }

        for comp_type, keywords in type_keywords.items():
            for keyword in keywords:
                if keyword in user_input_lower:
                    return comp_type

        # Default fallback
        return "component"

    async def _generate_action_plan(self, intent_result: Dict, entities: List[Dict],
                                  component_type: str, context: Optional[Dict]) -> Dict[str, Any]:
        """Generate an action plan based on the analysis."""
        intent = intent_result["type"]

        if intent == IntentType.CREATE_COMPONENT:
            return {
                "action": "generate_component",
                "component_type": component_type,
                "entities": entities,
                "priority": "high",
                "estimated_complexity": self._estimate_complexity(component_type, entities)
            }

        elif intent == IntentType.MODIFY_COMPONENT:
            return {
                "action": "modify_component",
                "entities": entities,
                "priority": "medium",
                "requires_existing_component": True
            }

        elif intent == IntentType.DELETE_COMPONENT:
            return {
                "action": "delete_component",
                "entities": entities,
                "priority": "low",
                "requires_confirmation": True
            }

        elif intent == IntentType.QUERY_SYSTEM:
            return {
                "action": "provide_help",
                "help_type": "capabilities",
                "priority": "low"
            }

        elif intent == IntentType.CONFIGURE:
            return {
                "action": "configure_system",
                "entities": entities,
                "priority": "medium"
            }

        else:
            return {
                "action": "clarify_request",
                "reason": "unknown_intent",
                "priority": "low"
            }

    def _estimate_complexity(self, component_type: str, entities: List[Dict]) -> str:
        """Estimate the complexity of generating a component."""
        complexity_map = {
            "button": "low",
            "input": "low",
            "card": "low",
            "badge": "low",
            "progress": "low",
            "form": "medium",
            "table": "medium",
            "chart": "medium",
            "calendar": "medium",
            "dashboard": "high",
            "editor": "high",
            "calculator": "high"
        }

        base_complexity = complexity_map.get(component_type, "medium")

        # Increase complexity based on number of entities
        if len(entities) > 3:
            if base_complexity == "low":
                return "medium"
            elif base_complexity == "medium":
                return "high"

        return base_complexity


# Global NLU service instance
nlu_service = NLUService()


async def analyze_user_request(user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convenience function to analyze user requests."""
    return await nlu_service.analyze_request(user_input, context)