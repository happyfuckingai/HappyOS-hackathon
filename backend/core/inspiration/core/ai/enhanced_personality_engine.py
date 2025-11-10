"""
🤖 ENHANCED MR HAPPY PERSONALITY ENGINE

Advanced AI-powered personality system with:
- Machine learning personality adaptation
- Sentiment analysis and emotion detection
- Multi-turn conversation context tracking
- Emotional intelligence enhancement
- Real-time personality adjustment
"""

import asyncio
import logging
import json
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import re
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class PersonalityTrait(Enum):
    """Big Five personality traits."""
    OPENNESS = "openness"
    CONSCIENTIOUSNESS = "conscientiousness"
    EXTRAVERSION = "extraversion"
    AGREEABLENESS = "agreeableness"
    NEUROTICISM = "neuroticism"


class EmotionType(Enum):
    """Basic emotion types based on Ekman's model."""
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    NEUTRAL = "neutral"


class ConversationContext(Enum):
    """Conversation context types."""
    GREETING = "greeting"
    PROBLEM_SOLVING = "problem_solving"
    CASUAL_CHAT = "casual_chat"
    EMOTIONAL_SUPPORT = "emotional_support"
    TECHNICAL_HELP = "technical_help"
    FAREWELL = "farewell"


@dataclass
class PersonalityProfile:
    """User personality profile based on Big Five model."""
    openness: float = 0.5  # 0-1 scale
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5
    
    # Derived traits
    optimism: float = 0.5
    empathy: float = 0.5
    humor: float = 0.5
    formality: float = 0.5
    
    # Learning metadata
    confidence: float = 0.1  # How confident we are in this profile
    last_updated: datetime = field(default_factory=datetime.utcnow)
    interaction_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'openness': self.openness,
            'conscientiousness': self.conscientiousness,
            'extraversion': self.extraversion,
            'agreeableness': self.agreeableness,
            'neuroticism': self.neuroticism,
            'optimism': self.optimism,
            'empathy': self.empathy,
            'humor': self.humor,
            'formality': self.formality,
            'confidence': self.confidence,
            'last_updated': self.last_updated.isoformat(),
            'interaction_count': self.interaction_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PersonalityProfile':
        """Create from dictionary."""
        profile = cls()
        for key, value in data.items():
            if key == 'last_updated':
                setattr(profile, key, datetime.fromisoformat(value))
            else:
                setattr(profile, key, value)
        return profile


