"""
Summarizer for Happy AI backend.
Generates summaries of conversations.
"""

import logging
from typing import Dict, Any, Optional, List
import asyncio

# Set up logging
logger = logging.getLogger(__name__)

async def generate_summary(context: Dict[str, Any]) -> Optional[str]:
    """
    Generates a summary of a conversation.
    
    Args:
        context: The conversation context
        
    Returns:
        The generated summary, or None if generation failed
    """
    try:
        # Extract messages from context
        messages = context.get("messages", [])
        
        if not messages:
            logger.warning("No messages to summarize")
            return None
        
        # For now, implement a simple summary generation
        # In the future, this could use an AI model
        
        # Count messages by role
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        assistant_messages = [msg for msg in messages if msg["role"] == "assistant"]
        
        # Generate a simple summary
        summary = f"Conversation with {len(messages)} messages "
        summary += f"({len(user_messages)} from user, {len(assistant_messages)} from assistant).\n\n"
        
        # Add the most recent messages
        summary += "Recent topics:\n"
        
        # Get the last 3 user messages
        recent_user_messages = user_messages[-3:]
        for msg in recent_user_messages:
            # Truncate long messages
            content = msg["content"]
            if len(content) > 100:
                content = content[:97] + "..."
            
            summary += f"- {content}\n"
        
        logger.info("Generated conversation summary")
        return summary
    
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return None

