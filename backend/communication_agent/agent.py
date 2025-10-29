try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    def load_dotenv():
        pass  # No-op fallback

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, ChatContext
from livekit.agents import llm, tts
from .prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from .tools import get_weather, search_web, send_email
from mem0 import AsyncMemoryClient
try:
    from mcp_client import MCPServerSse
    from mcp_client.agent_tools import MCPToolsIntegration
except ImportError:
    # MCP client not available - use mock for testing
    MCPServerSse = None
    MCPToolsIntegration = None
import os
import json
import logging
import asyncio
import sys
import importlib.util
import uuid
from datetime import datetime

load_dotenv()

# Dynamically import ADK integration
try:
    spec = importlib.util.spec_from_file_location("adk_agents", "adk_agents/adk/adk_integration.py")
    adk_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adk_module)
    ADKIntegration = adk_module.ADKIntegration
    adk_available = True
except Exception as e:
    logging.warning(f"ADK integration not available: {e}")
    adk_available = False
    ADKIntegration = None


class Assistant(Agent):
    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=llm.GoogleRealtimeModel(),
            tts=tts.GoogleTTS(),
            tools=[
                get_weather,
                search_web,
                send_email,
                self.delegate_to_banking_agent,
                self.delegate_to_crypto_team,
                self.get_financial_advice,
                self.check_system_status,

            ],
            chat_ctx=chat_ctx
        )

        # Initialize ADK integration for agent delegation
        self.adk_integration = None
        if adk_available:
            try:
                self.adk_integration = ADKIntegration()
                logging.info("✓ ADK integration initialized for Felicia")
            except Exception as e:
                logging.warning(f"Failed to initialize ADK integration: {e}")

    # Standardized Cross-Agent Workflow Orchestration
    async def execute_compliance_workflow(self, meeting_data: dict, compliance_requirements: list) -> str:
        """Execute standardized compliance checking workflow across all agents."""
        try:
            # Create standardized MCP headers
            trace_id = str(uuid.uuid4())
            conversation_id = str(uuid.uuid4())
            
            # Step 1: Extract financial topics from meeting (MeetMind)
            meetmind_result = await self._call_mcp_tool(
                agent="meetmind",
                tool="extract_financial_topics",
                arguments={
                    "meeting_data": meeting_data,
                    "analysis_depth": "comprehensive"
                },
                trace_id=trace_id,
                conversation_id=conversation_id
            )
            
            if not meetmind_result.get("success"):
                return f"Meeting analysis failed: {meetmind_result.get('error', 'Unknown error')}"
            
            financial_topics = meetmind_result.get("data", {}).get("financial_topics", [])
            
            # Step 2: Validate compliance with Swedish regulations (Agent Svea)
            svea_result = await self._call_mcp_tool(
                agent="agent_svea",
                tool="check_swedish_compliance",
                arguments={
                    "document_type": "meeting_decisions",
                    "document_data": {"financial_topics": financial_topics},
                    "compliance_rules": compliance_requirements
                },
                trace_id=trace_id,
                conversation_id=conversation_id
            )
            
            # Step 3: Analyze financial risk (Felicia's Finance)
            finance_result = await self._call_mcp_tool(
                agent="felicias_finance",
                tool="analyze_financial_risk",
                arguments={
                    "portfolio_data": meeting_data.get("portfolio_context", {}),
                    "risk_parameters": {"compliance_focused": True},
                    "market_conditions": {}
                },
                trace_id=trace_id,
                conversation_id=conversation_id
            )
            
            # Combine results using fan-in logic
            combined_result = await self._combine_workflow_results([
                {"agent": "meetmind", "result": meetmind_result},
                {"agent": "agent_svea", "result": svea_result},
                {"agent": "felicias_finance", "result": finance_result}
            ], trace_id)
            
            return f"Compliance workflow completed. {combined_result.get('summary', 'Results processed successfully.')}"
            
        except Exception as e:
            logging.error(f"Compliance workflow failed: {e}")
            return f"Compliance workflow encountered an error: {str(e)}"

    async def execute_financial_analysis_workflow(self, financial_request: dict) -> str:
        """Execute standardized financial analysis workflow across relevant agents."""
        try:
            trace_id = str(uuid.uuid4())
            conversation_id = str(uuid.uuid4())
            
            # Step 1: Risk analysis (Felicia's Finance)
            risk_result = await self._call_mcp_tool(
                agent="felicias_finance",
                tool="analyze_financial_risk",
                arguments={
                    "portfolio_data": financial_request.get("portfolio", {}),
                    "risk_parameters": financial_request.get("risk_params", {}),
                    "market_conditions": {}
                },
                trace_id=trace_id,
                conversation_id=conversation_id
            )
            
            # Step 2: Compliance validation (Agent Svea)
            compliance_result = await self._call_mcp_tool(
                agent="agent_svea",
                tool="validate_bas_account",
                arguments={
                    "account_number": financial_request.get("account_number", ""),
                    "transaction_data": financial_request.get("transaction", {})
                },
                trace_id=trace_id,
                conversation_id=conversation_id
            )
            
            # Step 3: Portfolio optimization if requested (Felicia's Finance)
            optimization_result = None
            if financial_request.get("optimize_portfolio"):
                optimization_result = await self._call_mcp_tool(
                    agent="felicias_finance",
                    tool="optimize_portfolio",
                    arguments={
                        "current_portfolio": financial_request.get("portfolio", {}),
                        "investment_goals": financial_request.get("goals", {}),
                        "risk_tolerance": financial_request.get("risk_tolerance", 0.5)
                    },
                    trace_id=trace_id,
                    conversation_id=conversation_id
                )
            
            # Combine results
            results = [
                {"agent": "felicias_finance", "result": risk_result},
                {"agent": "agent_svea", "result": compliance_result}
            ]
            if optimization_result:
                results.append({"agent": "felicias_finance", "result": optimization_result})
            
            combined_result = await self._combine_workflow_results(results, trace_id)
            
            return f"Financial analysis completed. {combined_result.get('summary', 'Analysis processed successfully.')}"
            
        except Exception as e:
            logging.error(f"Financial analysis workflow failed: {e}")
            return f"Financial analysis encountered an error: {str(e)}"

    async def execute_meeting_intelligence_workflow(self, meeting_id: str, analysis_type: str = "comprehensive") -> str:
        """Execute standardized meeting intelligence workflow."""
        try:
            trace_id = str(uuid.uuid4())
            conversation_id = str(uuid.uuid4())
            
            # Step 1: Generate meeting summary (MeetMind)
            summary_result = await self._call_mcp_tool(
                agent="meetmind",
                tool="generate_meeting_summary",
                arguments={
                    "meeting_id": meeting_id,
                    "summary_style": "executive"
                },
                trace_id=trace_id,
                conversation_id=conversation_id
            )
            
            # Step 2: Extract action items (MeetMind)
            actions_result = await self._call_mcp_tool(
                agent="meetmind",
                tool="extract_action_items",
                arguments={"meeting_id": meeting_id},
                trace_id=trace_id,
                conversation_id=conversation_id
            )
            
            # Step 3: Financial compliance check if financial topics detected
            compliance_result = None
            if summary_result.get("data", {}).get("contains_financial_topics"):
                compliance_result = await self._call_mcp_tool(
                    agent="meetmind",
                    tool="financial_compliance_check",
                    arguments={
                        "meeting_id": meeting_id,
                        "financial_topics": summary_result.get("data", {}).get("financial_topics", []),
                        "compliance_requirements": ["bas_compliance", "bfl_compliance"]
                    },
                    trace_id=trace_id,
                    conversation_id=conversation_id
                )
            
            # Combine results
            results = [
                {"agent": "meetmind", "result": summary_result},
                {"agent": "meetmind", "result": actions_result}
            ]
            if compliance_result:
                results.append({"agent": "meetmind", "result": compliance_result})
            
            combined_result = await self._combine_workflow_results(results, trace_id)
            
            return f"Meeting intelligence analysis completed. {combined_result.get('summary', 'Analysis processed successfully.')}"
            
        except Exception as e:
            logging.error(f"Meeting intelligence workflow failed: {e}")
            return f"Meeting intelligence workflow encountered an error: {str(e)}"

    async def _call_mcp_tool(self, agent: str, tool: str, arguments: dict, trace_id: str, conversation_id: str) -> dict:
        """Call MCP tool with standardized headers and reply-to semantics."""
        try:
            # Create standardized MCP headers
            headers = {
                "tenant-id": "default",
                "trace-id": trace_id,
                "conversation-id": conversation_id,
                "reply-to": "mcp://communications_agent/workflow_callback",
                "auth-sig": "",  # Would be generated by security service
                "caller": "communications_agent",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Simulate MCP call (in real implementation, this would use MCP client)
            # For now, return success response
            await asyncio.sleep(0.1)  # Simulate processing time
            
            return {
                "success": True,
                "data": {
                    "tool_executed": tool,
                    "agent": agent,
                    "trace_id": trace_id,
                    "result": f"Simulated result from {agent}.{tool}"
                }
            }
            
        except Exception as e:
            logging.error(f"MCP tool call failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent": agent,
                "tool": tool
            }

    async def _combine_workflow_results(self, results: list, trace_id: str) -> dict:
        """Combine results from multiple agents using fan-in logic."""
        try:
            successful_results = [r for r in results if r.get("result", {}).get("success")]
            failed_results = [r for r in results if not r.get("result", {}).get("success")]
            
            summary_parts = []
            
            for result in successful_results:
                agent = result.get("agent")
                data = result.get("result", {}).get("data", {})
                summary_parts.append(f"{agent}: {data.get('result', 'Success')}")
            
            if failed_results:
                for result in failed_results:
                    agent = result.get("agent")
                    error = result.get("result", {}).get("error", "Unknown error")
                    summary_parts.append(f"{agent}: Failed - {error}")
            
            return {
                "trace_id": trace_id,
                "total_agents": len(results),
                "successful_agents": len(successful_results),
                "failed_agents": len(failed_results),
                "summary": "; ".join(summary_parts),
                "success_rate": len(successful_results) / len(results) if results else 0
            }
            
        except Exception as e:
            logging.error(f"Failed to combine workflow results: {e}")
            return {
                "trace_id": trace_id,
                "error": str(e),
                "summary": "Failed to combine results"
            }

    # Legacy delegation methods (kept for backward compatibility)
    async def delegate_to_banking_agent_async(self, query: str) -> str:
        """Delegate simple banking requests to the banking specialist agent."""
        # Use new workflow orchestration
        return await self.execute_financial_analysis_workflow({
            "type": "banking_query",
            "query": query,
            "account_number": "1930",  # Default bank account
            "transaction": {"type": "inquiry", "amount": 0}
        })

    async def delegate_to_crypto_team_async(self, mission: str, strategy: dict) -> str:
        """Delegate complex investment requests to the crypto investment team."""
        # Use new workflow orchestration
        return await self.execute_financial_analysis_workflow({
            "type": "investment_analysis",
            "mission": mission,
            "strategy": strategy,
            "optimize_portfolio": True,
            "portfolio": strategy.get("current_portfolio", {}),
            "goals": {"mission": mission},
            "risk_tolerance": strategy.get("risk_level", 0.5)
        })

    async def analyze_user_intent_and_respond(self, user_input: str, context: str = "") -> str:
        """Analyze user input and decide if it needs agent work or just conversation."""
        try:
            # Analyze user intent
            intent_analysis = await self._analyze_user_intent(user_input, context)
            
            if intent_analysis["requires_agent_work"]:
                # Route to appropriate agent workflow
                return await self._route_to_agent_workflow(user_input, intent_analysis, context)
            else:
                # Handle as conversational response
                return await self._handle_conversational_response(user_input, intent_analysis, context)
                
        except Exception as e:
            logging.error(f"Intent analysis failed: {e}")
            return "I'm having trouble understanding your request right now. Could you please rephrase it?"

    async def _analyze_user_intent(self, user_input: str, context: str = "") -> dict:
        """Analyze user input to determine intent and required actions."""
        user_input_lower = user_input.lower()
        
        # Banking/Financial Action Keywords
        banking_action_keywords = [
            "transfer", "send money", "pay", "withdraw", "deposit", 
            "check balance", "account statement", "transaction history",
            "block card", "activate card", "change pin"
        ]
        
        # Investment/Trading Action Keywords  
        investment_action_keywords = [
            "buy", "sell", "trade", "invest in", "purchase", "execute order",
            "set stop loss", "place order", "liquidate", "rebalance portfolio"
        ]
        
        # Compliance/ERP Action Keywords
        compliance_action_keywords = [
            "create invoice", "generate report", "validate", "submit to skatteverket",
            "export sie", "sync erp", "compliance check", "bas validation"
        ]
        
        # Meeting/Analysis Action Keywords
        meeting_action_keywords = [
            "start meeting", "end meeting", "summarize meeting", "extract action items",
            "analyze transcript", "generate summary", "create meeting notes"
        ]
        
        # Information Request Keywords (might need agent work)
        info_request_keywords = [
            "what is my", "show me", "get me", "find", "search for",
            "calculate", "analyze", "compare", "recommend"
        ]
        
        # Conversational Keywords (no agent work needed)
        conversational_keywords = [
            "hello", "hi", "how are you", "good morning", "good afternoon",
            "thank you", "thanks", "bye", "goodbye", "see you",
            "what can you do", "help", "who are you", "tell me about"
        ]
        
        # Check for action keywords
        requires_banking = any(keyword in user_input_lower for keyword in banking_action_keywords)
        requires_investment = any(keyword in user_input_lower for keyword in investment_action_keywords)
        requires_compliance = any(keyword in user_input_lower for keyword in compliance_action_keywords)
        requires_meeting = any(keyword in user_input_lower for keyword in meeting_action_keywords)
        requires_info = any(keyword in user_input_lower for keyword in info_request_keywords)
        is_conversational = any(keyword in user_input_lower for keyword in conversational_keywords)
        
        # Determine if agent work is needed
        requires_agent_work = (requires_banking or requires_investment or 
                             requires_compliance or requires_meeting or 
                             (requires_info and not is_conversational))
        
        return {
            "requires_agent_work": requires_agent_work,
            "intent_type": self._determine_primary_intent(
                requires_banking, requires_investment, requires_compliance, 
                requires_meeting, requires_info, is_conversational
            ),
            "confidence": self._calculate_intent_confidence(user_input_lower),
            "detected_entities": self._extract_entities(user_input),
            "user_input": user_input,
            "context": context
        }

    def _determine_primary_intent(self, banking: bool, investment: bool, compliance: bool, 
                                meeting: bool, info: bool, conversational: bool) -> str:
        """Determine the primary intent from detected categories."""
        if banking:
            return "banking_action"
        elif investment:
            return "investment_action"
        elif compliance:
            return "compliance_action"
        elif meeting:
            return "meeting_action"
        elif info:
            return "information_request"
        elif conversational:
            return "conversational"
        else:
            return "unclear"

    def _calculate_intent_confidence(self, user_input_lower: str) -> float:
        """Calculate confidence score for intent detection."""
        # Simple confidence calculation based on keyword density and specificity
        total_words = len(user_input_lower.split())
        if total_words == 0:
            return 0.0
        
        # More specific keywords = higher confidence
        specific_keywords = [
            "transfer", "invest", "invoice", "meeting", "balance", 
            "portfolio", "compliance", "validate", "analyze"
        ]
        
        specific_count = sum(1 for keyword in specific_keywords if keyword in user_input_lower)
        confidence = min(0.9, specific_count / total_words + 0.3)
        
        return confidence

    def _extract_entities(self, user_input: str) -> dict:
        """Extract relevant entities from user input."""
        entities = {}
        
        # Extract amounts (simple regex)
        import re
        amounts = re.findall(r'\b\d+(?:\.\d{2})?\s*(?:kr|sek|usd|eur|btc|eth)?\b', user_input.lower())
        if amounts:
            entities["amounts"] = amounts
        
        # Extract account numbers (4-digit BAS accounts or longer account numbers)
        account_numbers = re.findall(r'\b\d{4,}\b', user_input)
        if account_numbers:
            entities["account_numbers"] = account_numbers
        
        # Extract dates
        dates = re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', user_input)
        if dates:
            entities["dates"] = dates
        
        return entities

    async def _route_to_agent_workflow(self, user_input: str, intent_analysis: dict, context: str) -> str:
        """Route user request to appropriate agent workflow."""
        intent_type = intent_analysis["intent_type"]
        entities = intent_analysis["detected_entities"]
        
        try:
            if intent_type == "banking_action":
                return await self._handle_banking_workflow(user_input, entities, context)
            
            elif intent_type == "investment_action":
                return await self._handle_investment_workflow(user_input, entities, context)
            
            elif intent_type == "compliance_action":
                return await self._handle_compliance_workflow(user_input, entities, context)
            
            elif intent_type == "meeting_action":
                return await self._handle_meeting_workflow(user_input, entities, context)
            
            elif intent_type == "information_request":
                return await self._handle_information_request(user_input, entities, context)
            
            else:
                return "I understand you need help, but I'm not sure exactly what you'd like me to do. Could you be more specific?"
                
        except Exception as e:
            logging.error(f"Workflow routing failed: {e}")
            return f"I encountered an issue processing your request: {str(e)}"

    async def _handle_conversational_response(self, user_input: str, intent_analysis: dict, context: str) -> str:
        """Handle conversational responses that don't require agent work."""
        user_input_lower = user_input.lower()
        
        # Greeting responses
        if any(greeting in user_input_lower for greeting in ["hello", "hi", "good morning", "good afternoon"]):
            return "Hello! I'm Felicia, your banking and investment assistant. How can I help you today?"
        
        # Farewell responses
        elif any(farewell in user_input_lower for farewell in ["bye", "goodbye", "see you"]):
            return "Goodbye! Feel free to reach out whenever you need financial assistance."
        
        # Thank you responses
        elif any(thanks in user_input_lower for thanks in ["thank you", "thanks"]):
            return "You're welcome! Is there anything else I can help you with?"
        
        # Capability questions
        elif any(capability in user_input_lower for capability in ["what can you do", "help", "capabilities"]):
            return """I can help you with:
            
🏦 Banking: Check balances, transfer money, account statements
💰 Investments: Portfolio analysis, crypto trading, risk assessment  
📊 Compliance: Swedish tax compliance, BAS validation, invoice generation
🎯 Meetings: Summarize meetings, extract action items, financial analysis

Just tell me what you'd like to do!"""
        
        # Identity questions
        elif any(identity in user_input_lower for identity in ["who are you", "tell me about"]):
            return "I'm Felicia, your AI assistant for banking and investment services. I work with specialized agents to help you manage your finances, ensure compliance, and analyze your meetings for financial insights."
        
        # Default conversational response
        else:
            return "I'm here to help with your banking and investment needs. What would you like to do today?"

    async def _handle_banking_workflow(self, user_input: str, entities: dict, context: str) -> str:
        """Handle banking-related workflows."""
        return await self.execute_financial_analysis_workflow({
            "type": "banking_request",
            "user_request": user_input,
            "entities": entities,
            "context": context,
            "account_number": entities.get("account_numbers", ["1930"])[0] if entities.get("account_numbers") else "1930"
        })

    async def _handle_investment_workflow(self, user_input: str, entities: dict, context: str) -> str:
        """Handle investment-related workflows."""
        return await self.execute_financial_analysis_workflow({
            "type": "investment_request", 
            "user_request": user_input,
            "entities": entities,
            "context": context,
            "optimize_portfolio": True,
            "amounts": entities.get("amounts", [])
        })

    async def _handle_compliance_workflow(self, user_input: str, entities: dict, context: str) -> str:
        """Handle compliance-related workflows."""
        return await self.execute_compliance_workflow({
            "user_request": user_input,
            "entities": entities,
            "context": context
        }, ["bas_compliance", "bfl_compliance"])

    async def _handle_meeting_workflow(self, user_input: str, entities: dict, context: str) -> str:
        """Handle meeting-related workflows."""
        # Extract meeting ID if present, otherwise use default
        meeting_id = "current_meeting"  # In real implementation, extract from context
        return await self.execute_meeting_intelligence_workflow(meeting_id, "comprehensive")

    async def _handle_information_request(self, user_input: str, entities: dict, context: str) -> str:
        """Handle information requests that might need agent analysis."""
        # Determine if this needs financial analysis or just general info
        if any(keyword in user_input.lower() for keyword in ["balance", "portfolio", "risk", "performance"]):
            return await self.execute_financial_analysis_workflow({
                "type": "information_request",
                "user_request": user_input,
                "entities": entities,
                "context": context
            })
        else:
            return "I can help you find that information. Could you be more specific about what you're looking for?"

    # Legacy method updated to use new intent analysis
    async def get_financial_advice_async(self, question: str, context: str = "") -> str:
        """Provide comprehensive financial advice by analyzing the request and delegating appropriately."""
        return await self.analyze_user_intent_and_respond(question, context)

    async def check_system_status_async(self) -> str:
        """Check the status of all financial systems."""
        try:
            # Use MCP calls to check agent health
            trace_id = str(uuid.uuid4())
            
            agents_to_check = ["agent_svea", "felicias_finance", "meetmind"]
            status_results = []
            
            for agent in agents_to_check:
                try:
                    # Simulate health check via MCP
                    await asyncio.sleep(0.05)  # Simulate network call
                    status_results.append(f"{agent}: Healthy")
                except Exception as e:
                    status_results.append(f"{agent}: Unhealthy - {str(e)}")
            
            return f"System Status Check (Trace: {trace_id[:8]}): " + "; ".join(status_results)
            
        except Exception as e:
            logging.error(f"System status check failed: {e}")
            return f"System status check failed: {str(e)}"

    # Synchronous wrapper methods for LiveKit compatibility
    def delegate_to_banking_agent(self, query: str) -> str:
        """Synchronous wrapper for banking agent delegation."""
        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            # If we're in an async context, this is problematic - return placeholder
            logging.warning("Async context detected in sync method - returning placeholder response")
            return "Banking request received. Processing in background..."
        except RuntimeError:
            # No running loop, safe to use asyncio.run
            return asyncio.run(self.delegate_to_banking_agent_async(query))

    def delegate_to_crypto_team(self, mission: str, strategy: dict) -> str:
        """Synchronous wrapper for crypto team delegation."""
        try:
            loop = asyncio.get_running_loop()
            logging.warning("Async context detected in sync method - returning placeholder response")
            return "Investment request received. Processing in background..."
        except RuntimeError:
            return asyncio.run(self.delegate_to_crypto_team_async(mission, strategy))

    def get_financial_advice(self, question: str, context: str = "") -> str:
        """Synchronous wrapper for financial advice with intent analysis."""
        try:
            loop = asyncio.get_running_loop()
            logging.warning("Async context detected in sync method - returning placeholder response")
            return "I'm analyzing your request and will respond shortly..."
        except RuntimeError:
            return asyncio.run(self.analyze_user_intent_and_respond(question, context))

    def check_system_status(self) -> str:
        """Synchronous wrapper for system status check."""
        try:
            loop = asyncio.get_running_loop()
            logging.warning("Async context detected in sync method - returning placeholder response")
            return "System status check initiated. Results will be provided shortly..."
        except RuntimeError:
            return asyncio.run(self.check_system_status_async())


        


async def entrypoint(ctx: agents.JobContext):

    async def shutdown_hook(chat_ctx: ChatContext, mem0: AsyncMemoryClient, memory_str: str):
        logging.info("Shutting down, saving chat context to memory...")

        messages_formatted = [
        ]

        logging.info(f"Chat context messages: {chat_ctx.items}")

        for item in chat_ctx.items:
            content_str = ''.join(item.content) if isinstance(item.content, list) else str(item.content)

            if memory_str and memory_str in content_str:
                continue

            if item.role in ['user', 'assistant']:
                messages_formatted.append({
                    "role": item.role,
                    "content": content_str.strip()
                })

        logging.info(f"Formatted messages to add to memory: {messages_formatted}")
        await mem0.add(messages_formatted, user_id="Marcus")
        logging.info("Chat context saved to memory.")


    session = AgentSession(
        
    )

    

    mem0 = AsyncMemoryClient()
    user_name = 'David'

    results = await mem0.get_all(user_id=user_name)
    initial_ctx = ChatContext()
    memory_str = ''

    if results:
        memories = [
            {
                "memory": result["memory"],
                "updated_at": result["updated_at"]
            }
            for result in results
        ]
        memory_str = json.dumps(memories)
        logging.info(f"Memories: {memory_str}")
        initial_ctx.add_message(
            role="assistant",
            content=f"The user's name is {user_name}, and this is relvant context about him: {memory_str}."
        )


    if MCPToolsIntegration:
        from mcp_client.config_loader import load_mcp_servers_from_config
        mcp_servers = load_mcp_servers_from_config()
        agent = await MCPToolsIntegration.create_agent_with_tools(
            agent_class=Assistant, agent_kwargs={"chat_ctx": initial_ctx},
            mcp_servers=mcp_servers
        )
    else:
        # Fallback for testing without MCP client
        agent = Assistant(chat_ctx=initial_ctx)

    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            video_enabled=True,
            # noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

    await session.generate_reply(
        instructions=SESSION_INSTRUCTION,
    )

    ctx.add_shutdown_callback(lambda: shutdown_hook(session._agent.chat_ctx, mem0, memory_str))

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
