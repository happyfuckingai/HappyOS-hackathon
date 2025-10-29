"""
Pattern Analysis Module

Detects patterns in meeting data using vector similarity and AI analysis.
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from backend.services.ai.memory_insights.models import Pattern, PatternType
from backend.services.ai.client_manager import AIClientManager
from backend.services.storage.vector_service import ProductionVectorService

logger = logging.getLogger(__name__)


class PatternAnalyzer:
    """Analyzes meeting data to detect patterns"""
    
    def __init__(self, ai_client: Optional[AIClientManager] = None,
                 vector_service: Optional[ProductionVectorService] = None):
        self.ai_client = ai_client
        self.vector_service = vector_service
        
        # Pattern detection thresholds
        self.thresholds = {
            "min_frequency": 2,
            "min_confidence": 0.6,
            "similarity_threshold": 0.8
        }
    
    async def analyze_patterns(self, meeting_data: List[Dict[str, Any]]) -> List[Pattern]:
        """
        Analyze meeting data to detect patterns
        
        Args:
            meeting_data: List of meeting data dictionaries
            
        Returns:
            List of detected patterns
        """
        if not meeting_data:
            return []
        
        patterns = []
        
        try:
            # Detect different types of patterns
            topic_patterns = await self._detect_topic_patterns(meeting_data)
            patterns.extend(topic_patterns)
            
            frequency_patterns = await self._detect_frequency_patterns(meeting_data)
            patterns.extend(frequency_patterns)
            
            behavior_patterns = await self._detect_behavior_patterns(meeting_data)
            patterns.extend(behavior_patterns)
            
            decision_patterns = await self._detect_decision_patterns(meeting_data)
            patterns.extend(decision_patterns)
            
            # Filter by confidence threshold
            filtered_patterns = [
                p for p in patterns 
                if p.confidence >= self.thresholds["min_confidence"]
            ]
            
            logger.info(f"Detected {len(filtered_patterns)} patterns from {len(meeting_data)} meetings")
            return filtered_patterns
            
        except Exception as e:
            logger.error(f"Failed to analyze patterns: {e}")
            return []
    
    async def _detect_topic_patterns(self, meeting_data: List[Dict[str, Any]]) -> List[Pattern]:
        """Detect recurring topic patterns using vector similarity"""
        patterns = []
        
        try:
            if not self.vector_service:
                return patterns
            
            # Group content by similarity
            topic_clusters = await self._cluster_topics_by_similarity(meeting_data)
            
            for cluster_id, cluster_data in topic_clusters.items():
                if len(cluster_data["meetings"]) >= self.thresholds["min_frequency"]:
                    pattern = Pattern(
                        pattern_id=f"topic_{cluster_id}",
                        pattern_type=PatternType.RECURRING_TOPIC,
                        description=f"Recurring topic: {cluster_data['topic_name']}",
                        confidence=cluster_data["confidence"],
                        frequency=len(cluster_data["meetings"]),
                        first_occurrence=min(m["created_at"] for m in cluster_data["meetings"]),
                        last_occurrence=max(m["created_at"] for m in cluster_data["meetings"]),
                        related_meetings=[m["meeting_id"] for m in cluster_data["meetings"]],
                        metadata={
                            "topic_keywords": cluster_data.get("keywords", []),
                            "avg_similarity": cluster_data.get("avg_similarity", 0.0)
                        }
                    )
                    patterns.append(pattern)
            
        except Exception as e:
            logger.error(f"Failed to detect topic patterns: {e}")
        
        return patterns
    
    async def _cluster_topics_by_similarity(self, meeting_data: List[Dict[str, Any]]) -> Dict[str, Dict]:
        """Cluster meeting topics by semantic similarity"""
        clusters = {}
        
        try:
            # Extract all content embeddings
            all_content = []
            for meeting in meeting_data:
                for content in meeting.get("content_embeddings", []):
                    embedding = await self.vector_service.generate_embedding(content["content"])
                    all_content.append({
                        "meeting_id": meeting["meeting_id"],
                        "meeting_name": meeting["name"],
                        "created_at": meeting["created_at"],
                        "content": content["content"],
                        "embedding": embedding
                    })
            
            if not all_content:
                return clusters
            
            # Simple clustering based on similarity threshold
            cluster_id = 0
            used_indices = set()
            
            for i, item1 in enumerate(all_content):
                if i in used_indices:
                    continue
                
                cluster_items = [item1]
                used_indices.add(i)
                
                for j, item2 in enumerate(all_content[i+1:], i+1):
                    if j in used_indices:
                        continue
                    
                    # Calculate similarity
                    similarity = self._cosine_similarity(item1["embedding"], item2["embedding"])
                    
                    if similarity >= self.thresholds["similarity_threshold"]:
                        cluster_items.append(item2)
                        used_indices.add(j)
                
                if len(cluster_items) >= self.thresholds["min_frequency"]:
                    # Generate topic name using AI
                    topic_name = await self._generate_topic_name(cluster_items)
                    
                    clusters[f"cluster_{cluster_id}"] = {
                        "topic_name": topic_name,
                        "meetings": [{"meeting_id": item["meeting_id"], "created_at": item["created_at"]} for item in cluster_items],
                        "confidence": min(1.0, len(cluster_items) / 10.0),
                        "keywords": self._extract_keywords(cluster_items),
                        "avg_similarity": np.mean([
                            self._cosine_similarity(cluster_items[0]["embedding"], item["embedding"])
                            for item in cluster_items[1:]
                        ]) if len(cluster_items) > 1 else 1.0
                    }
                    cluster_id += 1
            
        except Exception as e:
            logger.error(f"Failed to cluster topics: {e}")
        
        return clusters
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            vec1_np = np.array(vec1)
            vec2_np = np.array(vec2)
            
            dot_product = np.dot(vec1_np, vec2_np)
            norm1 = np.linalg.norm(vec1_np)
            norm2 = np.linalg.norm(vec2_np)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
            
        except Exception:
            return 0.0
    
    async def _generate_topic_name(self, cluster_items: List[Dict]) -> str:
        """Generate a topic name for a cluster using AI"""
        try:
            if not self.ai_client:
                return "Recurring Topic"
            
            # Combine content from cluster items
            combined_content = " ".join([item["content"][:200] for item in cluster_items[:5]])
            
            # Use AI to generate topic name
            result = await self.ai_client.summarize_meeting(
                content=f"Generate a short topic name (2-4 words) for this recurring theme: {combined_content}",
                meeting_id="topic_analysis",
                user_id="system",
                style="brief"
            )
            
            topic_name = result.get("summary", "Recurring Topic")[:50]
            return topic_name.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate topic name: {e}")
            return "Recurring Topic"
    
    def _extract_keywords(self, cluster_items: List[Dict]) -> List[str]:
        """Extract keywords from cluster content"""
        try:
            # Simple keyword extraction
            all_words = []
            for item in cluster_items:
                words = item["content"].lower().split()
                all_words.extend([w for w in words if len(w) > 3])
            
            # Count word frequency
            word_counts = {}
            for word in all_words:
                word_counts[word] = word_counts.get(word, 0) + 1
            
            # Return top keywords
            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
            return [word for word, count in sorted_words[:10] if count > 1]
            
        except Exception:
            return []
    
    async def _detect_frequency_patterns(self, meeting_data: List[Dict[str, Any]]) -> List[Pattern]:
        """Detect meeting frequency patterns"""
        patterns = []
        
        try:
            if len(meeting_data) < 3:
                return patterns
            
            # Sort meetings by date
            sorted_meetings = sorted(meeting_data, key=lambda x: x["created_at"])
            
            # Calculate intervals between meetings
            intervals = []
            for i in range(1, len(sorted_meetings)):
                interval = (sorted_meetings[i]["created_at"] - sorted_meetings[i-1]["created_at"]).days
                intervals.append(interval)
            
            if intervals:
                avg_interval = np.mean(intervals)
                std_interval = np.std(intervals)
                
                # Detect regular meeting pattern
                if std_interval < avg_interval * 0.3:  # Low variance indicates regularity
                    pattern = Pattern(
                        pattern_id="frequency_regular",
                        pattern_type=PatternType.MEETING_FREQUENCY,
                        description=f"Regular meeting pattern (every ~{avg_interval:.1f} days)",
                        confidence=max(0.5, 1.0 - (std_interval / avg_interval)),
                        frequency=len(meeting_data),
                        first_occurrence=sorted_meetings[0]["created_at"],
                        last_occurrence=sorted_meetings[-1]["created_at"],
                        related_meetings=[m["meeting_id"] for m in meeting_data],
                        metadata={
                            "avg_interval_days": avg_interval,
                            "std_interval_days": std_interval,
                            "regularity_score": 1.0 - (std_interval / avg_interval)
                        }
                    )
                    patterns.append(pattern)
            
        except Exception as e:
            logger.error(f"Failed to detect frequency patterns: {e}")
        
        return patterns
    
    async def _detect_behavior_patterns(self, meeting_data: List[Dict[str, Any]]) -> List[Pattern]:
        """Detect participant behavior patterns"""
        patterns = []
        
        try:
            # Analyze participant consistency
            all_participants = set()
            meeting_participants = {}
            
            for meeting in meeting_data:
                participants = set(meeting.get("participants", []))
                all_participants.update(participants)
                meeting_participants[meeting["meeting_id"]] = participants
            
            if len(all_participants) > 1:
                # Find core participants (appear in most meetings)
                participant_frequency = {}
                for participant in all_participants:
                    frequency = sum(1 for participants in meeting_participants.values() 
                                  if participant in participants)
                    participant_frequency[participant] = frequency
                
                core_participants = [
                    p for p, freq in participant_frequency.items() 
                    if freq >= len(meeting_data) * 0.7  # Appear in 70% of meetings
                ]
                
                if core_participants:
                    pattern = Pattern(
                        pattern_id="behavior_core_team",
                        pattern_type=PatternType.PARTICIPANT_BEHAVIOR,
                        description=f"Core team of {len(core_participants)} consistent participants",
                        confidence=len(core_participants) / len(all_participants),
                        frequency=len(meeting_data),
                        first_occurrence=min(m["created_at"] for m in meeting_data),
                        last_occurrence=max(m["created_at"] for m in meeting_data),
                        related_meetings=[m["meeting_id"] for m in meeting_data],
                        metadata={
                            "core_participants": core_participants,
                            "total_participants": len(all_participants),
                            "consistency_rate": len(core_participants) / len(all_participants)
                        }
                    )
                    patterns.append(pattern)
            
        except Exception as e:
            logger.error(f"Failed to detect behavior patterns: {e}")
        
        return patterns
    
    async def _detect_decision_patterns(self, meeting_data: List[Dict[str, Any]]) -> List[Pattern]:
        """Detect decision-making patterns using AI analysis"""
        patterns = []
        
        try:
            if not self.ai_client or len(meeting_data) < 2:
                return patterns
            
            # Analyze decision-making content
            decision_content = []
            for meeting in meeting_data:
                for content in meeting.get("content_embeddings", []):
                    if any(keyword in content["content"].lower() 
                          for keyword in ["decision", "decide", "agreed", "resolved", "action"]):
                        decision_content.append({
                            "meeting_id": meeting["meeting_id"],
                            "content": content["content"],
                            "created_at": meeting["created_at"]
                        })
            
            if len(decision_content) >= 2:
                # Use AI to analyze decision patterns
                combined_decisions = "\n".join([
                    f"Meeting {item['meeting_id']}: {item['content'][:200]}"
                    for item in decision_content[:10]
                ])
                
                result = await self.ai_client.analyze_personas(
                    content=f"Analyze decision-making patterns in these meetings: {combined_decisions}",
                    meeting_id="decision_analysis",
                    user_id="system"
                )
                
                if result.get("personas"):
                    pattern = Pattern(
                        pattern_id="decision_pattern",
                        pattern_type=PatternType.DECISION_PATTERN,
                        description="Consistent decision-making approach detected",
                        confidence=0.7,
                        frequency=len(decision_content),
                        first_occurrence=min(item["created_at"] for item in decision_content),
                        last_occurrence=max(item["created_at"] for item in decision_content),
                        related_meetings=list(set(item["meeting_id"] for item in decision_content)),
                        metadata={
                            "decision_count": len(decision_content),
                            "ai_analysis": result
                        }
                    )
                    patterns.append(pattern)
            
        except Exception as e:
            logger.error(f"Failed to detect decision patterns: {e}")
        
        return patterns