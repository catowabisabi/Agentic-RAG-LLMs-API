"""
Translate Agent

Handles language translation:
- Multi-language translation
- Format preservation
- Context-aware translation
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    MessageProtocol,
    TaskAssignment
)
from config.config import Config

logger = logging.getLogger(__name__)


class TranslationResult(BaseModel):
    """A translation result"""
    original_text: str = Field(description="The original text")
    translated_text: str = Field(description="The translated text")
    source_language: str = Field(description="Detected or specified source language")
    target_language: str = Field(description="Target language")
    confidence: float = Field(description="Confidence in translation 0-1")


class TranslateAgent(BaseAgent):
    """
    Translate Agent for the multi-agent system.
    
    Responsibilities:
    - Translate text between languages
    - Preserve formatting and meaning
    - Handle specialized terminology
    """
    
    def __init__(self, agent_name: str = "translate_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Translation Specialist",
            agent_description="Handles language translation"
        )
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.1,
            api_key=self.config.OPENAI_API_KEY
        )
        
        # Supported languages
        self.supported_languages = [
            "English", "Chinese", "Traditional Chinese", "Simplified Chinese",
            "Japanese", "Korean", "Spanish", "French", "German", "Italian",
            "Portuguese", "Russian", "Arabic", "Hindi", "Thai", "Vietnamese"
        ]
        
        logger.info("TranslateAgent initialized")
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a translation task"""
        task_type = task.task_type
        
        if task_type == "translate":
            return await self._translate(task)
        elif task_type == "detect":
            return await self._detect_language(task)
        elif task_type == "multi_translate":
            return await self._multi_translate(task)
        elif task_type == "localize":
            return await self._localize(task)
        else:
            return await self._translate(task)
    
    async def _translate(self, task: TaskAssignment) -> Dict[str, Any]:
        """Translate text to target language"""
        text = task.input_data.get("text", task.context)
        target_language = task.input_data.get("target_language", "English")
        source_language = task.input_data.get("source_language", "auto")
        preserve_formatting = task.input_data.get("preserve_formatting", True)
        domain = task.input_data.get("domain", "general")
        
        prompt = ChatPromptTemplate.from_template(
            """Translate the following text to {target_language}.
{source_instruction}
Domain: {domain}
{formatting_instruction}

Text to translate:
{text}

Translation:"""
        )
        
        source_instruction = (
            f"Source language: {source_language}"
            if source_language != "auto"
            else "Detect the source language automatically."
        )
        
        formatting_instruction = (
            "Preserve the original formatting (paragraphs, bullet points, etc.)."
            if preserve_formatting
            else "Focus on meaning, formatting can be adjusted."
        )
        
        chain = prompt | self.llm
        
        result = await chain.ainvoke({
            "text": text,
            "target_language": target_language,
            "source_instruction": source_instruction,
            "domain": domain,
            "formatting_instruction": formatting_instruction
        })
        
        # Detect source language if auto
        if source_language == "auto":
            detected = await self._detect_language_internal(text)
            source_language = detected.get("language", "Unknown")
        
        return {
            "success": True,
            "original_text": text,
            "translated_text": result.content,
            "source_language": source_language,
            "target_language": target_language
        }
    
    async def _detect_language(self, task: TaskAssignment) -> Dict[str, Any]:
        """Detect the language of text"""
        text = task.input_data.get("text", task.context)
        return await self._detect_language_internal(text)
    
    async def _detect_language_internal(self, text: str) -> Dict[str, Any]:
        """Internal language detection"""
        prompt = ChatPromptTemplate.from_template(
            """Detect the language of the following text.
Return only the language name (e.g., "English", "Chinese", "Japanese").

Text:
{text}

Language:"""
        )
        
        chain = prompt | self.llm
        
        result = await chain.ainvoke({"text": text[:500]})  # Limit text for detection
        
        language = result.content.strip()
        
        # Check if it's in supported languages
        is_supported = any(
            lang.lower() in language.lower()
            for lang in self.supported_languages
        )
        
        return {
            "success": True,
            "language": language,
            "is_supported": is_supported
        }
    
    async def _multi_translate(self, task: TaskAssignment) -> Dict[str, Any]:
        """Translate to multiple languages"""
        text = task.input_data.get("text", task.context)
        target_languages = task.input_data.get("target_languages", ["English", "Chinese"])
        
        translations = {}
        
        for lang in target_languages:
            prompt = ChatPromptTemplate.from_template(
                """Translate the following text to {target_language}.
Provide only the translation.

Text:
{text}

Translation:"""
            )
            
            chain = prompt | self.llm
            
            result = await chain.ainvoke({
                "text": text,
                "target_language": lang
            })
            
            translations[lang] = result.content
        
        return {
            "success": True,
            "original_text": text,
            "translations": translations
        }
    
    async def _localize(self, task: TaskAssignment) -> Dict[str, Any]:
        """Localize content for a specific region"""
        text = task.input_data.get("text", task.context)
        target_locale = task.input_data.get("target_locale", "en-US")
        context = task.input_data.get("context", "general")
        
        # Parse locale
        parts = target_locale.split("-")
        language = parts[0]
        region = parts[1] if len(parts) > 1 else ""
        
        prompt = ChatPromptTemplate.from_template(
            """Localize the following content for the {target_locale} locale.
Consider cultural context, idioms, and regional preferences.
Context: {context}

Original content:
{text}

Localized version:"""
        )
        
        chain = prompt | self.llm
        
        result = await chain.ainvoke({
            "text": text,
            "target_locale": target_locale,
            "context": context
        })
        
        return {
            "success": True,
            "original_text": text,
            "localized_text": result.content,
            "target_locale": target_locale
        }
