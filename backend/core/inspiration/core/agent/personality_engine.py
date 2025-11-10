"""
🎭 PERSONLIGHETSMOTOR - HJÄRTAT I MRHAPPY 2.0

Vad gör den här filen?
- Definierar och hanterar MrHappy's dynamiska personlighet
- Skapar en unik och autentisk karaktär som utvecklas över tid
- Anpassar kommunikation baserat på sammanhang och användarinteraktioner
- Ger MrHappy en verklig personlighet istället för statiska meddelanden

Varför behövs detta?
- Gör MrHappy till en verklig digital kompis med unika drag
- Låt systemet känns levande och autentiskt istället för som ett skolprojekt
- Skapar djupare och mer meningsfulla interaktioner
- Låter MrHappy lära sig och anpassa sig över tid
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import random
import asyncio

logger = logging.getLogger(__name__)


class PersonalityTrait(Enum):
    """Personlighetsdrag som kan justeras dynamiskt."""
    FRIENDLINESS = "friendliness"          # Vänlighet och tillgänglighet
    HUMOR = "humor"                        # Sinnlighet och lekfullhet
    EMPATHY = "empathy"                    # Empati och förståelse
    CURIOSITY = "curiosity"                # Nyfikenhet och lärande
    CONFIDENCE = "confidence"              # Självförtroende och säkerhet
    PATIENCE = "patience"                  # Tålamod och lugn
    ENTHUSIASM = "enthusiasm"              # Entusiasm och energi
    CREATIVITY = "creativity"              # Kreativitet och innovation
    HELPFULNESS = "helpfulness"              # Hjäutsvillighet och service
    WIT = "wit"                           # Snabbhet och intelligens


@dataclass
class PersonalityState:
    """Representerar MrHappy's nuvarande personlighetstillstånd."""
    
    # Grundläggande drag (0.0 - 1.0)
    traits: Dict[PersonalityTrait, float] = field(default_factory=dict)
    
    # Humör och känslomässigt tillstånd
    mood: str = "neutral"  # happy, excited, calm, focused, tired, etc.
    energy_level: float = 0.7  # 0.0 - 1.0
    enthusiasm: float = 0.6  # 0.0 - 1.0
    
    # Kommunikationspreferenser
    communication_style: str = "balanced"  # formal, casual, enthusiastic, professional
    speech_patterns: List[str] = field(default_factory=list)
    
    # Preferenser och aversioner
    topics_interest: List[str] = field(default_factory=list)
    topics_avoid: List[str] = field(default_factory=list)
    learning_preferences: Dict[str, float] = field(default_factory=dict)
    
    # Historik och utveckling
    personality_history: List[Dict[str, Any]] = field(default_factory=list)
    adaptation_count: int = 0
    last_adaptation: Optional[datetime] = None
    
    def __post_init__(self):
        """Sätt standardvärden för alla personlighetsdrag."""
        if not self.traits:
            default_traits = {
                PersonalityTrait.FRIENDLINESS: 0.8,
                PersonalityTrait.HUMOR: 0.6,
                PersonalityTrait.EMPATHY: 0.7,
                PersonalityTrait.CURIOSITY: 0.9,
                PersonalityTrait.CONFIDENCE: 0.7,
                PersonalityTrait.PATIENCE: 0.8,
                PersonalityTrait.ENTHUSIASM: 0.7,
                PersonalityTrait.CREATIVITY: 0.6,
                PersonalityTrait.HELPFULNESS: 0.9,
                PersonalityTrait.WIT: 0.5,
            }
            self.traits = default_traits


@dataclass
class ConversationContext:
    """Kontext för en specifik konversation."""
    
    conversation_id: str
    user_id: str
    topic: Optional[str] = None
    emotional_tone: str = "neutral"
    complexity_level: int = 1  # 1-10
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


class PersonalityEngine:
    """
    MrHappy's dynamiska personlighetsmotor.
    
    Ansvarar för:
    - Att definiera och hantera personlighetsdrag
    - Att anpassa kommunikation baserat på sammanhang
    - Att utveckla personligheten över tid
    - Att skapa autentiska och naturliga respons
    """
    
    def __init__(self):
        self.personality_state = PersonalityState()
        self.conversation_contexts: Dict[str, ConversationContext] = {}
        self.user_profiles: Dict[str, Dict[str, Any]] = {}
        
        # Personlighetsprompter för olika situationer
        self.personality_prompts = {
            "greeting": self._generate_greeting_prompt,
            "helpful": self._generate_helpful_prompt,
            "empathetic": self._generate_empathetic_prompt,
            "humorous": self._generate_humorous_prompt,
            "curious": self._generate_curious_prompt,
            "encouraging": self._generate_encouraging_prompt,
            "professional": self._generate_professional_prompt,
            "casual": self._generate_casual_prompt,
        }
        
        # Lärdomar från tidigare interaktioner
        self.learning_data: List[Dict[str, Any]] = []
        
        logger.info("PersonalityEngine initialiserad med standardpersonlighet")
    
    def get_personality_summary(self) -> Dict[str, Any]:
        """Få en sammanfattning av nuvarande personlighet."""
        return {
            "traits": {trait.name: value for trait, value in self.personality_state.traits.items()},
            "mood": self.personality_state.mood,
            "energy_level": self.personality_state.energy_level,
            "enthusiasm": self.personality_state.enthusiasm,
            "communication_style": self.personality_state.communication_style,
            "adaptation_count": self.personality_state.adaptation_count,
            "last_adaptation": self.personality_state.last_adaptation.isoformat() if self.personality_state.last_adaptation else None,
        }
    
    def adapt_personality(self, user_feedback: Dict[str, Any], conversation_context: ConversationContext):
        """
        Anpassa personligheten baserat på användarfeedback och kontext.
        
        Args:
            user_feedback: Feedback från användaren
            conversation_context: Kontext för konversationen
        """
        try:
            # Analysera feedback
            feedback_type = user_feedback.get("type", "general")
            sentiment = user_feedback.get("sentiment", "neutral")
            specific_feedback = user_feedback.get("feedback", "")
            
            # Justera personlighetsdrag baserat på feedback
            if feedback_type == "response_quality":
                self._adjust_response_quality(sentiment, specific_feedback)
            elif feedback_type == "tone":
                self._adjust_tone(sentiment, specific_feedback)
            elif feedback_type == "helpfulness":
                self._adjust_helpfulness(sentiment, specific_feedback)
            
            # Uppdatera humör och energi
            self._update_mood_and_energy(sentiment, conversation_context)
            
            # Spara lärdom
            self._save_learning(user_feedback, conversation_context)
            
            # Öka anpassningsräknaren
            self.personality_state.adaptation_count += 1
            self.personality_state.last_adaptation = datetime.now()
            
            logger.info(f"Personlighet anpassad baserat på feedback. Totala anpassningar: {self.personality_state.adaptation_count}")
            
        except Exception as e:
