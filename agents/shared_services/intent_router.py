# -*- coding: utf-8 -*-
"""
=============================================================================
Intent Router - 配置驅動的意圖路由器
=============================================================================

從 config/intents.yaml 載入意圖配置，動態路由請求。
不需要改代碼就可以添加新意圖！

=============================================================================
"""

import os
import re
import yaml
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from services.llm_service import LLMService

logger = logging.getLogger(__name__)


class IntentMatch(BaseModel):
    """Intent matching result"""
    intent: str = Field(description="Matched intent name")
    confidence: float = Field(default=1.0, description="Match confidence 0-1")
    route_to: str = Field(description="Target agent")
    handler: Optional[str] = Field(default=None, description="Specific handler method")
    matched_by: str = Field(default="pattern", description="pattern | llm | default")
    

class IntentRouter:
    """
    配置驅動的意圖路由器
    
    從 YAML 載入意圖定義，支持：
    1. 正則模式匹配 (快速)
    2. LLM 動態理解 (兜底)
    3. 熱重載配置 (不重啟服務)
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.config_path = Path(__file__).parent.parent.parent / "config" / "intents.yaml"
        self.intents: Dict[str, Dict] = {}
        self.compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self.last_loaded: Optional[datetime] = None
        
        # LLM Service for fallback classification
        self.llm_service = LLMService()
        
        self._load_config()
        self._initialized = True
        logger.info(f"IntentRouter initialized with {len(self.intents)} intents")
    
    def _load_config(self) -> None:
        """Load intent configuration from YAML"""
        try:
            if not self.config_path.exists():
                logger.warning(f"Intent config not found: {self.config_path}")
                self._load_defaults()
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            self.intents = config.get('intents', {})
            self.llm_fallback_enabled = config.get('llm_fallback', {}).get('enabled', True)
            
            # Compile regex patterns
            self.compiled_patterns = {}
            for intent_name, intent_config in self.intents.items():
                patterns = intent_config.get('patterns', [])
                self.compiled_patterns[intent_name] = [
                    re.compile(p, re.IGNORECASE | re.UNICODE) 
                    for p in patterns
                ]
            
            self.last_loaded = datetime.now()
            logger.info(f"Loaded {len(self.intents)} intents from {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load intent config: {e}")
            self._load_defaults()
    
    def _load_defaults(self) -> None:
        """Load default intents if config fails"""
        self.intents = {
            "casual_chat": {
                "description": "Casual conversation",
                "route_to": "casual_chat_agent",
                "patterns": [r"^(hi|hello|hey|你好)$"]
            },
            "general_query": {
                "description": "General questions",
                "route_to": "manager_agent",
                "patterns": []
            }
        }
        self.compiled_patterns = {
            "casual_chat": [re.compile(r"^(hi|hello|hey|你好)$", re.IGNORECASE)]
        }
        logger.info("Loaded default intents")
    
    def reload(self) -> bool:
        """Reload configuration (hot reload)"""
        try:
            self._load_config()
            return True
        except Exception as e:
            logger.error(f"Reload failed: {e}")
            return False
    
    def match(self, message: str, user_context: str = "") -> IntentMatch:
        """
        Match user message to an intent
        
        1. First try pattern matching (fast)
        2. If no match, use LLM (smart)
        3. Default to general_query
        """
        message_clean = message.strip()
        
        # Step 1: Pattern matching
        for intent_name, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(message_clean):
                    intent_config = self.intents[intent_name]
                    logger.debug(f"Pattern matched: {intent_name}")
                    return IntentMatch(
                        intent=intent_name,
                        confidence=0.95,
                        route_to=intent_config.get('route_to', 'manager_agent'),
                        handler=intent_config.get('handler'),
                        matched_by="pattern"
                    )
        
        # Step 2: LLM fallback (if enabled)
        if self.llm_fallback_enabled:
            try:
                return self._llm_classify(message_clean)
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}")
        
        # Step 3: Default
        return IntentMatch(
            intent="general_query",
            confidence=0.5,
            route_to="manager_agent",
            handler=None,
            matched_by="default"
        )
    
    def _llm_classify(self, message: str) -> IntentMatch:
        """Use LLM to classify intent"""
        # Build intent descriptions for prompt
        intent_list = "\n".join([
            f"- {name}: {config.get('description', 'No description')}"
            for name, config in self.intents.items()
        ])
        
        system_message = "你是一個意圖分類器，只回答意圖名稱，不要解釋。如果不確定，回答 general_query。"
        
        prompt = f"""分類這個用戶輸入的意圖。

可用意圖：
{intent_list}

用戶輸入: "{message}"

只回答意圖名稱，不要解釋。如果不確定，回答 "general_query"。
"""
        
        # Use synchronous generate (intent_router is not async)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            self.llm_service.generate(prompt=prompt, system_message=system_message, temperature=0)
        )
        intent_name = result.content.strip().lower().replace(" ", "_")
        
        # Validate intent exists
        if intent_name not in self.intents:
            intent_name = "general_query"
        
        intent_config = self.intents.get(intent_name, {})
        
        return IntentMatch(
            intent=intent_name,
            confidence=0.7,
            route_to=intent_config.get('route_to', 'manager_agent'),
            handler=intent_config.get('handler'),
            matched_by="llm"
        )
    
    def get_all_intents(self) -> Dict[str, Dict]:
        """Get all configured intents"""
        return self.intents.copy()
    
    def add_intent(self, name: str, config: Dict) -> bool:
        """
        Dynamically add a new intent (also saves to YAML)
        
        Example:
            router.add_intent("weather", {
                "description": "Weather queries",
                "route_to": "manager_agent",
                "handler": "weather_lookup",
                "patterns": ["天氣", "weather", "幾度"]
            })
        """
        try:
            # Add to memory
            self.intents[name] = config
            patterns = config.get('patterns', [])
            self.compiled_patterns[name] = [
                re.compile(p, re.IGNORECASE | re.UNICODE)
                for p in patterns
            ]
            
            # Save to YAML
            self._save_config()
            logger.info(f"Added intent: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add intent: {e}")
            return False
    
    def _save_config(self) -> None:
        """Save current configuration to YAML"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            config['intents'] = self.intents
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
                
        except Exception as e:
            logger.error(f"Failed to save config: {e}")


# Singleton getter
def get_intent_router() -> IntentRouter:
    """Get the intent router singleton"""
    return IntentRouter()
