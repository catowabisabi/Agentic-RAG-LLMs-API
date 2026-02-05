# -*- coding: utf-8 -*-
"""
=============================================================================
Review Workflow - 協作審核工作流
=============================================================================

參考 Microsoft AI Agents 課程第8課 Multi-Agent 設計：
- Producer-Consumer Pattern
- Collaborative Filtering
- Quality Assurance through Review

核心概念（來自 MSFT 第8課）：
"Multiple agents contributing different perspectives. Consensus building 
through structured discussion. Democratic decision making with weighted opinions."

=============================================================================
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field

from services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ReviewDecision(str, Enum):
    """Possible review decisions"""
    APPROVE = "approve"
    NEEDS_REVISION = "needs_revision"
    REJECT = "reject"
    ESCALATE = "escalate"


class ReviewFeedback(BaseModel):
    """Feedback from a reviewer"""
    reviewer_name: str
    decision: ReviewDecision
    score: float = Field(ge=0, le=1)
    strengths: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0, le=1)


class ReviewResult(BaseModel):
    """Combined result from all reviewers"""
    final_decision: ReviewDecision
    consensus_score: float
    all_feedback: List[ReviewFeedback]
    combined_suggestions: List[str]
    requires_revision: bool
    revision_instructions: Optional[str] = None


@dataclass
class ReviewerConfig:
    """Configuration for a reviewer agent"""
    name: str
    perspective: str  # What aspect they focus on
    criteria: List[str]  # Specific criteria to evaluate
    weight: float = 1.0  # Weight in consensus calculation


class ReviewWorkflow:
    """
    Multi-agent review workflow.
    
    Implements the Producer-Consumer pattern from Microsoft's curriculum:
    1. Producer generates initial content
    2. Multiple reviewers evaluate from different perspectives
    3. Consensus is built from weighted opinions
    4. Producer refines based on feedback
    
    Use cases:
    - Quality assurance for AI responses
    - Multi-perspective validation
    - Iterative refinement
    """
    
    # Default reviewer configurations
    DEFAULT_REVIEWERS = [
        ReviewerConfig(
            name="accuracy_reviewer",
            perspective="Accuracy and Factuality",
            criteria=["Is the information correct?", "Are there any factual errors?", "Is the data up-to-date?"],
            weight=1.2
        ),
        ReviewerConfig(
            name="completeness_reviewer", 
            perspective="Completeness and Relevance",
            criteria=["Does it fully answer the question?", "Is anything missing?", "Is everything relevant?"],
            weight=1.0
        ),
        ReviewerConfig(
            name="clarity_reviewer",
            perspective="Clarity and Communication",
            criteria=["Is it easy to understand?", "Is the structure logical?", "Is the tone appropriate?"],
            weight=0.8
        )
    ]
    
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        reviewers: Optional[List[ReviewerConfig]] = None,
        consensus_threshold: float = 0.7
    ):
        """
        Initialize review workflow.
        
        Args:
            llm_service: LLM Service for review tasks
            reviewers: List of reviewer configurations
            consensus_threshold: Score threshold for approval
        """
        self.llm_service = llm_service or LLMService()
        
        self.reviewers = reviewers or self.DEFAULT_REVIEWERS
        self.consensus_threshold = consensus_threshold
        
        self._init_prompts()
        logger.info(f"ReviewWorkflow initialized with {len(self.reviewers)} reviewers")
    
    def _init_prompts(self):
        """Initialize review prompts - now stored as simple strings for llm_service"""
        self.review_system_template = """You are a {perspective} reviewer.

Your role is to evaluate the given content from your specific perspective.
Focus on these criteria:
{criteria}

Be constructive and specific. Identify both strengths and areas for improvement.

Respond in JSON format:
{{
    "decision": "approve" or "needs_revision" or "reject",
    "score": 0.85,
    "strengths": ["Specific strength 1", "Specific strength 2"],
    "issues": ["Specific issue 1"],
    "suggestions": ["Specific suggestion for improvement"],
    "confidence": 0.8
}}
"""
        
        self.refinement_system = """You are refining content based on reviewer feedback.

Apply the suggestions while maintaining the original intent and information.
Address the identified issues specifically.
Keep the strengths that were noted.

