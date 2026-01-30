# -*- coding: utf-8 -*-
"""
=============================================================================
Group Chat - 群組討論協作
=============================================================================

參考 Microsoft AI Agents 課程第8課 Multi-Agent 設計：
- Group Chat Pattern
- Multiple agents discussing together
- Consensus building

核心概念（來自 MSFT 第8課）：
"This pattern is useful when you want to create a group chat application 
where multiple agents can communicate with each other. Typical use cases 
include team collaboration, customer support, and social networking."

=============================================================================
"""

import logging
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    """Roles in group chat"""
    MODERATOR = "moderator"
    PARTICIPANT = "participant"
    OBSERVER = "observer"


class ChatMessage(BaseModel):
    """A message in the group chat"""
    sender: str
    role: MessageRole
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DiscussionResult(BaseModel):
    """Result of a group discussion"""
    topic: str
    conclusion: str
    key_points: List[str]
    participants: List[str]
    message_count: int
    consensus_reached: bool
    dissenting_views: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)


@dataclass
class ParticipantConfig:
    """Configuration for a group chat participant"""
    name: str
    role: MessageRole
    expertise: str
    personality: str
    speaking_style: str = "professional"
    priority: int = 1  # Higher = speaks earlier


class GroupChat:
    """
    Multi-agent group chat for collaborative problem solving.
    
    Features:
    - Multiple perspectives on a topic
    - Moderated discussion
    - Consensus building
    - Summary generation
    
    Based on Microsoft's Group Chat pattern.
    """
    
    # Default participants for general discussions
    DEFAULT_PARTICIPANTS = [
        ParticipantConfig(
            name="analyst",
            role=MessageRole.PARTICIPANT,
            expertise="Data analysis and logical reasoning",
            personality="Analytical, detail-oriented",
            priority=2
        ),
        ParticipantConfig(
            name="creative",
            role=MessageRole.PARTICIPANT,
            expertise="Creative problem solving and alternatives",
            personality="Innovative, open-minded",
            priority=1
        ),
        ParticipantConfig(
            name="critic",
            role=MessageRole.PARTICIPANT,
            expertise="Critical evaluation and risk assessment",
            personality="Skeptical, thorough",
            priority=3
        )
    ]
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        participants: Optional[List[ParticipantConfig]] = None,
        max_rounds: int = 3
    ):
        """
        Initialize group chat.
        
        Args:
            llm: LLM for all participants
            participants: List of participant configurations
            max_rounds: Maximum discussion rounds
        """
        if llm is None:
            from config.config import Config
            config = Config()
            self.llm = ChatOpenAI(
                model=config.DEFAULT_MODEL,
                temperature=0.7,  # Higher for diversity
                api_key=config.OPENAI_API_KEY,
                max_tokens=500
            )
        else:
            self.llm = llm
        
        self.participants = participants or self.DEFAULT_PARTICIPANTS
        self.max_rounds = max_rounds
        
        # Sort by priority
        self.participants.sort(key=lambda x: x.priority, reverse=True)
        
        self._init_prompts()
        logger.info(f"GroupChat initialized with {len(self.participants)} participants")
    
    def _init_prompts(self):
        """Initialize prompts for participants"""
        self.participant_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are {name}, an expert in {expertise}.

Your personality: {personality}
Speaking style: {speaking_style}

You are participating in a group discussion about the topic below.
Contribute your perspective based on your expertise.
Be constructive and engage with other participants' points.
Keep your response focused and concise (2-4 sentences).

Do NOT repeat what others have said. Add new value."""),
            ("human", """Topic: {topic}

Discussion so far:
{history}