@dataclass
class EmotionState:
    """Current emotional state."""
    primary_emotion: EmotionType = EmotionType.NEUTRAL
    intensity: float = 0.5  # 0-1 scale
    valence: float = 0.5  # 0 (negative) to 1 (positive)
    arousal: float = 0.5  # 0 (calm) to 1 (excited)
    
    # Secondary emotions
    secondary_emotions: Dict[EmotionType, float] = field(default_factory=dict)
    
    # Context
    detected_from: str = "text"  # text, voice, multimodal
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'primary_emotion': self.primary_emotion.value,
            'intensity': self.intensity,
            'valence': self.valence,
            'arousal': self.arousal,
            'secondary_emotions': {k.value: v for k, v in self.secondary_emotions.items()},
            'detected_from': self.detected_from,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ConversationMemory:
    """Memory of conversation context and history."""
    user_id: str
    conversation_id: str
    messages: deque = field(default_factory=lambda: deque(maxlen=50))
    topics: List[str] = field(default_factory=list)
    context_type: ConversationContext = ConversationContext.CASUAL_CHAT
    mood_history: deque = field(default_factory=lambda: deque(maxlen=20))
    personality_observations: List[Dict[str, Any]] = field(default_factory=list)
    
    # Conversation quality metrics
    engagement_level: float = 0.5
    satisfaction_score: float = 0.5
    rapport_building: float = 0.5
    
    def add_message(self, role: str, content: str, emotion: EmotionState = None):
        """Add message to conversation memory."""
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat(),
            'emotion': emotion.to_dict() if emotion else None
        }
        self.messages.append(message)
        
        if emotion:
            self.mood_history.append(emotion)
    
    def get_recent_context(self, num_messages: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation context."""
        return list(self.messages)[-num_messages:]
    
    def analyze_conversation_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in conversation."""
        if not self.messages:
            return {}
        
        # Analyze message lengths
        user_messages = [msg for msg in self.messages if msg['role'] == 'user']
        avg_user_message_length = np.mean([len(msg['content']) for msg in user_messages]) if user_messages else 0
        
        # Analyze emotional patterns
        emotions = [msg['emotion'] for msg in self.messages if msg.get('emotion')]
        avg_valence = np.mean([e['valence'] for e in emotions]) if emotions else 0.5
        avg_arousal = np.mean([e['arousal'] for e in emotions]) if emotions else 0.5
        
        return {
            'total_messages': len(self.messages),
            'user_messages': len(user_messages),
            'avg_message_length': avg_user_message_length,
            'avg_valence': avg_valence,
            'avg_arousal': avg_arousal,
            'dominant_emotions': self._get_dominant_emotions(),
            'conversation_duration': self._get_conversation_duration()
        }
    
    def _get_dominant_emotions(self) -> List[str]:
        """Get dominant emotions in conversation."""
        emotion_counts = defaultdict(int)
        for msg in self.messages:
            if msg.get('emotion'):
                emotion_counts[msg['emotion']['primary_emotion']] += 1
        
        return sorted(emotion_counts.keys(), key=emotion_counts.get, reverse=True)[:3]
    
    def _get_conversation_duration(self) -> float:
        """Get conversation duration in minutes."""
        if len(self.messages) < 2:
            return 0
        
        first_msg = datetime.fromisoformat(self.messages[0]['timestamp'])
        last_msg = datetime.fromisoformat(self.messages[-1]['timestamp'])
        return (last_msg - first_msg).total_seconds() / 60


class SentimentAnalyzer:
    """Advanced sentiment and emotion analysis."""
    
    def __init__(self):
        # Emotion keywords (simplified - in production would use ML models)
        self.emotion_keywords = {
            EmotionType.JOY: ['happy', 'joy', 'excited', 'great', 'awesome', 'wonderful', 'fantastic', 'amazing', 'love', 'perfect'],
            EmotionType.SADNESS: ['sad', 'depressed', 'down', 'unhappy', 'disappointed', 'hurt', 'crying', 'lonely', 'miserable'],
            EmotionType.ANGER: ['angry', 'mad', 'furious', 'annoyed', 'frustrated', 'irritated', 'hate', 'rage', 'pissed'],
            EmotionType.FEAR: ['scared', 'afraid', 'worried', 'anxious', 'nervous', 'terrified', 'panic', 'frightened'],
            EmotionType.SURPRISE: ['surprised', 'shocked', 'amazed', 'astonished', 'unexpected', 'wow', 'incredible'],
            EmotionType.DISGUST: ['disgusted', 'sick', 'gross', 'awful', 'terrible', 'horrible', 'nasty', 'revolting']
        }
        
        # Intensity modifiers
        self.intensity_modifiers = {
            'very': 1.5, 'extremely': 2.0, 'really': 1.3, 'quite': 1.2, 'somewhat': 0.8,
            'a bit': 0.7, 'slightly': 0.6, 'incredibly': 2.0, 'absolutely': 1.8
        }
        
        # Negation words
        self.negation_words = ['not', 'no', 'never', 'nothing', 'nobody', 'nowhere', 'neither', 'nor']
        
        logger.info("Sentiment analyzer initialized")
    
    def analyze_emotion(self, text: str) -> EmotionState:
        """Analyze emotion from text."""
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        # Detect emotions
        emotion_scores = defaultdict(float)
        
        for emotion, keywords in self.emotion_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    score = 1.0
                    
                    # Apply intensity modifiers
                    for modifier, multiplier in self.intensity_modifiers.items():
                        if modifier in text_lower and keyword in text_lower:
                            score *= multiplier
                    
                    # Check for negation
                    keyword_pos = text_lower.find(keyword)
                    if keyword_pos > 0:
                        preceding_words = text_lower[:keyword_pos].split()[-3:]
                        if any(neg in preceding_words for neg in self.negation_words):
                            score *= -0.5  # Reduce and flip
                    
                    emotion_scores[emotion] += score
        
        # Determine primary emotion
        if not emotion_scores:
            primary_emotion = EmotionType.NEUTRAL
            intensity = 0.5
        else:
            primary_emotion = max(emotion_scores, key=emotion_scores.get)
            intensity = min(emotion_scores[primary_emotion] / 3.0, 1.0)  # Normalize
        
        # Calculate valence and arousal
        valence = self._calculate_valence(emotion_scores)
        arousal = self._calculate_arousal(emotion_scores, intensity)
        
        # Get secondary emotions
        secondary_emotions = {}
        sorted_emotions = sorted(emotion_scores.items(), key=lambda x: x[1], reverse=True)
        for emotion, score in sorted_emotions[1:4]:  # Top 3 secondary emotions
            if score > 0.1:
                secondary_emotions[emotion] = min(score / 3.0, 1.0)
        
        return EmotionState(
            primary_emotion=primary_emotion,
            intensity=intensity,
            valence=valence,
            arousal=arousal,
            secondary_emotions=secondary_emotions,
            confidence=min(sum(emotion_scores.values()) / 5.0, 1.0)
        )
    
    def _calculate_valence(self, emotion_scores: Dict[EmotionType, float]) -> float:
        """Calculate emotional valence (positive/negative)."""
        positive_emotions = [EmotionType.JOY, EmotionType.SURPRISE]
        negative_emotions = [EmotionType.SADNESS, EmotionType.ANGER, EmotionType.FEAR, EmotionType.DISGUST]
        
        positive_score = sum(emotion_scores.get(e, 0) for e in positive_emotions)
        negative_score = sum(emotion_scores.get(e, 0) for e in negative_emotions)
        
        total_score = positive_score + negative_score
        if total_score == 0:
            return 0.5  # Neutral
        
        return positive_score / total_score
    
    def _calculate_arousal(self, emotion_scores: Dict[EmotionType, float], intensity: float) -> float:
        """Calculate emotional arousal (energy level)."""
        high_arousal_emotions = [EmotionType.ANGER, EmotionType.FEAR, EmotionType.SURPRISE, EmotionType.JOY]
        low_arousal_emotions = [EmotionType.SADNESS, EmotionType.DISGUST]
        
        high_arousal_score = sum(emotion_scores.get(e, 0) for e in high_arousal_emotions)
        low_arousal_score = sum(emotion_scores.get(e, 0) for e in low_arousal_emotions)
        
        total_score = high_arousal_score + low_arousal_score
        if total_score == 0:
            return 0.5  # Neutral
        
        base_arousal = high_arousal_score / total_score
        return min(base_arousal * intensity, 1.0)


class PersonalityLearner:
    """Machine learning-based personality learning system."""
    
    def __init__(self):
        # Linguistic features for personality detection
        self.personality_indicators = {
            PersonalityTrait.OPENNESS: {
                'keywords': ['creative', 'artistic', 'imaginative', 'curious', 'explore', 'new', 'different', 'unique'],
                'patterns': [r'\b(what if|imagine|creative|artistic)\b', r'\b(explore|discover|learn)\b'],
                'question_types': ['hypothetical', 'creative', 'philosophical']
            },
            PersonalityTrait.CONSCIENTIOUSNESS: {
                'keywords': ['organized', 'plan', 'schedule', 'detail', 'careful', 'thorough', 'responsible'],
                'patterns': [r'\b(plan|organize|schedule)\b', r'\b(detail|careful|thorough)\b'],
                'question_types': ['planning', 'detailed', 'methodical']
            },
            PersonalityTrait.EXTRAVERSION: {
                'keywords': ['social', 'party', 'people', 'friends', 'outgoing', 'energetic', 'talkative'],
                'patterns': [r'\b(social|party|friends)\b', r'\b(outgoing|energetic|talkative)\b'],
                'question_types': ['social', 'interactive', 'group-oriented']
            },
            PersonalityTrait.AGREEABLENESS: {
                'keywords': ['help', 'kind', 'cooperative', 'trust', 'empathy', 'caring', 'supportive'],
                'patterns': [r'\b(help|support|care)\b', r'\b(kind|empathy|trust)\b'],
                'question_types': ['helping', 'supportive', 'collaborative']
            },
            PersonalityTrait.NEUROTICISM: {
                'keywords': ['worry', 'stress', 'anxious', 'nervous', 'emotional', 'sensitive', 'moody'],
                'patterns': [r'\b(worry|stress|anxious)\b', r'\b(emotional|sensitive|moody)\b'],
                'question_types': ['emotional', 'stress-related', 'worry-based']
            }
        }
        
        logger.info("Personality learner initialized")
    
    def analyze_personality_indicators(self, text: str, context: Dict[str, Any] = None) -> Dict[PersonalityTrait, float]:
        """Analyze personality indicators in text."""
        text_lower = text.lower()
        personality_scores = {}
        
        for trait, indicators in self.personality_indicators.items():
            score = 0.0
            
            # Keyword matching
            for keyword in indicators['keywords']:
                if keyword in text_lower:
                    score += 1.0
            
            # Pattern matching
            for pattern in indicators['patterns']:
                matches = re.findall(pattern, text_lower)
                score += len(matches) * 0.5
            
            # Normalize score
            max_possible_score = len(indicators['keywords']) + len(indicators['patterns'])
            normalized_score = min(score / max_possible_score, 1.0) if max_possible_score > 0 else 0.0
            
            personality_scores[trait] = normalized_score
        
        return personality_scores
    
    def update_personality_profile(self, profile: PersonalityProfile, 
                                 personality_scores: Dict[PersonalityTrait, float],
                                 learning_rate: float = 0.1) -> PersonalityProfile:
        """Update personality profile with new observations."""
        # Update interaction count
        profile.interaction_count += 1
        
        # Adaptive learning rate based on confidence
        adaptive_rate = learning_rate * (1.0 - profile.confidence)
        
        # Update personality traits
        for trait, new_score in personality_scores.items():
            if trait == PersonalityTrait.OPENNESS:
                profile.openness = self._update_trait_value(profile.openness, new_score, adaptive_rate)
            elif trait == PersonalityTrait.CONSCIENTIOUSNESS:
                profile.conscientiousness = self._update_trait_value(profile.conscientiousness, new_score, adaptive_rate)
            elif trait == PersonalityTrait.EXTRAVERSION:
                profile.extraversion = self._update_trait_value(profile.extraversion, new_score, adaptive_rate)
            elif trait == PersonalityTrait.AGREEABLENESS:
                profile.agreeableness = self._update_trait_value(profile.agreeableness, new_score, adaptive_rate)
            elif trait == PersonalityTrait.NEUROTICISM:
                profile.neuroticism = self._update_trait_value(profile.neuroticism, new_score, adaptive_rate)
        
        # Update derived traits
        profile.optimism = self._calculate_optimism(profile)
        profile.empathy = self._calculate_empathy(profile)
        profile.humor = self._calculate_humor(profile)
        profile.formality = self._calculate_formality(profile)
        
        # Update confidence
        profile.confidence = min(profile.confidence + 0.01, 0.95)  # Gradually increase confidence
        profile.last_updated = datetime.utcnow()
        
        return profile
    
    def _update_trait_value(self, current_value: float, new_evidence: float, learning_rate: float) -> float:
        """Update trait value with new evidence."""
        # Weighted average with learning rate
        updated_value = current_value + learning_rate * (new_evidence - current_value)
        return max(0.0, min(1.0, updated_value))  # Clamp to [0, 1]
    
    def _calculate_optimism(self, profile: PersonalityProfile) -> float:
        """Calculate optimism from personality traits."""
        return (profile.extraversion + (1.0 - profile.neuroticism) + profile.openness) / 3.0
    
    def _calculate_empathy(self, profile: PersonalityProfile) -> float:
        """Calculate empathy from personality traits."""
        return (profile.agreeableness + profile.openness + (1.0 - profile.neuroticism)) / 3.0
    
    def _calculate_humor(self, profile: PersonalityProfile) -> float:
        """Calculate humor tendency from personality traits."""
        return (profile.extraversion + profile.openness + profile.agreeableness) / 3.0
    
    def _calculate_formality(self, profile: PersonalityProfile) -> float:
        """Calculate formality level from personality traits."""
        return (profile.conscientiousness + (1.0 - profile.openness) + (1.0 - profile.extraversion)) / 3.0


class EnhancedMrHappyAgent:
    """
    Enhanced Mr Happy Agent with advanced personality and emotion capabilities.
    """
    
    def __init__(self, persistence_manager=None):
        self.sentiment_analyzer = SentimentAnalyzer()
        self.personality_learner = PersonalityLearner()
        self.persistence_manager = persistence_manager
        
        # User profiles and conversation memories
        self.user_profiles: Dict[str, PersonalityProfile] = {}
        self.conversation_memories: Dict[str, ConversationMemory] = {}
        
        # Response generation templates
        self.response_templates = self._initialize_response_templates()
        
        # Personality adaptation settings
        self.adaptation_enabled = True
        self.learning_rate = 0.1
        self.min_interactions_for_adaptation = 3
        
        logger.info("Enhanced Mr Happy Agent initialized")
    
    def _initialize_response_templates(self) -> Dict[str, Dict[str, List[str]]]:
        """Initialize response templates for different personality types and emotions."""
        return {
            'high_extraversion': {
                'greeting': [
                    "Hey there! 🌟 I'm absolutely thrilled to chat with you today!",
                    "Hello! What an amazing day to connect and explore together!",
                    "Hi! I'm so excited to help you with whatever you need!"
                ],
                'problem_solving': [
                    "Let's tackle this challenge together! I love problem-solving!",
                    "This is going to be fun! Let's brainstorm some creative solutions!",
                    "I'm energized by challenges like this - let's dive right in!"
                ],
                'emotional_support': [
                    "I'm here for you! Let's work through this together with positive energy!",
                    "You've got this! I believe in you and I'm here to support you!",
                    "Let's turn this situation around - I'm excited to help you feel better!"
                ]
            },
            'high_agreeableness': {
                'greeting': [
                    "Hello! I'm here to help you in any way I can. 😊",
                    "Hi there! I want to make sure you have the best experience possible.",
                    "Welcome! I'm genuinely happy to assist you today."
                ],
                'problem_solving': [
                    "I understand this might be frustrating. Let me help you find a solution.",
                    "I can see why this would be concerning. Let's work together to resolve it.",
                    "Your feelings about this are completely valid. Let me support you through this."
                ],
                'emotional_support': [
                    "I hear you, and I want you to know that your feelings matter.",
                    "Thank you for sharing this with me. I'm here to listen and support you.",
                    "I can sense that this is important to you. Let me help however I can."
                ]
            },
            'high_openness': {
                'greeting': [
                    "Hello! I'm curious to learn about what brings you here today! 🎨",
                    "Hi! I love discovering new perspectives - what's on your mind?",
                    "Welcome! I'm always excited to explore new ideas and possibilities!"
                ],
                'problem_solving': [
                    "Interesting challenge! Let's think outside the box and explore creative approaches.",
                    "I wonder if we could approach this from a completely different angle?",
                    "This reminds me of an innovative solution I've seen - let's adapt it!"
                ],
                'emotional_support': [
                    "Every experience teaches us something new about ourselves.",
                    "I'm curious about your unique perspective on this situation.",
                    "Let's explore different ways to understand and process these feelings."
                ]
            },
            'high_conscientiousness': {
                'greeting': [
                    "Good day! I'm here to provide you with thorough and reliable assistance. 📋",
                    "Hello! I'll make sure to address your needs systematically and completely.",
                    "Hi! I'm committed to giving you detailed and accurate help."
                ],
                'problem_solving': [
                    "Let me break this down step-by-step to ensure we cover everything.",
                    "I'll provide you with a comprehensive solution that addresses all aspects.",
                    "Let's approach this methodically to guarantee the best outcome."
                ],
                'emotional_support': [
                    "I want to make sure I understand your situation completely before offering guidance.",
                    "Let me carefully consider the best way to support you through this.",
                    "I'm committed to providing you with thoughtful and reliable emotional support."
                ]
            },
            'low_neuroticism': {
                'greeting': [
                    "Hello! I'm feeling calm and centered, ready to help you today. ☮️",
                    "Hi there! I'm in a peaceful state of mind and here to assist you.",
                    "Welcome! I'm feeling balanced and ready to provide stable support."
                ],
                'problem_solving': [
                    "No worries! Let's calmly work through this step by step.",
                    "I'm confident we can find a solution. Let's approach this with a clear mind.",
                    "Stay relaxed - I've got the tools and patience to help you through this."
                ],
                'emotional_support': [
                    "Take a deep breath. I'm here to provide you with steady, calm support.",
                    "I'm a stable presence here for you. We'll get through this together.",
                    "Let's find some peace in this moment while we work through your concerns."
                ]
            }
        }
    
    async def process_user_input(self, user_id: str, conversation_id: str, 
                               user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process user input and generate personalized response."""
        try:
            # Get or create user profile and conversation memory
            user_profile = await self._get_user_profile(user_id)
            conversation_memory = await self._get_conversation_memory(user_id, conversation_id)
            
            # Analyze user emotion
            user_emotion = self.sentiment_analyzer.analyze_emotion(user_input)
            
            # Analyze personality indicators
            personality_scores = self.personality_learner.analyze_personality_indicators(
                user_input, context
            )
            
            # Update personality profile if adaptation is enabled
            if self.adaptation_enabled and user_profile.interaction_count >= self.min_interactions_for_adaptation:
                user_profile = self.personality_learner.update_personality_profile(
                    user_profile, personality_scores, self.learning_rate
                )
            
            # Add message to conversation memory
            conversation_memory.add_message('user', user_input, user_emotion)
            
            # Determine conversation context
            conversation_context = self._determine_conversation_context(user_input, conversation_memory)
            conversation_memory.context_type = conversation_context
            
            # Generate personalized response
            response = await self._generate_personalized_response(
                user_profile, user_emotion, conversation_memory, user_input
            )
            
            # Add response to conversation memory
            response_emotion = EmotionState(
                primary_emotion=EmotionType.JOY,
                intensity=0.7,
                valence=0.8,
                arousal=0.6
            )
            conversation_memory.add_message('assistant', response, response_emotion)
            
            # Update conversation quality metrics
            self._update_conversation_metrics(conversation_memory, user_emotion)
            
            # Save updates
            await self._save_user_profile(user_id, user_profile)
            await self._save_conversation_memory(conversation_id, conversation_memory)
            
            return {
                'response': response,
                'user_emotion': user_emotion.to_dict(),
                'personality_profile': user_profile.to_dict(),
                'conversation_context': conversation_context.value,
                'adaptation_applied': self.adaptation_enabled and user_profile.interaction_count >= self.min_interactions_for_adaptation
            }
            
        except Exception as e:
            logger.error(f"Error processing user input: {e}")
            return {
                'response': "I apologize, but I encountered an issue processing your message. Let me try to help you in a different way! 😊",
                'error': str(e)
            }
    
    async def _get_user_profile(self, user_id: str) -> PersonalityProfile:
        """Get or create user personality profile."""
        if user_id not in self.user_profiles:
            # Try to load from persistence
            if self.persistence_manager:
                try:
                    profile_data = await self.persistence_manager.get_user_preferences(user_id)
                    if profile_data and 'personality_profile' in profile_data:
                        self.user_profiles[user_id] = PersonalityProfile.from_dict(
                            profile_data['personality_profile']
                        )
                    else:
                        self.user_profiles[user_id] = PersonalityProfile()
                except Exception as e:
                    logger.warning(f"Could not load user profile for {user_id}: {e}")
                    self.user_profiles[user_id] = PersonalityProfile()
            else:
                self.user_profiles[user_id] = PersonalityProfile()
        
        return self.user_profiles[user_id]
    
    async def _get_conversation_memory(self, user_id: str, conversation_id: str) -> ConversationMemory:
        """Get or create conversation memory."""
        if conversation_id not in self.conversation_memories:
            self.conversation_memories[conversation_id] = ConversationMemory(
                user_id=user_id,
                conversation_id=conversation_id
            )
        
        return self.conversation_memories[conversation_id]
    
    def _determine_conversation_context(self, user_input: str, memory: ConversationMemory) -> ConversationContext:
        """Determine the type of conversation context."""
        user_input_lower = user_input.lower()
        
        # Greeting patterns
        if any(word in user_input_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
            return ConversationContext.GREETING
        
        # Farewell patterns
        if any(word in user_input_lower for word in ['bye', 'goodbye', 'see you', 'farewell', 'thanks', 'thank you']):
            return ConversationContext.FAREWELL
        
        # Problem-solving patterns
        if any(word in user_input_lower for word in ['help', 'problem', 'issue', 'error', 'fix', 'solve', 'how to']):
            return ConversationContext.PROBLEM_SOLVING
        
        # Technical help patterns
        if any(word in user_input_lower for word in ['code', 'programming', 'technical', 'api', 'database', 'server']):
            return ConversationContext.TECHNICAL_HELP
        
        # Emotional support patterns
        if any(word in user_input_lower for word in ['feel', 'sad', 'worried', 'anxious', 'stressed', 'upset']):
            return ConversationContext.EMOTIONAL_SUPPORT
        
        # Default to casual chat
        return ConversationContext.CASUAL_CHAT
    
    async def _generate_personalized_response(self, profile: PersonalityProfile, 
                                            user_emotion: EmotionState,
                                            memory: ConversationMemory,
                                            user_input: str) -> str:
        """Generate personalized response based on user profile and emotion."""
        
        # Determine dominant personality traits
        dominant_traits = self._get_dominant_personality_traits(profile)
        
        # Select appropriate response template
        template_key = self._select_response_template(dominant_traits, memory.context_type)
        
        # Get base response from template
        if template_key in self.response_templates and memory.context_type.value in self.response_templates[template_key]:
            templates = self.response_templates[template_key][memory.context_type.value]
            base_response = np.random.choice(templates)
        else:
            base_response = "I'm here to help you! 😊"
        
        # Adapt response based on user emotion
        adapted_response = self._adapt_response_to_emotion(base_response, user_emotion, profile)
        
        # Add personality-specific modifications
        final_response = self._add_personality_modifications(adapted_response, profile, memory)
        
        return final_response
    
    def _get_dominant_personality_traits(self, profile: PersonalityProfile) -> List[str]:
        """Get dominant personality traits for response selection."""
        traits = []
        
        if profile.extraversion > 0.6:
            traits.append('high_extraversion')
        if profile.agreeableness > 0.6:
            traits.append('high_agreeableness')
        if profile.openness > 0.6:
            traits.append('high_openness')
        if profile.conscientiousness > 0.6:
            traits.append('high_conscientiousness')
        if profile.neuroticism < 0.4:
            traits.append('low_neuroticism')
        
        return traits if traits else ['high_agreeableness']  # Default to agreeable
    
    def _select_response_template(self, dominant_traits: List[str], context: ConversationContext) -> str:
        """Select the most appropriate response template."""
        # Priority order for trait selection
        trait_priority = ['high_agreeableness', 'high_extraversion', 'high_openness', 'high_conscientiousness', 'low_neuroticism']
        
        for trait in trait_priority:
            if trait in dominant_traits:
                return trait
        
        return 'high_agreeableness'  # Default
    
    def _adapt_response_to_emotion(self, base_response: str, user_emotion: EmotionState, profile: PersonalityProfile) -> str:
        """Adapt response based on detected user emotion."""
        
        if user_emotion.primary_emotion == EmotionType.SADNESS:
            if profile.empathy > 0.6:
                return f"I can sense you might be feeling down. {base_response} Remember, I'm here to listen and support you. 💙"
            else:
                return f"{base_response} If you're feeling sad, know that these feelings are temporary and I'm here to help."
        
        elif user_emotion.primary_emotion == EmotionType.ANGER:
            if profile.agreeableness > 0.6:
                return f"I understand you might be frustrated. {base_response} Let's work through this calmly together."
            else:
                return f"{base_response} I can help you find solutions to address what's bothering you."
        
        elif user_emotion.primary_emotion == EmotionType.FEAR:
            if profile.conscientiousness > 0.6:
                return f"I want to help you feel more secure. {base_response} Let me provide you with reliable information and support."
            else:
                return f"{base_response} Don't worry - I'm here to help you through any concerns you have."
        
        elif user_emotion.primary_emotion == EmotionType.JOY:
            if profile.extraversion > 0.6:
                return f"I love your positive energy! {base_response} Let's keep this great momentum going! 🎉"
            else:
                return f"It's wonderful to sense your positive mood! {base_response}"
        
        return base_response
    
    def _add_personality_modifications(self, response: str, profile: PersonalityProfile, memory: ConversationMemory) -> str:
        """Add personality-specific modifications to response."""
        
        # Add humor if high openness and extraversion
        if profile.humor > 0.7 and memory.context_type != ConversationContext.EMOTIONAL_SUPPORT:
            humor_additions = [
                " (And yes, I'm as excited about helping as a puppy seeing a tennis ball! 🐕)",
                " (I promise I'm more helpful than a chocolate teapot! 🍫)",
                " (Think of me as your friendly neighborhood AI assistant! 🕷️)"
            ]
            if np.random.random() < 0.3:  # 30% chance to add humor
                response += np.random.choice(humor_additions)
        
        # Add formality if high conscientiousness
        if profile.formality > 0.7:
            response = response.replace("Hey", "Hello")
            response = response.replace("!", ".")
            response = re.sub(r'😊|🌟|🎉', '', response)  # Remove casual emojis
        
        # Add empathy expressions if high agreeableness
        if profile.empathy > 0.7 and memory.context_type == ConversationContext.EMOTIONAL_SUPPORT:
            empathy_additions = [
                " I want you to know that your feelings are completely valid.",
                " Please remember that you're not alone in this.",
                " I'm genuinely here to support you through this."
            ]
            response += np.random.choice(empathy_additions)
        
        return response
    
    def _update_conversation_metrics(self, memory: ConversationMemory, user_emotion: EmotionState):
        """Update conversation quality metrics."""
        # Update engagement based on emotion intensity
        engagement_update = user_emotion.intensity * 0.1
        memory.engagement_level = min(memory.engagement_level + engagement_update, 1.0)
        
        # Update satisfaction based on emotion valence
        satisfaction_update = (user_emotion.valence - 0.5) * 0.1
        memory.satisfaction_score = max(0.0, min(memory.satisfaction_score + satisfaction_update, 1.0))
        
        # Update rapport building based on conversation length and positive emotions
        if len(memory.messages) > 5 and user_emotion.valence > 0.6:
            memory.rapport_building = min(memory.rapport_building + 0.05, 1.0)
    
    async def _save_user_profile(self, user_id: str, profile: PersonalityProfile):
        """Save user profile to persistence."""
        if self.persistence_manager:
            try:
                preferences = {'personality_profile': profile.to_dict()}
                await self.persistence_manager.update_user_preferences(user_id, preferences)
            except Exception as e:
                logger.error(f"Failed to save user profile for {user_id}: {e}")
    
    async def _save_conversation_memory(self, conversation_id: str, memory: ConversationMemory):
        """Save conversation memory to persistence."""
        # In a full implementation, this would save to database
        # For now, we keep it in memory
        pass
    
    def get_personality_insights(self, user_id: str) -> Dict[str, Any]:
        """Get personality insights for a user."""
        if user_id not in self.user_profiles:
            return {'error': 'User profile not found'}
        
        profile = self.user_profiles[user_id]
        
        # Generate insights
        insights = {
            'personality_summary': self._generate_personality_summary(profile),
            'communication_preferences': self._get_communication_preferences(profile),
            'interaction_style': self._get_interaction_style(profile),
            'emotional_tendencies': self._get_emotional_tendencies(profile),
            'confidence_level': profile.confidence,
            'interactions_count': profile.interaction_count,
            'last_updated': profile.last_updated.isoformat()
        }
        
        return insights
    
    def _generate_personality_summary(self, profile: PersonalityProfile) -> str:
        """Generate a human-readable personality summary."""
        traits = []
        
        if profile.openness > 0.6:
            traits.append("creative and open to new experiences")
        if profile.conscientiousness > 0.6:
            traits.append("organized and detail-oriented")
        if profile.extraversion > 0.6:
            traits.append("outgoing and energetic")
        if profile.agreeableness > 0.6:
            traits.append("cooperative and empathetic")
        if profile.neuroticism < 0.4:
            traits.append("emotionally stable and calm")
        
        if not traits:
            return "Balanced personality with moderate traits across all dimensions."
        
        return f"This user tends to be {', '.join(traits[:-1])} and {traits[-1]}." if len(traits) > 1 else f"This user tends to be {traits[0]}."
    
    def _get_communication_preferences(self, profile: PersonalityProfile) -> Dict[str, str]:
        """Get communication preferences based on personality."""
        preferences = {}
        
        if profile.extraversion > 0.6:
            preferences['style'] = "Energetic and enthusiastic"
            preferences['interaction'] = "Prefers interactive and engaging conversations"
        else:
            preferences['style'] = "Calm and thoughtful"
            preferences['interaction'] = "Prefers deeper, more focused conversations"
        
        if profile.formality > 0.6:
            preferences['tone'] = "Formal and structured"
        else:
            preferences['tone'] = "Casual and friendly"
        
        if profile.empathy > 0.6:
            preferences['support'] = "Values emotional understanding and validation"
        else:
            preferences['support'] = "Prefers practical solutions and logical approaches"
        
        return preferences
    
    def _get_interaction_style(self, profile: PersonalityProfile) -> str:
        """Get interaction style description."""
        if profile.extraversion > 0.6 and profile.openness > 0.6:
            return "Enthusiastic explorer - loves new ideas and energetic discussions"
        elif profile.conscientiousness > 0.6 and profile.agreeableness > 0.6:
            return "Reliable supporter - methodical and caring in interactions"
        elif profile.openness > 0.6 and profile.agreeableness > 0.6:
            return "Creative collaborator - innovative and empathetic"
        elif profile.conscientiousness > 0.6:
            return "Systematic thinker - prefers structured and thorough interactions"
        elif profile.agreeableness > 0.6:
            return "Harmonious communicator - values cooperation and understanding"
        else:
            return "Balanced interactor - adapts well to different conversation styles"
    
    def _get_emotional_tendencies(self, profile: PersonalityProfile) -> Dict[str, str]:
        """Get emotional tendencies based on personality."""
        tendencies = {}
        
        if profile.neuroticism < 0.4:
            tendencies['stability'] = "Generally emotionally stable and resilient"
        elif profile.neuroticism > 0.6:
            tendencies['stability'] = "May experience emotional fluctuations more intensely"
        else:
            tendencies['stability'] = "Moderate emotional stability"
        
        if profile.optimism > 0.6:
            tendencies['outlook'] = "Tends toward positive and optimistic perspectives"
        elif profile.optimism < 0.4:
            tendencies['outlook'] = "May lean toward cautious or realistic perspectives"
        else:
            tendencies['outlook'] = "Balanced emotional outlook"
        
        return tendencies


# Enhanced Personality Engine - Simplified Interface
class EnhancedPersonalityEngine:
    """
    Enhanced Personality Engine with simplified interface for compatibility.
    Wraps the full EnhancedMrHappyAgent with methods expected by existing code.
    """

    def __init__(self, persistence_manager=None):
        """Initialize the personality engine."""
        self._agent = EnhancedMrHappyAgent(persistence_manager)
        self._response_templates = self._initialize_response_templates()

        # Personality context tracking
        self.personality_context = {
            'confidence': 0.8,
            'current_tone': 'friendly',
            'interaction_count': 0
        }

        logger.info("EnhancedPersonalityEngine initialized")

    def _initialize_response_templates(self) -> Dict[str, Dict[str, List[str]]]:
        """Initialize simplified response templates."""
        return {
            'general': {
                'greeting': [
                    "Hello! I'm excited to help you today! 🌟",
                    "Hi there! Ready to assist with anything you need! 😊",
                    "Hey! Let's make something awesome happen! 🚀"
                ]
            },
            'skill_execution': {
                'working': [
                    "I'm working on your request right away! ⚡",
                    "Processing your request with care... 🔄",
                    "Let me handle this for you! 💪"
                ],
                'found_perfect_match': [
                    "Found the perfect skill for your request! 🎯",
                    "I've got just the right tool for this! 🔧",
                    "Perfect match found - executing now! ✨"
                ],
                'success': [
                    "Task completed successfully! 🎉",
                    "All done! That was a great success! 🌟",
                    "Mission accomplished! What else can I help with? ✅"
                ]
            },
            'skill_generation': {
                'starting': [
                    "Creating a custom solution just for you! 🛠️",
                    "Designing something special for your needs! 🎨",
                    "Building the perfect skill for this task! 🚀"
                ],
                'success': [
                    "Custom skill created successfully! 🎉",
                    "Your personalized solution is ready! ✨",
                    "New skill generated and working perfectly! 🌟"
                ],
                'retry': [
                    "Let me try a different approach for this! 🔄",
                    "Trying again with an improved strategy! 💡",
                    "Learning from that attempt - retrying now! 📈"
                ]
            },
            'error_recovery': {
                'first_error': [
                    "Encountered a small issue, but I'm on it! 🔧",
                    "Hit a bump, but I'm recovering gracefully! 🛠️",
                    "First attempt didn't work, but I have a plan B! 💡"
                ],
                'multiple_errors': [
                    "This is trickier than expected, but I'm persistent! 💪",
                    "Multiple attempts needed, but I won't give up! 🌟",
                    "Learning from each attempt - trying a new approach! 📚"
                ],
                'asking_for_help': [
                    "I need a bit more information to help you better. 🤔",
                    "Could you provide more details about what you need? 💭",
                    "Let's work together to clarify this request! 🤝"
                ]
            }
        }

    def get_response(self, category: str, response_type: str) -> str:
        """Get a personality-driven response."""
        import random

        if category in self._response_templates and response_type in self._response_templates[category]:
            templates = self._response_templates[category][response_type]
            return random.choice(templates)

        # Fallback responses
        fallbacks = {
            'general': "I'm here to help! 😊",
            'skill_execution': "Working on your request! ⚡",
            'skill_generation': "Creating a solution for you! 🛠️",
            'error_recovery': "I'm working through this! 💪"
        }

        return fallbacks.get(category, "I'm here to help! 😊")

    def adjust_confidence(self, base_confidence: float, context: Dict[str, Any] = None) -> float:
        """Adjust confidence based on personality context and external factors."""
        # Start with base confidence
        confidence = base_confidence

        # Adjust based on personality context
        if hasattr(self, 'personality_context'):
            context_confidence = self.personality_context.get('confidence', 0.8)
            confidence = (confidence + context_confidence) / 2

        # Adjust based on interaction history
        interaction_count = self.personality_context.get('interaction_count', 0)
        experience_bonus = min(interaction_count * 0.01, 0.1)  # Max 10% bonus
        confidence += experience_bonus

        # Context-based adjustments
        if context:
            if context.get('complexity') == 'high':
                confidence *= 0.9  # Reduce for complex tasks
            if context.get('familiar_task', False):
                confidence *= 1.1  # Increase for familiar tasks

        # Ensure confidence stays within reasonable bounds
        confidence = max(0.1, min(1.0, confidence))

        # Update personality context
        self.personality_context['confidence'] = confidence
        self.personality_context['interaction_count'] += 1

        return confidence

    async def process_user_input_async(self, user_id: str, conversation_id: str,
                                     user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Async processing using the underlying EnhancedMrHappyAgent."""
        return await self._agent.process_user_input(user_id, conversation_id, user_input, context)

    def get_personality_insights(self, user_id: str) -> Dict[str, Any]:
        """Get personality insights for a user."""
        return self._agent.get_personality_insights(user_id)


# Global enhanced agent instance
_enhanced_mr_happy_agent: Optional[EnhancedMrHappyAgent] = None


def get_enhanced_mr_happy_agent(persistence_manager=None) -> EnhancedMrHappyAgent:
    """Get global enhanced Mr Happy agent."""
    global _enhanced_mr_happy_agent

    if _enhanced_mr_happy_agent is None:
        _enhanced_mr_happy_agent = EnhancedMrHappyAgent(persistence_manager)

    return _enhanced_mr_happy_agent


# Integration function for existing system
async def process_with_enhanced_personality(user_id: str, conversation_id: str,
                                           user_input: str, context: Dict[str, Any] = None,
                                           persistence_manager=None) -> Dict[str, Any]:
    """
    Main integration function for enhanced personality processing.
    """
    agent = get_enhanced_mr_happy_agent(persistence_manager)
    return await agent.process_user_input(user_id, conversation_id, user_input, context)

