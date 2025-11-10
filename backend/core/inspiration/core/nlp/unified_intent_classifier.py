import logging
import json # Though not directly used in the class, it was in SBO. Keep if LLM might return JSON.
from typing import Dict, Any, List, Optional, Tuple
import re

# Route LLM access through app namespace and allow dynamic, UI-driven configuration
from app.llm.router import get_llm_client
from app.core.config.settings import get_settings  # IntentClassifier uses settings

logger = logging.getLogger(__name__)
settings = get_settings() # Added: IntentClassifier uses settings

class IntentClassifier:
    """
    Classifies user intent and extracts parameters using an LLM.
    It also handles MCP (Model Context Protocol) style requests.
    """

    def __init__(self, model_name: Optional[str] = None, llm_client_type: Optional[str] = None):
        """
        Initialize classifier without reading provider/keys from ENV.
        Provider and model are expected to be injected at runtime via DynamicConfig/UI.
        If unavailable, classifier runs in disabled mode (no vendor names printed).
        """
        # Default model string kept generic; actual model comes from DynamicConfig at call-time if needed
        self.model_name = model_name or "default"
        self.llm_client = None

    async def initialize(self, llm_client_type: Optional[str] = None):
        """
        Asynchronously initializes the IntentClassifier.
        """
        # Try to load dynamic runtime configuration (no ENV leakage)
        # Safe import to avoid hard dependency if dynamic_config is missing
        try:
            from app.config.dynamic_config import get_dynamic_config  # type: ignore
            dyn = await get_dynamic_config()
            configured_type = None
            if dyn and hasattr(dyn, "get"):
                configured_type = dyn.get("llm.provider") or dyn.get("llm.client_type")
                if not self.model_name:
                    self.model_name = dyn.get("llm.model") or self.model_name
        except Exception:
            configured_type = None

        # Resolve client type without exposing vendor names in logs
        actual_client_type = llm_client_type or configured_type

        # Defer client resolution; if not configured, operate disabled
        if actual_client_type:
            try:
                self.llm_client = get_llm_client(actual_client_type)
            except Exception:
                self.llm_client = None
        if not self.llm_client:
            logger.info("IntentClassifier initialized in disabled mode (LLM not configured via UI).")

    def _construct_mcp_detection_prompt(self, request: str) -> str:
        # Simple keyword-based MCP detection for now
        # This is a placeholder for a more robust MCP detection/parsing logic
        # For example, if request starts with "mcp:", "tell model:", etc.
        # A more advanced version could use the LLM to determine if it's an MCP request.
        mcp_keywords = ['mcp:', 'tell model:', 'model context:', 'file:', 'search:', 'web:', 'knowledge:', 'image:', 'transcribe:']
        if any(request.lower().startswith(keyword) for keyword in mcp_keywords):
            # This indicates it *might* be an MCP request.
            # The prompt asks the LLM to confirm and structure it.
            return f"""
Analyze the following user request. Determine if it's an MCP (Model Context Protocol) request.
MCP requests typically involve commands like file operations, web searches, image generation, etc., often prefixed.
If it is an MCP request, identify the 'service' (e.g., file_system, search, firecrawl, knowledge, imagegen, transcription) and extract all relevant 'data' parameters.
The 'data' should be a dictionary of parameters specific to that service.
If it's NOT an MCP request, simply state "Not an MCP request."

User Request: "{request}"

If MCP, provide JSON: {{"is_mcp": true, "service": "service_name", "data": {{...params...}}, "original_request": "{request}"}}
If not MCP, provide JSON: {{"is_mcp": false, "original_request": "{request}"}}
"""
        return "" # Returns empty if not initially looking like MCP based on simple keywords

    async def classify_intent(self, request: str, available_skills: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Classifies the user's intent and extracts parameters.
        Includes MCP request detection.
        """
        if not self.llm_client:
            # Disabled mode: do not call any vendor; provide safe default classification
            return {
                "intent": "unclear",
                "parameters": {},
                "confidence": 0.0,
                "explanation": "LLM disabled",
                "original_request": request
            }

        # Phase 1: MCP Detection (Optional, can be integrated into main prompt)
        # For this version, we'll use a simplified keyword check first, then LLM confirmation if needed.

        # Try to parse as structured MCP command first (e.g., "mcp:service:operation data='...'")
        # This is a simplified parser, a more robust one would be better.
        mcp_match = re.match(r"mcp:(\w+):(\w+)\s*(.*)", request, re.IGNORECASE)
        if mcp_match:
            service, operation, raw_data = mcp_match.groups()
            data_params = {}
            if raw_data:
                try:
                    # Attempt to parse as JSON if it looks like it, otherwise treat as string arg
                    if raw_data.strip().startswith('{') and raw_data.strip().endswith('}'):
                        data_params = json.loads(raw_data)
                    else: # Simplistic key=value parsing, needs improvement for real use
                        for part in raw_data.split(','):
                            if '=' in part:
                                key, value = part.split('=', 1)
                                data_params[key.strip()] = value.strip()
                            else: # if no '=', assume it's a primary unnamed param, e.g. path for file ops
                                if service == "file_system" and "path" not in data_params: # common case
                                     data_params["path"] = part.strip()
                                elif service == "search" and "query" not in data_params:
                                     data_params["query"] = part.strip()
                                else:
                                     data_params["value"] = part.strip() # generic value

                    # Ensure 'operation' is part of the 'data' dict for services that need it (like file_system)
                    if "operation" not in data_params : data_params["operation"] = operation

                except json.JSONDecodeError:
                    logger.warning(f"MCP raw_data '{raw_data}' looked like JSON but failed to parse. Treating as basic string.")
                    data_params = {"raw_command_data": raw_data, "operation": operation} # Fallback
                except Exception as e:
                    logger.warning(f"Error parsing MCP raw_data '{raw_data}': {e}. Treating as basic string.")
                    data_params = {"raw_command_data": raw_data, "operation": operation} # Fallback

            logger.info(f"Parsed structured MCP: service='{service}', operation='{operation}', data='{data_params}'")
            return {
                "intent": "mcp_request", # Special intent for MCP
                "parameters": {
                    "service": service,
                    "data": data_params, # This is the 'data' field for McpSkill
                    "_meta": {"parser": "structured_mcp_regex"}
                },
                "original_request": request
            }

        # If not a structured MCP command, use LLM for general intent classification and potential MCP detection
        prompt_template = self._build_classification_prompt(request, available_skills, context)
        messages = [{"role": "user", "content": prompt_template}]

        try:
            # When calling generate, we can pass self.model_name if the client supports model selection per call
            response = await self.llm_client.generate(messages, temperature=0.1, max_tokens=500, model=self.model_name)
            content = response.get("content", "{}").strip()

            # LLM sometimes returns markdown with JSON block
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()

            parsed_response = json.loads(content)

            # If LLM identifies it as MCP
            if parsed_response.get("is_mcp") and parsed_response.get("service"):
                logger.info(f"LLM identified as MCP: {parsed_response}")
                return {
                    "intent": "mcp_request",
                    "parameters": {
                        "service": parsed_response["service"],
                        "data": parsed_response.get("data", {}),
                         "_meta": {"parser": "llm_mcp_detection"}
                    },
                    "original_request": parsed_response.get("original_request", request)
                }

            # Standard intent classification
            intent = parsed_response.get("intent", "unknown")
            parameters = parsed_response.get("parameters", {})
            confidence = parsed_response.get("confidence", 0.0)
            explanation = parsed_response.get("explanation", "")

            logger.info(f"Intent classification: Intent='{intent}', Params='{parameters}', Confidence='{confidence}', Explanation='{explanation}'")
            return {"intent": intent, "parameters": parameters, "confidence": confidence, "explanation": explanation, "original_request": request}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response for intent classification. Error: {e}. Response: {content}")
            return {"error": "LLM response parse error", "intent": "error_parsing_llm_response", "parameters": {}, "original_request": request}
        except Exception as e:
            logger.error(f"Error during intent classification LLM call: {str(e)}", exc_info=True)
            return {"error": str(e), "intent": "error_llm_call", "parameters": {}, "original_request": request}


    def _build_classification_prompt(self, request: str, available_skills: List[Dict[str, Any]], context: Optional[Dict[str, Any]]) -> str:
        # Context string for the prompt (simplified)
        context_str = json.dumps(context, indent=2, ensure_ascii=False) if context else "None"

        # Skills string for the prompt
        skills_descriptions = "\n".join([
            f"- Skill: \"{s['name']}\" (ID: \"{s['id']}\") - Description: {s['description']} - Capabilities: {', '.join(c['name'] for c in s.get('capabilities', []))}"
            for s in available_skills
        ])

        # Enhanced prompt to also consider MCP requests if not caught by regex
        prompt = f"""
Analyze the user's request and determine the primary intent and any relevant parameters.
Consider if the request is an MCP (Model Context Protocol) command.
MCP services include: 'file_system', 'search', 'firecrawl', 'knowledge', 'imagegen', 'transcription'.
If it is an MCP request, identify the 'service', and extract all 'data' parameters for that service.

Available Skills (for non-MCP general intents):
{skills_descriptions}

User Request: "{request}"
Current Context: {context_str}

Output format MUST be JSON.

If it's an MCP request:
Provide JSON: {{"is_mcp": true, "service": "service_name", "data": {{...parameters...}}, "original_request": "{request}"}}
Example MCP data for file_system: {{"operation": "read", "path": "/example/file.txt"}}
Example MCP data for search: {{"query": "latest AI news"}}

If it's a general intent related to one of the available skills:
Identify the skill ID that best matches the intent.
Provide JSON: {{"intent": "skill_id_or_general_intent_name", "parameters": {{...extracted_parameters...}}, "confidence": <0.0-1.0>, "explanation": "Brief reasoning.", "is_mcp": false, "original_request": "{request}"}}
If the intent is very clear for a specific skill, use the skill's ID as the intent.
If the intent seems general and not directly tied to a specific skill's main capability, use a general intent name (e.g., "general_query", "chat_response").

If the intent is unclear or cannot be handled by available skills or MCP:
Provide JSON: {{"intent": "unclear", "parameters": {{}}, "confidence": 0.0, "explanation": "Reason for uncertainty.", "is_mcp": false, "original_request": "{request}"}}
"""
        return prompt

async def create_unified_intent_classifier():
    """
    Factory function to create and initialize the IntentClassifier.
    """
    classifier = IntentClassifier()
    await classifier.initialize()
    return classifier

unified_intent_classifier = IntentClassifier()