async def generate_mindmap(context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Generates a mind map of a conversation.
    
    Creates a structured mind map representation of the conversation
    with topics, subtopics, and relationships.
    
    Args:
        context: The conversation context
        
    Returns:
        The generated mind map, or None if generation failed
    """
    try:
        from app.llm.router import get_llm_client
        
        # Extract messages from context
        messages = context.get("messages", [])
        
        if not messages:
            logger.warning("No messages to create mind map from")
            return None
        
        # Get LLM client for advanced mind map generation
        from app.llm.router import get_llm_client
        llm_client = get_llm_client()

        if llm_client:
            # Use AI to generate a structured mind map
            return await _generate_ai_mindmap(messages, llm_client)
        else:
            # Fallback to basic mind map generation
            return await _generate_basic_mindmap(messages)
            
    except Exception as e:
        logger.error(f"Error generating mind map: {e}")
        return None


async def _generate_ai_mindmap(messages: List[Dict[str, Any]], llm_client) -> Optional[Dict[str, Any]]:
    """
    Generates an AI-powered mind map from conversation messages.
    
    Args:
        messages: List of conversation messages
        llm_client: The LLM client to use
        
    Returns:
        Structured mind map or None if generation failed
    """
    try:
        # Prepare conversation text for analysis
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in messages[-20:]  # Last 20 messages
        ])
        
        # Create prompt for mind map generation
        prompt = f"""
Analysera följande konversation och skapa en strukturerad mind map i JSON-format.
Mind map:en ska innehålla huvudteman, underteman och viktiga punkter.

Konversation:
{conversation_text}

Returnera resultatet som JSON med följande struktur:
{{
    "central_topic": "Huvudämne för konversationen",
    "main_branches": [
        {{
            "topic": "Huvudämne 1",
            "subtopics": ["Underämne 1", "Underämne 2"],
            "importance": 1-10
        }}
    ],
    "key_insights": ["Viktig insikt 1", "Viktig insikt 2"],
    "action_items": ["Åtgärd 1", "Åtgärd 2"]
}}
"""
        
        # Generate mind map using LLM
        response = await llm_client.generate([
            {"role": "user", "content": prompt}
        ], temperature=0.3)
        
        content = response.get("content", "").strip()
        
        # Try to parse JSON response
        import json
        try:
            mindmap_data = json.loads(content)
            logger.info("Generated AI-powered mind map successfully")
            return mindmap_data
        except json.JSONDecodeError:
            logger.warning("LLM response was not valid JSON, falling back to basic mind map")
            return await _generate_basic_mindmap(messages)
            
    except Exception as e:
        logger.error(f"Error in AI mind map generation: {e}")
        return await _generate_basic_mindmap(messages)


async def _generate_basic_mindmap(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a basic mind map from conversation messages.
    
    Args:
        messages: List of conversation messages
        
    Returns:
        Basic structured mind map
    """
    try:
        # Extract basic information
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        assistant_messages = [msg for msg in messages if msg["role"] == "assistant"]
        
        # Identify common topics (simple keyword analysis)
        all_text = " ".join([msg["content"].lower() for msg in messages])
        
        # Common Swedish keywords for different topics
        topic_keywords = {
            "Bokföring": ["faktura", "kvitto", "moms", "bokföring", "ekonomi", "kund"],
            "Filer": ["fil", "bild", "dokument", "ladda", "spara", "media"],
            "Allmänt": ["hjälp", "fråga", "information", "vad", "hur", "varför"],
            "Teknik": ["system", "fel", "problem", "installation", "konfiguration"]
        }
        
        # Count topic relevance
        topic_scores = {}
        for topic, keywords in topic_keywords.items():
            score = sum(1 for keyword in keywords if keyword in all_text)
            if score > 0:
                topic_scores[topic] = score
        
        # Create main branches based on identified topics
        main_branches = []
        for topic, score in sorted(topic_scores.items(), key=lambda x: x[1], reverse=True):
            main_branches.append({
                "topic": topic,
                "subtopics": [f"Diskussion om {topic.lower()}", f"Frågor kring {topic.lower()}"],
                "importance": min(10, score * 2)
            })
        
        # Extract key insights from recent messages
        key_insights = []
        recent_messages = messages[-5:]
        for msg in recent_messages:
            if msg["role"] == "assistant" and len(msg["content"]) > 50:
                # Take first sentence as insight
                first_sentence = msg["content"].split('.')[0]
                if len(first_sentence) > 20:
                    key_insights.append(first_sentence + ".")
        
        # Create basic mind map structure
        mindmap = {
            "central_topic": f"Konversation med {len(messages)} meddelanden",
            "main_branches": main_branches[:5],  # Top 5 topics
            "key_insights": key_insights[:3],  # Top 3 insights
            "action_items": [
                "Fortsätt konversationen",
                "Ställ fler specifika frågor"
            ],
            "statistics": {
                "total_messages": len(messages),
                "user_messages": len(user_messages),
                "assistant_messages": len(assistant_messages)
            }
        }
        
        logger.info("Generated basic mind map successfully")
        return mindmap
        
    except Exception as e:
        logger.error(f"Error in basic mind map generation: {e}")
        return {
            "central_topic": "Konversation",
            "main_branches": [],
            "key_insights": [],
            "action_items": [],
            "error": "Kunde inte generera mind map"
        }


class Summarizer:
    """
    Summarizer class that provides a clean interface for summarization functionality.
    Wraps the existing summarization functions.
    """

    def __init__(self):
        """Initialize the Summarizer."""
        self.logger = logging.getLogger(__name__)

    async def summarize(self, text: str, context: Dict[str, Any] = None) -> str:
        """
        Summarize the given text using conversation context.

        Args:
            text: The text to summarize
            context: Optional context dictionary containing conversation messages

        Returns:
            A summarized version of the text
        """
        try:
            if not text:
                return "Ingen text att sammanfatta."

            # If we have conversation context, use the generate_summary function
            if context and "messages" in context:
                summary = await generate_summary(context)
                return summary or f"Sammanfattning: {text[:200]}{'...' if len(text) > 200 else ''}"

            # Simple text summarization for basic cases
            if len(text) <= 300:
                return text

            # Create a simple summary for longer text
            sentences = text.split('.')
            if len(sentences) <= 3:
                return text

            # Take first and last sentence, add middle summary
            summary = f"{sentences[0].strip()}."

            if len(sentences) > 4:
                middle_summary = f" [Sammanfattat: {len(sentences)} meningar totalt]"
                summary += middle_summary

            if len(sentences) > 1:
                summary += f" {sentences[-1].strip()}."

            return summary

        except Exception as e:
            self.logger.error(f"Error in summarization: {e}")
            return f"Sammanfattning: {text[:100]}{'...' if len(text) > 100 else ''}"

    async def generate_mindmap(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a mind map from conversation context.

        Args:
            context: The conversation context

        Returns:
            The generated mind map or None if generation failed
        """
        return await generate_mindmap(context)