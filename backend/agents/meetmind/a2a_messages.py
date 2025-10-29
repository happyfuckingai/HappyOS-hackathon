"""
MeetMind A2A Message Types and Handlers

Defines A2A protocol message types specific to MeetMind module
for communication with other agents and core services.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime


class MeetMindMessageType(Enum):
    """MeetMind-specific A2A message types."""
    
    # Meeting lifecycle messages
    MEETING_START_REQUEST = "meetmind_meeting_start"
    MEETING_END_REQUEST = "meetmind_meeting_end"
    MEETING_STATUS_REQUEST = "meetmind_meeting_status"
    
    # Transcript processing messages
    TRANSCRIPT_CHUNK_ADD = "meetmind_transcript_add"
    TRANSCRIPT_COMPILE_REQUEST = "meetmind_transcript_compile"
    
    # AI processing messages
    SUMMARY_GENERATION_REQUEST = "meetmind_summary_generate"
    ACTION_ITEMS_EXTRACTION_REQUEST = "meetmind_action_items_extract"
    TOPICS_DETECTION_REQUEST = "meetmind_topics_detect"
    INSIGHTS_GENERATION_REQUEST = "meetmind_insights_generate"
    
    # Real-time processing messages
    REAL_TIME_ANALYSIS_REQUEST = "meetmind_realtime_analysis"
    PARTICIPANT_ANALYSIS_REQUEST = "meetmind_participant_analysis"
    
    # Notification messages
    MEETING_STARTED_NOTIFICATION = "meetmind_meeting_started"
    MEETING_ENDED_NOTIFICATION = "meetmind_meeting_ended"
    SUMMARY_READY_NOTIFICATION = "meetmind_summary_ready"
    ACTION_ITEMS_READY_NOTIFICATION = "meetmind_action_items_ready"
    
    # Cross-module workflow messages
    FINANCIAL_COMPLIANCE_CHECK = "meetmind_financial_compliance_check"
    MEETING_FINANCIAL_ANALYSIS = "meetmind_financial_analysis"
    COMPLIANCE_VALIDATION_REQUEST = "meetmind_compliance_validation"


@dataclass
class MeetingStartMessage:
    """Message for starting a meeting."""
    meeting_id: str
    participants: List[str]
    agenda: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tenant_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "participants": self.participants,
            "agenda": self.agenda,
            "metadata": self.metadata or {},
            "tenant_id": self.tenant_id
        }


@dataclass
class TranscriptChunkMessage:
    """Message for adding transcript chunk."""
    meeting_id: str
    content: str
    speaker: Optional[str] = None
    timestamp: Optional[str] = None
    is_final: bool = False
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "content": self.content,
            "speaker": self.speaker,
            "timestamp": self.timestamp or datetime.utcnow().isoformat(),
            "is_final": self.is_final,
            "confidence": self.confidence,
            "metadata": self.metadata or {}
        }


@dataclass
class SummaryGenerationMessage:
    """Message for requesting summary generation."""
    meeting_id: str
    style: str = "executive"  # brief, detailed, executive
    include_action_items: bool = True
    include_topics: bool = True
    custom_instructions: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "style": self.style,
            "include_action_items": self.include_action_items,
            "include_topics": self.include_topics,
            "custom_instructions": self.custom_instructions
        }


@dataclass
class ActionItemsExtractionMessage:
    """Message for requesting action items extraction."""
    meeting_id: str
    focus_participants: Optional[List[str]] = None
    priority_filter: Optional[str] = None  # high, medium, low
    due_date_extraction: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "focus_participants": self.focus_participants,
            "priority_filter": self.priority_filter,
            "due_date_extraction": self.due_date_extraction
        }


@dataclass
class TopicsDetectionMessage:
    """Message for requesting topics detection."""
    meeting_id: str
    min_confidence: float = 0.7
    max_topics: int = 10
    include_subtopics: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "min_confidence": self.min_confidence,
            "max_topics": self.max_topics,
            "include_subtopics": self.include_subtopics
        }


@dataclass
class ParticipantAnalysisMessage:
    """Message for requesting participant analysis."""
    meeting_id: str
    participants: List[str]
    analysis_type: str = "engagement"  # engagement, contribution, sentiment
    include_speaking_time: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "participants": self.participants,
            "analysis_type": self.analysis_type,
            "include_speaking_time": self.include_speaking_time
        }


@dataclass
class FinancialComplianceCheckMessage:
    """Message for cross-module financial compliance check."""
    meeting_id: str
    financial_topics: List[str]
    compliance_requirements: List[str]
    regulatory_context: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "financial_topics": self.financial_topics,
            "compliance_requirements": self.compliance_requirements,
            "regulatory_context": self.regulatory_context
        }


@dataclass
class MeetingFinancialAnalysisMessage:
    """Message for meeting-driven financial analysis workflow."""
    meeting_id: str
    financial_decisions: List[Dict[str, Any]]
    risk_assessment_required: bool = True
    compliance_check_required: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "financial_decisions": self.financial_decisions,
            "risk_assessment_required": self.risk_assessment_required,
            "compliance_check_required": self.compliance_check_required
        }


class MeetMindA2AMessageFactory:
    """Factory for creating MeetMind A2A messages."""
    
    @staticmethod
    def create_meeting_start_message(meeting_id: str,
                                   participants: List[str],
                                   agenda: Optional[str] = None,
                                   metadata: Optional[Dict[str, Any]] = None,
                                   tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a meeting start message."""
        message = MeetingStartMessage(
            meeting_id=meeting_id,
            participants=participants,
            agenda=agenda,
            metadata=metadata,
            tenant_id=tenant_id
        )
        
        return {
            "message_type": MeetMindMessageType.MEETING_START_REQUEST.value,
            "data": message.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_transcript_chunk_message(meeting_id: str,
                                      content: str,
                                      speaker: Optional[str] = None,
                                      timestamp: Optional[str] = None,
                                      is_final: bool = False,
                                      confidence: Optional[float] = None,
                                      metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a transcript chunk message."""
        message = TranscriptChunkMessage(
            meeting_id=meeting_id,
            content=content,
            speaker=speaker,
            timestamp=timestamp,
            is_final=is_final,
            confidence=confidence,
            metadata=metadata
        )
        
        return {
            "message_type": MeetMindMessageType.TRANSCRIPT_CHUNK_ADD.value,
            "data": message.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_summary_generation_message(meeting_id: str,
                                        style: str = "executive",
                                        include_action_items: bool = True,
                                        include_topics: bool = True,
                                        custom_instructions: Optional[str] = None) -> Dict[str, Any]:
        """Create a summary generation message."""
        message = SummaryGenerationMessage(
            meeting_id=meeting_id,
            style=style,
            include_action_items=include_action_items,
            include_topics=include_topics,
            custom_instructions=custom_instructions
        )
        
        return {
            "message_type": MeetMindMessageType.SUMMARY_GENERATION_REQUEST.value,
            "data": message.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_action_items_extraction_message(meeting_id: str,
                                             focus_participants: Optional[List[str]] = None,
                                             priority_filter: Optional[str] = None,
                                             due_date_extraction: bool = True) -> Dict[str, Any]:
        """Create an action items extraction message."""
        message = ActionItemsExtractionMessage(
            meeting_id=meeting_id,
            focus_participants=focus_participants,
            priority_filter=priority_filter,
            due_date_extraction=due_date_extraction
        )
        
        return {
            "message_type": MeetMindMessageType.ACTION_ITEMS_EXTRACTION_REQUEST.value,
            "data": message.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_topics_detection_message(meeting_id: str,
                                      min_confidence: float = 0.7,
                                      max_topics: int = 10,
                                      include_subtopics: bool = True) -> Dict[str, Any]:
        """Create a topics detection message."""
        message = TopicsDetectionMessage(
            meeting_id=meeting_id,
            min_confidence=min_confidence,
            max_topics=max_topics,
            include_subtopics=include_subtopics
        )
        
        return {
            "message_type": MeetMindMessageType.TOPICS_DETECTION_REQUEST.value,
            "data": message.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_financial_compliance_check_message(meeting_id: str,
                                                financial_topics: List[str],
                                                compliance_requirements: List[str],
                                                regulatory_context: Optional[str] = None) -> Dict[str, Any]:
        """Create a financial compliance check message for cross-module workflow."""
        message = FinancialComplianceCheckMessage(
            meeting_id=meeting_id,
            financial_topics=financial_topics,
            compliance_requirements=compliance_requirements,
            regulatory_context=regulatory_context
        )
        
        return {
            "message_type": MeetMindMessageType.FINANCIAL_COMPLIANCE_CHECK.value,
            "data": message.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_meeting_financial_analysis_message(meeting_id: str,
                                                financial_decisions: List[Dict[str, Any]],
                                                risk_assessment_required: bool = True,
                                                compliance_check_required: bool = True) -> Dict[str, Any]:
        """Create a meeting-driven financial analysis message."""
        message = MeetingFinancialAnalysisMessage(
            meeting_id=meeting_id,
            financial_decisions=financial_decisions,
            risk_assessment_required=risk_assessment_required,
            compliance_check_required=compliance_check_required
        )
        
        return {
            "message_type": MeetMindMessageType.MEETING_FINANCIAL_ANALYSIS.value,
            "data": message.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_notification_message(notification_type: MeetMindMessageType,
                                  meeting_id: str,
                                  data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a notification message."""
        return {
            "message_type": notification_type.value,
            "data": {
                "meeting_id": meeting_id,
                **data
            },
            "timestamp": datetime.utcnow().isoformat()
        }


class MeetMindA2AMessageValidator:
    """Validator for MeetMind A2A messages."""
    
    @staticmethod
    def validate_meeting_start_message(data: Dict[str, Any]) -> bool:
        """Validate meeting start message."""
        required_fields = ["meeting_id", "participants"]
        return all(field in data for field in required_fields)
    
    @staticmethod
    def validate_transcript_chunk_message(data: Dict[str, Any]) -> bool:
        """Validate transcript chunk message."""
        required_fields = ["meeting_id", "content"]
        return all(field in data for field in required_fields)
    
    @staticmethod
    def validate_summary_generation_message(data: Dict[str, Any]) -> bool:
        """Validate summary generation message."""
        required_fields = ["meeting_id"]
        valid_styles = ["brief", "detailed", "executive"]
        
        if not all(field in data for field in required_fields):
            return False
        
        style = data.get("style", "executive")
        return style in valid_styles
    
    @staticmethod
    def validate_action_items_extraction_message(data: Dict[str, Any]) -> bool:
        """Validate action items extraction message."""
        required_fields = ["meeting_id"]
        valid_priorities = ["high", "medium", "low", None]
        
        if not all(field in data for field in required_fields):
            return False
        
        priority = data.get("priority_filter")
        return priority in valid_priorities
    
    @staticmethod
    def validate_financial_compliance_check_message(data: Dict[str, Any]) -> bool:
        """Validate financial compliance check message."""
        required_fields = ["meeting_id", "financial_topics", "compliance_requirements"]
        return all(field in data for field in required_fields)
    
    @staticmethod
    def validate_message(message_type: str, data: Dict[str, Any]) -> bool:
        """Validate any MeetMind A2A message."""
        validators = {
            MeetMindMessageType.MEETING_START_REQUEST.value: 
                MeetMindA2AMessageValidator.validate_meeting_start_message,
            MeetMindMessageType.TRANSCRIPT_CHUNK_ADD.value: 
                MeetMindA2AMessageValidator.validate_transcript_chunk_message,
            MeetMindMessageType.SUMMARY_GENERATION_REQUEST.value: 
                MeetMindA2AMessageValidator.validate_summary_generation_message,
            MeetMindMessageType.ACTION_ITEMS_EXTRACTION_REQUEST.value: 
                MeetMindA2AMessageValidator.validate_action_items_extraction_message,
            MeetMindMessageType.FINANCIAL_COMPLIANCE_CHECK.value: 
                MeetMindA2AMessageValidator.validate_financial_compliance_check_message,
        }
        
        validator = validators.get(message_type)
        if validator:
            return validator(data)
        
        # For unknown message types, just check that data is a dict
        return isinstance(data, dict)