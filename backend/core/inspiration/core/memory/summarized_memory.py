"""
Summarized Memory System for HappyOS.

Uses summarizer to determine what to store and provides intelligent memory retrieval
with mindmap integration and conversation flow awareness.
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import re

from app.core.ai.summarizer import Summarizer
from app.core.memory.intelligent_memory import IntelligentMemoryManager
from app.core.memory.context_memory import PersistentContextMemory

logger = logging.getLogger(__name__)


@dataclass
class MemorySummary:
    """Represents a summarized memory entry."""
    conversation_id: str
    summary_id: str
    content_summary: str
    mindmap: Optional[Dict[str, Any]] = None
    key_insights: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    relevance_score: float = 0.0
    topics: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    conversation_flow: Dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConversationFlow:
    """Represents conversation flow analysis."""
    stages: List[str] = field(default_factory=list)
    current_stage: str = ""
    transitions: List[Tuple[str, str]] = field(default_factory=list)
    completion_status: Dict[str, bool] = field(default_factory=dict)
    blockers: List[str] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)


class SummarizedMemory:
    """
    Intelligent summarized memory system that uses summarizer to determine what to store
    and provides structured memory retrieval with mindmap integration.
    """

    def __init__(self, intelligent_memory: IntelligentMemoryManager,
                 context_memory: PersistentContextMemory,
                 auto_summarize_threshold: int = 10):
        """
        Initialize summarized memory system.

        Args:
            intelligent_memory: Intelligent memory manager instance
            context_memory: Persistent context memory instance
            auto_summarize_threshold: Number of messages before auto-summarization
        """
        self.intelligent_memory = intelligent_memory
        self.context_memory = context_memory
        self.summarizer = Summarizer()

        self.auto_summarize_threshold = auto_summarize_threshold

        # Memory storage
        self._summaries: Dict[str, MemorySummary] = {}
        self._conversation_summaries: Dict[str, List[str]] = defaultdict(list)  # conversation_id -> summary_ids

        # Flow analysis
        self._conversation_flows: Dict[str, ConversationFlow] = {}

        # Content analysis patterns
        self.topic_patterns = {
            'bokföring': re.compile(r'\b(faktura|kvitto|moms|bokföring|kund|leverantör|betalning)\b', re.IGNORECASE),
            'media': re.compile(r'\b(bild|foto|video|ljud|fil|dokument|media)\b', re.IGNORECASE),
            'teknik': re.compile(r'\b(system|fel|problem|installation|konfiguration|databas|server)\b', re.IGNORECASE),
            'frågor': re.compile(r'\b(vad|hur|varför|vem|när|vilken|vilket)\b', re.IGNORECASE),
            'uppgifter': re.compile(r'\b(skapa|gör|utför|ändra|uppdatera|ta bort|radera)\b', re.IGNORECASE)
        }

        logger.info("SummarizedMemory initialized")

    async def process_conversation_chunk(self, conversation_id: str,
                                       messages: List[Dict[str, Any]]) -> Optional[str]:
        """
        Process a chunk of conversation messages and create/update summary if needed.

        Args:
            conversation_id: Conversation identifier
            messages: List of conversation messages

        Returns:
            Summary ID if created/updated, None otherwise
        """
        try:
            # Check if summarization is needed
            if len(messages) < self.auto_summarize_threshold:
                return None

            # Analyze conversation content
            analysis = await self._analyze_conversation_content(messages)

            # Determine if summary should be created/updated
            should_summarize = (
                analysis['importance_score'] > 0.6 or
                len(messages) >= self.auto_summarize_threshold * 2 or
                analysis['has_action_items'] or
                analysis['conversation_complete']
            )

            if not should_summarize:
                return None

            # Create or update summary
            summary_id = await self._create_or_update_summary(conversation_id, messages, analysis)

            # Update conversation flow
            await self._update_conversation_flow(conversation_id, messages, analysis)

            logger.debug(f"Processed conversation chunk for {conversation_id}, summary: {summary_id}")
            return summary_id

        except Exception as e:
            logger.error(f"Error processing conversation chunk: {e}")
            return None

    async def retrieve_relevant_memory(self, conversation_id: str,
                                     query: str,
                                     context: Optional[Dict[str, Any]] = None,
                                     limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve relevant summarized memory based on query and context.

        Args:
            conversation_id: Conversation identifier
            query: Search query
            context: Additional context for relevance scoring
            limit: Maximum number of results

        Returns:
            List of relevant memory entries
        """
        try:
            relevant_summaries = []

            # Get summaries for this conversation
            summary_ids = self._conversation_summaries.get(conversation_id, [])

            for summary_id in summary_ids:
                if summary_id in self._summaries:
                    summary = self._summaries[summary_id]

                    # Calculate relevance to query
                    relevance_score = await self._calculate_relevance(summary, query, context)

                    if relevance_score > 0.3:  # Minimum relevance threshold
                        relevant_summaries.append({
                            'summary_id': summary_id,
                            'content': summary.content_summary,
                            'mindmap': summary.mindmap,
                            'key_insights': summary.key_insights,
                            'action_items': summary.action_items,
                            'topics': summary.topics,
                            'relevance_score': relevance_score,
                            'timestamp': summary.timestamp.isoformat(),
                            'conversation_flow': summary.conversation_flow
                        })

                        # Update access statistics
                        summary.access_count += 1
                        summary.last_accessed = datetime.utcnow()

            # Sort by relevance and recency
            relevant_summaries.sort(key=lambda x: (x['relevance_score'], x['timestamp']), reverse=True)

            logger.debug(f"Retrieved {len(relevant_summaries)} relevant memories for query: {query[:50]}...")
            return relevant_summaries[:limit]

        except Exception as e:
            logger.error(f"Error retrieving relevant memory: {e}")
            return []

    async def get_conversation_overview(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get comprehensive overview of a conversation from summarized memory.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Conversation overview with summaries, flow, and insights
        """
        try:
            summary_ids = self._conversation_summaries.get(conversation_id, [])
            summaries = [self._summaries[sid] for sid in summary_ids if sid in self._summaries]

            if not summaries:
                return {'status': 'no_summary', 'conversation_id': conversation_id}

            # Sort summaries by timestamp
            summaries.sort(key=lambda s: s.timestamp)

            # Aggregate information
            overview = {
                'conversation_id': conversation_id,
                'total_summaries': len(summaries),
                'date_range': {
                    'start': summaries[0].timestamp.isoformat(),
                    'end': summaries[-1].timestamp.isoformat()
                },
                'topics': list(set(topic for s in summaries for topic in s.topics)),
                'all_key_insights': [insight for s in summaries for insight in s.key_insights],
                'pending_actions': [action for s in summaries for action in s.action_items
                                  if not self._is_action_completed(action, summaries)],
                'average_relevance': sum(s.relevance_score for s in summaries) / len(summaries),
                'conversation_flow': self._conversation_flows.get(conversation_id, ConversationFlow()).dict() if conversation_id in self._conversation_flows else None,
                'latest_summary': {
                    'content': summaries[-1].content_summary,
                    'mindmap': summaries[-1].mindmap,
                    'timestamp': summaries[-1].timestamp.isoformat()
                } if summaries else None
            }

            return overview

        except Exception as e:
            logger.error(f"Error getting conversation overview: {e}")
            return {'error': str(e)}

    async def consolidate_memories(self, conversation_id: str) -> Optional[str]:
        """
        Consolidate multiple summaries into a comprehensive overview.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Consolidated summary ID if successful
        """
        try:
            summary_ids = self._conversation_summaries.get(conversation_id, [])
            summaries = [self._summaries[sid] for sid in summary_ids if sid in self._summaries]

            if len(summaries) < 2:
                return None

            # Create consolidated content
            all_content = []
            all_insights = []
            all_actions = []
            all_topics = set()

            for summary in summaries:
                all_content.append(summary.content_summary)
                all_insights.extend(summary.key_insights)
                all_actions.extend(summary.action_items)
                all_topics.update(summary.topics)

            consolidated_content = "\n\n".join(all_content)

            # Generate new consolidated summary
            consolidated_summary = await self.summarizer.summarize(
                consolidated_content,
                {"conversation_id": conversation_id, "summary_count": len(summaries)}
            )

            # Generate consolidated mindmap
            consolidated_mindmap = await self.summarizer.generate_mindmap({
                "messages": [{"role": "assistant", "content": consolidated_content}]
            })

            # Create consolidated summary entry
            consolidated_id = f"{conversation_id}_consolidated_{int(datetime.utcnow().timestamp())}"

            consolidated_summary_obj = MemorySummary(
                conversation_id=conversation_id,
                summary_id=consolidated_id,
                content_summary=consolidated_summary or consolidated_content[:500],
                mindmap=consolidated_mindmap,
                key_insights=list(set(all_insights))[:10],  # Unique insights, max 10
                action_items=list(set(all_actions))[:5],   # Unique actions, max 5
                relevance_score=sum(s.relevance_score for s in summaries) / len(summaries),
                topics=list(all_topics),
                conversation_flow={
                    'consolidated': True,
                    'original_summaries': len(summaries),
                    'consolidation_timestamp': datetime.utcnow().isoformat()
                }
            )

            self._summaries[consolidated_id] = consolidated_summary_obj
            self._conversation_summaries[conversation_id].append(consolidated_id)

            # Remove old summaries (keep only consolidated)
            for old_id in summary_ids:
                if old_id in self._summaries and old_id != consolidated_id:
                    del self._summaries[old_id]

            self._conversation_summaries[conversation_id] = [consolidated_id]

            logger.info(f"Consolidated {len(summaries)} summaries into {consolidated_id}")
            return consolidated_id

        except Exception as e:
            logger.error(f"Error consolidating memories: {e}")
            return None

    async def _analyze_conversation_content(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze conversation content for summarization decisions."""
        try:
            # Extract text content
            text_content = " ".join(msg.get('content', '') for msg in messages)

            analysis = {
                'importance_score': 0.0,
                'has_action_items': False,
                'conversation_complete': False,
                'topics': [],
                'entities': [],
                'sentiment': 'neutral'
            }

            # Topic analysis
            for topic, pattern in self.topic_patterns.items():
                if pattern.search(text_content):
                    analysis['topics'].append(topic)
                    analysis['importance_score'] += 0.1

            # Check for action items
            action_indicators = ['skapa', 'gör', 'utför', 'ändra', 'implementera', 'fixa', 'lösa']
            analysis['has_action_items'] = any(indicator in text_content.lower() for indicator in action_indicators)
            if analysis['has_action_items']:
                analysis['importance_score'] += 0.3

            # Check conversation completion
            completion_indicators = ['klart', 'färdig', 'slutfört', 'komplett', 'done', 'finished']
            analysis['conversation_complete'] = any(indicator in text_content.lower() for indicator in completion_indicators)

            # Entity extraction (simple)
            # Look for capitalized words that might be names or important terms
            words = re.findall(r'\b[A-ZÅÄÖ][a-zåäö]+\b', text_content)
            analysis['entities'] = list(set(words))[:5]  # Max 5 entities

            # Importance based on message count and content length
            analysis['importance_score'] += min(0.3, len(messages) / 20.0)  # Max 0.3 for message count
            analysis['importance_score'] += min(0.2, len(text_content) / 1000.0)  # Max 0.2 for content length

            # Cap importance score
            analysis['importance_score'] = min(1.0, analysis['importance_score'])

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing conversation content: {e}")
            return {
                'importance_score': 0.5,
                'has_action_items': False,
                'conversation_complete': False,
                'topics': [],
                'entities': [],
                'sentiment': 'neutral'
            }

    async def _create_or_update_summary(self, conversation_id: str,
                                       messages: List[Dict[str, Any]],
                                       analysis: Dict[str, Any]) -> str:
        """Create or update a conversation summary."""
        try:
            # Convert messages to context format for summarizer
            context = {"messages": messages}

            # Generate summary
            summary_text = await self.summarizer.summarize(
                " ".join(msg.get('content', '') for msg in messages),
                context
            )

            if not summary_text:
                summary_text = f"Konversation med {len(messages)} meddelanden om {', '.join(analysis['topics'])}"

            # Generate mindmap
            mindmap = await self.summarizer.generate_mindmap(context)

            # Extract key insights and action items from mindmap
            key_insights = mindmap.get('key_insights', []) if mindmap else []
            action_items = mindmap.get('action_items', []) if mindmap else []

            # Create summary ID
            summary_id = f"{conversation_id}_summary_{int(datetime.utcnow().timestamp())}"

            # Create summary object
            summary = MemorySummary(
                conversation_id=conversation_id,
                summary_id=summary_id,
                content_summary=summary_text,
                mindmap=mindmap,
                key_insights=key_insights,
                action_items=action_items,
                relevance_score=analysis['importance_score'],
                topics=analysis['topics'],
                entities=analysis['entities']
            )

            # Store summary
            self._summaries[summary_id] = summary
            self._conversation_summaries[conversation_id].append(summary_id)

            # Keep only recent summaries (max 10 per conversation)
            if len(self._conversation_summaries[conversation_id]) > 10:
                old_summaries = self._conversation_summaries[conversation_id][:-10]
                for old_id in old_summaries:
                    if old_id in self._summaries:
                        del self._summaries[old_id]
                self._conversation_summaries[conversation_id] = self._conversation_summaries[conversation_id][-10:]

            return summary_id

        except Exception as e:
            logger.error(f"Error creating summary: {e}")
            return f"{conversation_id}_error_{int(datetime.utcnow().timestamp())}"

    async def _update_conversation_flow(self, conversation_id: str,
                                       messages: List[Dict[str, Any]],
                                       analysis: Dict[str, Any]):
        """Update conversation flow analysis."""
        try:
            if conversation_id not in self._conversation_flows:
                self._conversation_flows[conversation_id] = ConversationFlow()

            flow = self._conversation_flows[conversation_id]

            # Analyze conversation stages
            text_content = " ".join(msg.get('content', '') for msg in messages).lower()

            # Simple stage detection
            if 'problem' in text_content or 'fel' in text_content or 'issue' in text_content:
                if 'problem_identification' not in flow.stages:
                    flow.stages.append('problem_identification')
                    flow.current_stage = 'problem_identification'

            if 'lösning' in text_content or 'fix' in text_content or 'solution' in text_content:
                if 'solution_discussion' not in flow.stages:
                    flow.stages.append('solution_discussion')
                    flow.current_stage = 'solution_discussion'
                    flow.transitions.append(('problem_identification', 'solution_discussion'))

            if analysis['conversation_complete']:
                if 'completion' not in flow.stages:
                    flow.stages.append('completion')
                    flow.current_stage = 'completion'

            # Update next actions
            if analysis['has_action_items']:
                flow.next_actions.extend(analysis.get('action_items', []))

            # Remove duplicates
            flow.next_actions = list(set(flow.next_actions))

        except Exception as e:
            logger.error(f"Error updating conversation flow: {e}")

    async def _calculate_relevance(self, summary: MemorySummary, query: str,
                                  context: Optional[Dict[str, Any]] = None) -> float:
        """Calculate relevance score for a summary against a query."""
        try:
            relevance = 0.0
            query_lower = query.lower()

            # Content relevance
            if query_lower in summary.content_summary.lower():
                relevance += 0.4

            # Topic relevance
            query_topics = []
            for topic, pattern in self.topic_patterns.items():
                if pattern.search(query):
                    query_topics.append(topic)

            if any(topic in summary.topics for topic in query_topics):
                relevance += 0.3

            # Key insights relevance
            for insight in summary.key_insights:
                if query_lower in insight.lower():
                    relevance += 0.2
                    break

            # Action items relevance
            for action in summary.action_items:
                if query_lower in action.lower():
                    relevance += 0.2
                    break

            # Mindmap relevance
            if summary.mindmap:
                mindmap_text = json.dumps(summary.mindmap).lower()
                if query_lower in mindmap_text:
                    relevance += 0.1

            # Recency boost (newer summaries slightly more relevant)
            days_old = (datetime.utcnow() - summary.timestamp).days
            recency_boost = max(0, 0.1 - (days_old * 0.01))
            relevance += recency_boost

            # Access frequency boost
            access_boost = min(0.1, summary.access_count * 0.01)
            relevance += access_boost

            return min(1.0, relevance)

        except Exception as e:
            logger.error(f"Error calculating relevance: {e}")
            return 0.0

    def _is_action_completed(self, action: str, summaries: List[MemorySummary]) -> bool:
        """Check if an action item has been completed based on conversation history."""
        try:
            completion_indicators = ['klart', 'färdig', 'slutfört', 'genomfört', 'completed', 'done']

            # Check if any summary mentions completion of this action
            for summary in summaries:
                summary_text = (summary.content_summary + " " +
                              " ".join(summary.key_insights)).lower()

                if any(indicator in summary_text for indicator in completion_indicators):
                    # Simple check - could be made more sophisticated
                    if any(word in summary_text for word in action.lower().split()):
                        return True

            return False

        except Exception:
            return False

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get summarized memory statistics."""
        try:
            total_summaries = len(self._summaries)
            conversations_with_summaries = len(self._conversation_summaries)

            if total_summaries > 0:
                avg_relevance = sum(s.relevance_score for s in self._summaries.values()) / total_summaries
                total_insights = sum(len(s.key_insights) for s in self._summaries.values())
                total_actions = sum(len(s.action_items) for s in self._summaries.values())
                avg_access_count = sum(s.access_count for s in self._summaries.values()) / total_summaries
            else:
                avg_relevance = 0.0
                total_insights = 0
                total_actions = 0
                avg_access_count = 0.0

            return {
                'total_summaries': total_summaries,
                'conversations_with_summaries': conversations_with_summaries,
                'average_relevance_score': avg_relevance,
                'total_key_insights': total_insights,
                'total_action_items': total_actions,
                'average_access_count': avg_access_count,
                'topics_covered': list(set(topic for s in self._summaries.values() for topic in s.topics)),
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {'error': str(e)}

    def clear_old_summaries(self, days_old: int = 90):
        """Clear summaries older than specified days."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            removed_count = 0

            summaries_to_remove = []
            for summary_id, summary in self._summaries.items():
                if summary.timestamp < cutoff_date and summary.access_count < 5:
                    summaries_to_remove.append((summary_id, summary.conversation_id))

            for summary_id, conversation_id in summaries_to_remove:
                del self._summaries[summary_id]
                if conversation_id in self._conversation_summaries:
                    if summary_id in self._conversation_summaries[conversation_id]:
                        self._conversation_summaries[conversation_id].remove(summary_id)
                removed_count += 1

            logger.info(f"Cleared {removed_count} old summaries")
            return removed_count

        except Exception as e:
            logger.error(f"Error clearing old summaries: {e}")
            return 0