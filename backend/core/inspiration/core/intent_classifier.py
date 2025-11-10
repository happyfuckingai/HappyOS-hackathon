"""
Intent classifier for HappyOS.

This module provides functionality to classify user intents, particularly
for code generation requests.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from enum import Enum

from app.config.settings import get_settings
from app.llm.router import get_llm_client

logger = logging.getLogger(__name__)
settings = get_settings()

class IntentType(Enum):
    """Types of intents that can be classified."""
    UNKNOWN = "unknown"
    GREETING = "greeting"
    QUESTION = "question"
    CODE_GENERATION = "code_generation"
    DATA_ANALYSIS = "data_analysis"
    WEB_DEVELOPMENT = "web_development"
    TASK_MANAGEMENT = "task_management"
    CLARIFICATION = "clarification"


class IntentClassifier:
    """
    Classifies user intents, with special focus on code generation requests.
    
    This classifier uses a combination of rule-based patterns and LLM-based
    classification to determine the user's intent.
    """
    
    def __init__(self):
        """Initialize the intent classifier."""
        self.llm_client = get_llm_client()
        
        # Patterns for rule-based classification
        self.patterns = {
            IntentType.GREETING: [
                r"^(hej|hello|hi|hey|goddag|god morgon|god kväll)",
                r"^(tjena|hallå|tja|yo)",
            ],
            IntentType.CODE_GENERATION: [
                r"(skapa|generera|bygg|implementera|skriv|skriva|skriver|skrivit)\s+(en|ett)?\s*(kod|funktion|klass|modul|komponent|script)",
                r"(create|generate|build|implement|write|code)\s+(a|an)?\s*(code|function|class|module|component|script)",
                r"(kod|funktion|klass|modul|komponent|script)\s+(för|som|att)\s+",
            ],
            IntentType.WEB_DEVELOPMENT: [
                r"(skapa|generera|bygg|implementera)\s+(en|ett)?\s*(webbsida|hemsida|webbapp|webapp|webbapplikation|webapplikation)",
                r"(create|generate|build|implement)\s+(a|an)?\s*(webpage|website|web app|webapp|web application)",
            ],
            IntentType.DATA_ANALYSIS: [
                r"(analysera|analys|visualisera|visualisering|data)\s+(data|dataset|information)",
                r"(analyze|analysis|visualize|visualization|data)\s+(data|dataset|information)",
            ],
        }
    
    async def classify(self, user_input: str) -> Dict[str, Any]:
        """
        Classify the user's intent.
        
        Args:
            user_input: The user's input text
            
        Returns:
            A dictionary containing the classified intent
        """
        # Normalize input
        normalized_input = user_input.lower().strip()
        
        # Try rule-based classification first
        intent = self._rule_based_classification(normalized_input)
        
        # If high confidence, return immediately
        if intent["confidence"] > 0.8:
            return intent
        
        # Otherwise, use LLM-based classification
        llm_intent = await self._llm_based_classification(normalized_input)
        
        # Merge results, preferring the higher confidence
        if llm_intent["confidence"] > intent["confidence"]:
            intent = llm_intent
        
        # Extract additional information for code generation
        if intent["type"] == IntentType.CODE_GENERATION.value:
            intent.update(await self._extract_code_generation_details(normalized_input))
        
        return intent
    
    def _rule_based_classification(self, normalized_input: str) -> Dict[str, Any]:
        """
        Perform rule-based classification using regex patterns.
        
        Args:
            normalized_input: Normalized user input
            
        Returns:
            Classification result
        """
        result = {
            "type": IntentType.UNKNOWN.value,
            "confidence": 0.0,
            "method": "rule_based"
        }
        
        # Check each pattern
        for intent_type, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, normalized_input, re.IGNORECASE):
                    result["type"] = intent_type.value
                    result["confidence"] = 0.7  # Base confidence for pattern match
                    
                    # Increase confidence for longer, more specific matches
                    match_length = len(re.search(pattern, normalized_input, re.IGNORECASE).group(0))
                    if match_length > 10:
                        result["confidence"] = 0.8
                    if match_length > 20:
                        result["confidence"] = 0.9
                    
                    return result
        
        return result
    
    async def _llm_based_classification(self, normalized_input: str) -> Dict[str, Any]:
        """
        Use LLM to classify the intent.
        
        Args:
            normalized_input: Normalized user input
            
        Returns:
            Classification result
        """
        prompt = f"""
        Classify the following user input into one of these categories:
        - greeting: General greetings and salutations
        - question: User is asking a question
        - code_generation: User wants to generate code, a function, class, or component
        - data_analysis: User wants to analyze or visualize data
        - web_development: User wants to create a website or web application
        - task_management: User wants to manage tasks or projects
        - clarification: User is asking for clarification
        - unknown: Cannot determine the intent
        
        User input: "{normalized_input}"
        
        Respond with a JSON object with the following structure:
        {{
            "type": "category_name",
            "confidence": 0.0 to 1.0,
            "reasoning": "Brief explanation of why this classification was chosen"
        }}
        """
        
        try:
            response = await self.llm_client.generate_text(prompt)
            
            # Extract JSON from response
            import json
            import re
            
            # Find JSON pattern in the response
            json_match = re.search(r'({.*})', response.replace('\n', ' '), re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                classification = json.loads(json_str)
                
                # Add method information
                classification["method"] = "llm_based"
                
                return classification
            else:
                logger.warning(f"Could not extract JSON from LLM response: {response}")
                return {
                    "type": IntentType.UNKNOWN.value,
                    "confidence": 0.3,
                    "method": "llm_based_failed",
                    "reasoning": "Failed to parse LLM response"
                }
        
        except Exception as e:
            logger.error(f"Error in LLM-based classification: {str(e)}")
            return {
                "type": IntentType.UNKNOWN.value,
                "confidence": 0.2,
                "method": "llm_based_error",
                "reasoning": f"Error: {str(e)}"
            }
    
    async def _extract_code_generation_details(self, normalized_input: str) -> Dict[str, Any]:
        """
        Extract details about code generation request.
        
        Args:
            normalized_input: Normalized user input
            
        Returns:
            Dictionary with code generation details
        """
        # Default values
        details = {
            "language": "python",  # Default language
            "code_type": "function",  # Default code type
            "name": "",  # Name will be extracted by LLM
            "description": ""  # Description will be extracted by LLM
        }
        
        # Extract language
        language_patterns = {
            "python": [r"python", r"py\b"],
            "javascript": [r"javascript", r"js\b", r"node", r"react", r"vue"],
            "typescript": [r"typescript", r"ts\b"],
            "java": [r"java\b", r"spring"],
            "csharp": [r"c#", r"csharp", r"\.net", r"dotnet"],
            "cpp": [r"c\+\+", r"cpp"],
            "go": [r"golang", r"go\b"],
            "rust": [r"rust"],
            "php": [r"php"],
            "ruby": [r"ruby"],
            "swift": [r"swift"],
            "kotlin": [r"kotlin"],
            "sql": [r"sql"]
        }
        
        for lang, patterns in language_patterns.items():
            for pattern in patterns:
                if re.search(pattern, normalized_input, re.IGNORECASE):
                    details["language"] = lang
                    break
        
        # Extract code type
        code_type_patterns = {
            "function": [r"funktion", r"function", r"metod", r"method"],
            "class": [r"klass", r"class"],
            "module": [r"modul", r"module"],
            "component": [r"komponent", r"component"],
            "script": [r"script", r"skript"]
        }
        
        for code_type, patterns in code_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, normalized_input, re.IGNORECASE):
                    details["code_type"] = code_type
                    break
        
        # Use LLM to extract name and description
        prompt = f"""
        Extract the name and description for a code generation request.
        
        User input: "{normalized_input}"
        
        Respond with a JSON object with the following structure:
        {{
            "name": "extracted_name_in_camelCase",
            "description": "Brief description of what the code should do"
        }}
        
        If you can't determine a good name, use a descriptive name based on functionality.
        """
        
        try:
            response = await self.llm_client.generate_text(prompt)
            
            # Extract JSON from response
            import json
            import re
            
            # Find JSON pattern in the response
            json_match = re.search(r'({.*})', response.replace('\n', ' '), re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                extracted = json.loads(json_str)
                
                # Update details
                if "name" in extracted and extracted["name"]:
                    details["name"] = extracted["name"]
                if "description" in extracted and extracted["description"]:
                    details["description"] = extracted["description"]
            
        except Exception as e:
            logger.error(f"Error extracting code generation details: {str(e)}")
        
        return details