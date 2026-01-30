# -*- coding: utf-8 -*-
"""
Collaborative Module

Provides multi-agent collaboration patterns following Microsoft's design:
- Review Workflow: Producer-Consumer pattern with quality assurance
- Group Chat: Multi-perspective discussion and consensus building

Based on Microsoft AI Agents for Beginners - Lesson 8: Multi-Agent Design
"""

from .review_workflow import (
    ReviewWorkflow,
    QuickReview,
    ReviewResult,
    ReviewFeedback,
    ReviewDecision,
    ReviewerConfig
)

from .group_chat import (
    GroupChat,
    ExpertPanel,
    DiscussionResult,
    ChatMessage,
    MessageRole,
    ParticipantConfig
)

__all__ = [
    # Review Workflow
    'ReviewWorkflow',
    'QuickReview',
    'ReviewResult',
    'ReviewFeedback',
    'ReviewDecision',
    'ReviewerConfig',
    
    # Group Chat
    'GroupChat',
    'ExpertPanel',
    'DiscussionResult',
    'ChatMessage',
    'MessageRole',
    'ParticipantConfig',
]