Provide the refined content directly."""
    
    async def review(
        self,
        query: str,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ReviewResult:
        """
        Run the review workflow.
        
        Args:
            query: Original user query
            content: Content to review
            context: Additional context
        
        Returns:
            ReviewResult with combined feedback
        """
        import json
        import asyncio
        
        # Collect feedback from all reviewers
        feedback_tasks = [
            self._get_review(reviewer, query, content)
            for reviewer in self.reviewers
        ]
        
        all_feedback = await asyncio.gather(*feedback_tasks)
        
        # Calculate consensus
        total_weight = sum(r.weight for r in self.reviewers)
        weighted_score = sum(
            f.score * r.weight 
            for f, r in zip(all_feedback, self.reviewers)
        ) / total_weight
        
        # Determine final decision
        approve_count = sum(1 for f in all_feedback if f.decision == ReviewDecision.APPROVE)
        reject_count = sum(1 for f in all_feedback if f.decision == ReviewDecision.REJECT)
        
        if reject_count > 0:
            final_decision = ReviewDecision.REJECT
        elif weighted_score >= self.consensus_threshold and approve_count >= len(self.reviewers) // 2:
            final_decision = ReviewDecision.APPROVE
        else:
            final_decision = ReviewDecision.NEEDS_REVISION
        
        # Combine suggestions
        all_issues = []
        all_suggestions = []
        for f in all_feedback:
            all_issues.extend(f.issues)
            all_suggestions.extend(f.suggestions)
        
        # Build revision instructions if needed
        revision_instructions = None
        if final_decision == ReviewDecision.NEEDS_REVISION:
            revision_instructions = self._build_revision_instructions(all_feedback)
        
        result = ReviewResult(
            final_decision=final_decision,
            consensus_score=weighted_score,
            all_feedback=all_feedback,
            combined_suggestions=list(set(all_suggestions)),
            requires_revision=final_decision == ReviewDecision.NEEDS_REVISION,
            revision_instructions=revision_instructions
        )
        
        logger.info(f"Review complete: {final_decision.value} (score: {weighted_score:.2f})")
        return result
    
    async def review_and_refine(
        self,
        query: str,
        content: str,
        max_iterations: int = 2
    ) -> Dict[str, Any]:
        """
        Review and iteratively refine content.
        
        Args:
            query: Original query
            content: Initial content
            max_iterations: Maximum refinement iterations
        
        Returns:
            Dict with final content and review history
        """
        current_content = content
        history = []
        
        for iteration in range(max_iterations):
            # Review
            review_result = await self.review(query, current_content)
            history.append({
                "iteration": iteration + 1,
                "decision": review_result.final_decision.value,
                "score": review_result.consensus_score,
                "issues": [i for f in review_result.all_feedback for i in f.issues]
            })
            
            # Check if approved
            if review_result.final_decision == ReviewDecision.APPROVE:
                logger.info(f"Content approved after {iteration + 1} iteration(s)")
                return {
                    "content": current_content,
                    "approved": True,
                    "iterations": iteration + 1,
                    "final_score": review_result.consensus_score,
                    "history": history
                }
            
            # Check if rejected
            if review_result.final_decision == ReviewDecision.REJECT:
                logger.warning("Content rejected by reviewers")
                return {
                    "content": current_content,
                    "approved": False,
                    "iterations": iteration + 1,
                    "final_score": review_result.consensus_score,
                    "rejection_reason": review_result.combined_suggestions,
                    "history": history
                }
            
            # Refine
            current_content = await self._refine_content(
                query=query,
                content=current_content,
                review_result=review_result
            )
        
        # Max iterations reached
        logger.warning(f"Max iterations ({max_iterations}) reached")
        final_review = await self.review(query, current_content)
        
        return {
            "content": current_content,
            "approved": final_review.final_decision == ReviewDecision.APPROVE,
            "iterations": max_iterations,
            "final_score": final_review.consensus_score,
            "history": history
        }
    
    async def _get_review(
        self,
        reviewer: ReviewerConfig,
        query: str,
        content: str
    ) -> ReviewFeedback:
        """Get review from a single reviewer"""
        import json
        
        criteria_text = "\n".join([f"- {c}" for c in reviewer.criteria])
        
        system_message = self.review_system_template.format(
            perspective=reviewer.perspective,
            criteria=criteria_text
        )
        
        prompt = f"""Review this content:

**Original Query:**
{query[:300]}

**Content to Review:**
{content[:2000]}

Provide your review from the {reviewer.perspective} perspective."""
        
        try:
            result = await self.llm_service.generate(
                prompt=prompt,
                system_message=system_message,
                temperature=0.2
            )
            review_data = json.loads(result.content)
            
            return ReviewFeedback(
                reviewer_name=reviewer.name,
                decision=ReviewDecision(review_data.get("decision", "needs_revision")),
                score=review_data.get("score", 0.5),
                strengths=review_data.get("strengths", []),
                issues=review_data.get("issues", []),
                suggestions=review_data.get("suggestions", []),
                confidence=review_data.get("confidence", 0.8)
            )
            
        except Exception as e:
            logger.error(f"Review failed for {reviewer.name}: {e}")
            return ReviewFeedback(
                reviewer_name=reviewer.name,
                decision=ReviewDecision.NEEDS_REVISION,
                score=0.5,
                issues=["Review process failed"],
                confidence=0.3
            )
    
    async def _refine_content(
        self,
        query: str,
        content: str,
        review_result: ReviewResult
    ) -> str:
        """Refine content based on review feedback"""
        # Compile feedback
        feedback_text = "\n".join([
            f"**{f.reviewer_name}** ({f.decision.value}, {f.score:.1f}):\n"
            f"  Issues: {', '.join(f.issues)}\n"
            f"  Suggestions: {', '.join(f.suggestions)}"
            for f in review_result.all_feedback
        ])
        
        issues_text = "\n".join([f"- {i}" for i in review_result.combined_suggestions[:5]])
        suggestions_text = "\n".join([
            f"- {s}" for f in review_result.all_feedback for s in f.suggestions[:2]
        ])
        
        prompt = f"""Refine this content:

**Original Query:**
{query[:300]}

**Original Content:**
{content[:2000]}

**Reviewer Feedback:**
{feedback_text}

**Key Issues to Address:**
{issues_text}

**Specific Suggestions:**
{suggestions_text}

Provide the refined content."""
        
        try:
            result = await self.llm_service.generate(
                prompt=prompt,
                system_message=self.refinement_system,
                temperature=0.3
            )
            return result.content
            
        except Exception as e:
            logger.error(f"Refinement failed: {e}")
            return content  # Return original if refinement fails
    
    def _build_revision_instructions(self, feedback: List[ReviewFeedback]) -> str:
        """Build clear revision instructions from feedback"""
        instructions = ["Please revise the content to address:"]
        
        for f in feedback:
            if f.issues:
                instructions.append(f"\n**{f.reviewer_name}:**")
                for issue in f.issues[:3]:
                    instructions.append(f"  - {issue}")
        
        return "\n".join(instructions)


class QuickReview:
    """
    Simplified review for fast validation.
    
    Single-pass review without iteration.
    Use for quick quality checks.
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None, threshold: float = 0.6):
        self.llm_service = llm_service or LLMService()
        self.threshold = threshold
        
        self.system_prompt = """Quickly evaluate this response. Score 0-1 for quality.
Consider: accuracy, completeness, clarity, relevance.
Respond with just a JSON: {"score": 0.8, "pass": true, "issue": "optional issue"}"""
    
    async def check(self, query: str, response: str) -> Dict[str, Any]:
        """Quick quality check"""
        import json
        
        try:
            prompt = f"Query: {query[:200]}\nResponse: {response[:500]}"
            result = await self.llm_service.generate(
                prompt=prompt,
                system_message=self.system_prompt,
                temperature=0.1
            )
            data = json.loads(result.content)
            
            return {
                "score": data.get("score", 0.5),
                "passed": data.get("pass", data.get("score", 0.5) >= self.threshold),
                "issue": data.get("issue")
            }
            
        except Exception as e:
            logger.warning(f"Quick review failed: {e}")
            return {"score": 0.5, "passed": True, "issue": None}
