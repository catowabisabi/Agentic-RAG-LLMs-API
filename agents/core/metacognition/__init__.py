# -*- coding: utf-8 -*-
"""
Metacognition Module

Provides metacognitive capabilities for AI agents following Microsoft's design patterns:
- Self-Evaluation: Assess own performance
- Experience Learning: Learn from past tasks
- Strategy Adaptation: Dynamically adjust approach

Based on Microsoft AI Agents for Beginners - Lesson 9: Metacognition
"""

from .self_evaluator import (
    SelfEvaluator,
    AdaptiveEvaluator,
    EvaluationResult,
    EvaluationDimension
)

from .experience_learner import (
    ExperienceLearner,
    LearnedPattern,
    StrategyRecommendation
)

from .strategy_adapter import (
    StrategyAdapter,
    AdaptedStrategy,
    ExecutionMode
)

__all__ = [
    # Self Evaluation
    'SelfEvaluator',
    'AdaptiveEvaluator',
    'EvaluationResult',
    'EvaluationDimension',
    
    # Experience Learning
    'ExperienceLearner',
    'LearnedPattern',
    'StrategyRecommendation',
    
    # Strategy Adaptation
    'StrategyAdapter',
    'AdaptedStrategy',
    'ExecutionMode',
]