Share your perspective on this topic, considering what others have said.""")
        ])
        
        self.moderator_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the discussion moderator.

Your job is to:
1. Guide the discussion productively
2. Identify when consensus is reached
3. Highlight key disagreements
4. Summarize conclusions

Keep the discussion on track and ensure all perspectives are heard."""),
            ("human", """Topic: {topic}

Full discussion:
{history}

Analyze this discussion and provide:
1. Whether consensus was reached
2. Key points of agreement
3. Key points of disagreement
4. Recommended conclusion
5. Action items (if any)

Respond in JSON format:
{{
    "consensus_reached": true/false,
    "conclusion": "Main conclusion",
    "key_points": ["point1", "point2"],
    "dissenting_views": ["view1"],
    "action_items": ["action1"]
}}""")
        ])
    
    async def discuss(
        self,
        topic: str,
        context: Optional[str] = None,
        initial_position: Optional[str] = None
    ) -> DiscussionResult:
        """
        Run a group discussion on a topic.
        
        Args:
            topic: Topic to discuss
            context: Additional context
            initial_position: Optional initial position to discuss
        
        Returns:
            DiscussionResult with conclusions
        """
        import json
        
        messages: List[ChatMessage] = []
        
        # Add context as initial message if provided
        if context:
            messages.append(ChatMessage(
                sender="context",
                role=MessageRole.OBSERVER,
                content=f"Background: {context}"
            ))
        
        if initial_position:
            messages.append(ChatMessage(
                sender="initial",
                role=MessageRole.OBSERVER,
                content=f"Initial position: {initial_position}"
            ))
        
        # Run discussion rounds
        for round_num in range(self.max_rounds):
            logger.debug(f"Discussion round {round_num + 1}")
            
            # Each participant contributes
            for participant in self.participants:
                response = await self._get_participant_response(
                    participant=participant,
                    topic=topic,
                    history=messages
                )
                
                messages.append(ChatMessage(
                    sender=participant.name,
                    role=participant.role,
                    content=response
                ))
        
        # Moderator summarizes
        summary = await self._moderate(topic, messages)
        
        result = DiscussionResult(
            topic=topic,
            conclusion=summary.get("conclusion", "No clear conclusion"),
            key_points=summary.get("key_points", []),
            participants=[p.name for p in self.participants],
            message_count=len(messages),
            consensus_reached=summary.get("consensus_reached", False),
            dissenting_views=summary.get("dissenting_views", []),
            action_items=summary.get("action_items", [])
        )
        
        logger.info(f"Discussion complete: consensus={result.consensus_reached}")
        return result
    
    async def quick_consult(
        self,
        question: str,
        num_perspectives: int = 2
    ) -> Dict[str, str]:
        """
        Quick consultation with fewer participants.
        
        Good for getting diverse perspectives without full discussion.
        """
        perspectives = {}
        
        for participant in self.participants[:num_perspectives]:
            response = await self._get_participant_response(
                participant=participant,
                topic=question,
                history=[]
            )
            perspectives[participant.name] = response
        
        return perspectives
    
    async def _get_participant_response(
        self,
        participant: ParticipantConfig,
        topic: str,
        history: List[ChatMessage]
    ) -> str:
        """Get response from a participant"""
        # Build history text
        history_text = self._format_history(history)
        
        try:
            formatted = self.participant_prompt.format_messages(
                name=participant.name,
                expertise=participant.expertise,
                personality=participant.personality,
                speaking_style=participant.speaking_style,
                topic=topic[:500],
                history=history_text if history_text else "No discussion yet. You speak first."
            )
            
            result = await self.llm.ainvoke(formatted)
            return result.content
            
        except Exception as e:
            logger.error(f"Participant {participant.name} failed: {e}")
            return f"[{participant.name} could not respond]"
    
    async def _moderate(
        self,
        topic: str,
        messages: List[ChatMessage]
    ) -> Dict[str, Any]:
        """Moderator summarizes the discussion"""
        import json
        
        history_text = self._format_history(messages)
        
        try:
            formatted = self.moderator_prompt.format_messages(
                topic=topic[:500],
                history=history_text
            )
            
            result = await self.llm.ainvoke(formatted)
            return json.loads(result.content)
            
        except Exception as e:
            logger.error(f"Moderation failed: {e}")
            return {
                "consensus_reached": False,
                "conclusion": "Discussion inconclusive",
                "key_points": [],
                "dissenting_views": [],
                "action_items": []
            }
    
    def _format_history(self, messages: List[ChatMessage]) -> str:
        """Format message history for prompt"""
        if not messages:
            return ""
        
        lines = []
        for msg in messages[-20:]:  # Limit history
            lines.append(f"**{msg.sender}**: {msg.content}")
        
        return "\n\n".join(lines)


class ExpertPanel(GroupChat):
    """
    Specialized group chat for expert consultation.
    
    Pre-configured with domain experts for specific topics.
    """
    
    # Expert panels by domain
    PANELS = {
        "technical": [
            ParticipantConfig("architect", MessageRole.PARTICIPANT, 
                            "System architecture and design", "Systematic, thorough", priority=3),
            ParticipantConfig("developer", MessageRole.PARTICIPANT,
                            "Implementation and best practices", "Practical, detail-oriented", priority=2),
            ParticipantConfig("security", MessageRole.PARTICIPANT,
                            "Security and risk assessment", "Cautious, security-focused", priority=1)
        ],
        "business": [
            ParticipantConfig("strategist", MessageRole.PARTICIPANT,
                            "Business strategy and market analysis", "Strategic, forward-thinking", priority=3),
            ParticipantConfig("financial", MessageRole.PARTICIPANT,
                            "Financial analysis and ROI", "Analytical, numbers-focused", priority=2),
            ParticipantConfig("operations", MessageRole.PARTICIPANT,
                            "Operations and implementation", "Practical, efficiency-focused", priority=1)
        ],
        "creative": [
            ParticipantConfig("designer", MessageRole.PARTICIPANT,
                            "Design and user experience", "Creative, user-focused", priority=3),
            ParticipantConfig("writer", MessageRole.PARTICIPANT,
                            "Content and communication", "Articulate, persuasive", priority=2),
            ParticipantConfig("researcher", MessageRole.PARTICIPANT,
                            "Research and trends", "Curious, well-informed", priority=1)
        ]
    }
    
    @classmethod
    def create_panel(cls, domain: str, llm: Optional[ChatOpenAI] = None) -> 'ExpertPanel':
        """Create an expert panel for a specific domain"""
        if domain not in cls.PANELS:
            domain = "technical"  # Default
        
        return cls(
            llm=llm,
            participants=cls.PANELS[domain],
            max_rounds=2
        )
