"""
LLM Service - 統一的 LLM 服務層

統一管理所有 LLM 調用，提供：
1. 多 Provider 支持 (OpenAI, Anthropic, Google)
2. Token 使用追蹤
3. 統一的錯誤處理與重試
4. 快取機制
5. 成本追蹤

使用範例:
    llm_service = get_llm_service()
    response = await llm_service.generate("Hello", temperature=0.7)
    stats = llm_service.get_usage_stats()
"""

import logging
import hashlib
import json
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from config.config import Config

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """支持的 LLM Provider"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"


class TokenUsage(BaseModel):
    """Token 使用統計"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


class LLMRequest(BaseModel):
    """LLM 請求"""
    prompt: Union[str, List[Dict[str, str]]]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    model: Optional[str] = None
    system_message: Optional[str] = None
    stop_sequences: Optional[List[str]] = None


class LLMResponse(BaseModel):
    """LLM 響應"""
    content: str
    usage: TokenUsage
    model: str
    cached: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TokenUsageTracker:
    """Token 使用追蹤器"""
    
    def __init__(self):
        self.total_usage = TokenUsage()
        self.session_usage: Dict[str, TokenUsage] = {}
        self.model_usage: Dict[str, TokenUsage] = {}
        self.hourly_usage: Dict[str, TokenUsage] = {}
        
        # 價格表 (每 1M tokens 的價格，USD)
        self.pricing = {
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00},
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        }
    
    def track(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        session_id: str = "default"
    ):
        """記錄 Token 使用"""
        total = prompt_tokens + completion_tokens
        
        # 計算成本
        cost = 0.0
        if model in self.pricing:
            cost = (
                (prompt_tokens / 1_000_000) * self.pricing[model]["input"] +
                (completion_tokens / 1_000_000) * self.pricing[model]["output"]
            )
        
        # 更新總計
        self.total_usage.prompt_tokens += prompt_tokens
        self.total_usage.completion_tokens += completion_tokens
        self.total_usage.total_tokens += total
        self.total_usage.cost += cost
        
        # 更新 Session 統計
        if session_id not in self.session_usage:
            self.session_usage[session_id] = TokenUsage()
        self.session_usage[session_id].prompt_tokens += prompt_tokens
        self.session_usage[session_id].completion_tokens += completion_tokens
        self.session_usage[session_id].total_tokens += total
        self.session_usage[session_id].cost += cost
        
        # 更新 Model 統計
        if model not in self.model_usage:
            self.model_usage[model] = TokenUsage()
        self.model_usage[model].prompt_tokens += prompt_tokens
        self.model_usage[model].completion_tokens += completion_tokens
        self.model_usage[model].total_tokens += total
        self.model_usage[model].cost += cost
        
        # 更新小時統計
        hour_key = datetime.now().strftime("%Y-%m-%d %H:00")
        if hour_key not in self.hourly_usage:
            self.hourly_usage[hour_key] = TokenUsage()
        self.hourly_usage[hour_key].prompt_tokens += prompt_tokens
        self.hourly_usage[hour_key].completion_tokens += completion_tokens
        self.hourly_usage[hour_key].total_tokens += total
        self.hourly_usage[hour_key].cost += cost
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取統計數據"""
        return {
            "total": self.total_usage.model_dump(),
            "by_session": {k: v.model_dump() for k, v in self.session_usage.items()},
            "by_model": {k: v.model_dump() for k, v in self.model_usage.items()},
            "by_hour": {k: v.model_dump() for k, v in self.hourly_usage.items()}
        }
    
    def reset_session(self, session_id: str):
        """重置 Session 統計"""
        if session_id in self.session_usage:
            del self.session_usage[session_id]


class LLMCache:
    """LLM 響應快取"""
    
    def __init__(self, max_age_seconds: int = 3600, max_size: int = 1000):
        self.cache: Dict[str, tuple[LLMResponse, datetime]] = {}
        self.max_age = timedelta(seconds=max_age_seconds)
        self.max_size = max_size
    
    def _generate_key(self, request: LLMRequest) -> str:
        """生成快取鍵"""
        data = {
            "prompt": request.prompt,
            "temperature": request.temperature,
            "model": request.model,
            "system": request.system_message
        }
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    def get(self, request: LLMRequest) -> Optional[LLMResponse]:
        """獲取快取的響應"""
        key = self._generate_key(request)
        
        if key in self.cache:
            response, timestamp = self.cache[key]
            
            # 檢查是否過期
            if datetime.now() - timestamp < self.max_age:
                response.cached = True
                return response
            else:
                del self.cache[key]
        
        return None
    
    def set(self, request: LLMRequest, response: LLMResponse):
        """保存響應到快取"""
        # 如果快取已滿，移除最舊的項目
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        
        key = self._generate_key(request)
        self.cache[key] = (response, datetime.now())
    
    def clear(self):
        """清空快取"""
        self.cache.clear()


class LLMService:
    """
    統一的 LLM 服務層
    
    特性：
    - 多 Provider 支持
    - Token 追蹤與成本計算
    - 自動重試與錯誤處理
    - 響應快取
    - 統一的接口
    """
    
    def __init__(
        self,
        config: Optional[Config] = None,
        provider: LLMProvider = LLMProvider.OPENAI,
        enable_cache: bool = True,
        enable_tracking: bool = True
    ):
        self.config = config or Config()
        self.provider = provider
        
        # 初始化 Provider
        self._llm = self._create_provider()
        
        # Token 追蹤
        self.tracker = TokenUsageTracker() if enable_tracking else None
        
        # 快取
        self.cache = LLMCache() if enable_cache else None
        
        logger.info(f"[LLMService] Initialized with provider: {provider}")
    
    def _create_provider(self):
        """根據配置創建 LLM Provider"""
        if self.provider == LLMProvider.OPENAI:
            return ChatOpenAI(
                model=self.config.DEFAULT_MODEL,
                temperature=self.config.TEMPERATURE,
                api_key=self.config.OPENAI_API_KEY,
                max_tokens=self.config.MAX_TOKENS
            )
        elif self.provider == LLMProvider.ANTHROPIC:
            # 未來支持
            try:
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    model="claude-3-sonnet-20240229",
                    api_key=self.config.ANTHROPIC_API_KEY
                )
            except ImportError:
                logger.warning("Anthropic not installed, falling back to OpenAI")
                return self._create_openai_provider()
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _create_openai_provider(self):
        """創建 OpenAI Provider"""
        return ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=self.config.TEMPERATURE,
            api_key=self.config.OPENAI_API_KEY,
            max_tokens=self.config.MAX_TOKENS
        )
    
    async def generate(
        self,
        prompt: Union[str, List[Dict[str, str]]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        system_message: Optional[str] = None,
        session_id: str = "default",
        use_cache: bool = True
    ) -> LLMResponse:
        """
        生成 LLM 響應
        
        Args:
            prompt: 提示詞或消息列表
            temperature: 溫度參數
            max_tokens: 最大 Token 數
            model: 模型名稱（覆蓋默認）
            system_message: 系統消息
            session_id: Session ID（用於追蹤）
            use_cache: 是否使用快取
        
        Returns:
            LLMResponse
        """
        # 創建請求對象
        request = LLMRequest(
            prompt=prompt,
            temperature=temperature or self.config.TEMPERATURE,
            max_tokens=max_tokens or self.config.MAX_TOKENS,
            model=model or self.config.DEFAULT_MODEL,
            system_message=system_message
        )
        
        # 檢查快取
        if use_cache and self.cache:
            cached_response = self.cache.get(request)
            if cached_response:
                logger.debug("[LLMService] Cache hit")
                return cached_response
        
        # 準備消息
        messages = self._prepare_messages(prompt, system_message)
        
        # 創建帶參數的 LLM
        llm = self._llm
        if temperature is not None or max_tokens is not None or model is not None:
            llm = ChatOpenAI(
                model=model or self.config.DEFAULT_MODEL,
                temperature=temperature or self.config.TEMPERATURE,
                max_tokens=max_tokens or self.config.MAX_TOKENS,
                api_key=self.config.OPENAI_API_KEY
            )
        
        try:
            # 調用 LLM
            result = await llm.ainvoke(messages)
            
            # 提取內容
            content = result.content if hasattr(result, 'content') else str(result)
            
            # 提取 Token 使用
            usage = TokenUsage()
            if hasattr(result, 'response_metadata'):
                token_usage = result.response_metadata.get('token_usage', {})
                usage.prompt_tokens = token_usage.get('prompt_tokens', 0)
                usage.completion_tokens = token_usage.get('completion_tokens', 0)
                usage.total_tokens = token_usage.get('total_tokens', 0)
            
            # 追蹤使用
            if self.tracker:
                self.tracker.track(
                    model=request.model,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    session_id=session_id
                )
                usage.cost = self.tracker.session_usage.get(session_id, TokenUsage()).cost
            
            # 創建響應
            response = LLMResponse(
                content=content,
                usage=usage,
                model=request.model,
                cached=False
            )
            
            # 保存到快取
            if use_cache and self.cache:
                self.cache.set(request, response)
            
            return response
            
        except Exception as e:
            logger.error(f"[LLMService] Generation failed: {e}")
            
            # Check if this is an API key error
            error_str = str(e)
            if "401" in error_str or "invalid_api_key" in error_str.lower() or "incorrect api key" in error_str.lower():
                # Broadcast API key error
                try:
                    from services.broadcast_service import get_broadcast_service
                    broadcast = get_broadcast_service()
                    await broadcast.custom(
                        message_type="api_key_error",
                        content={
                            "error": "Invalid or missing API key",
                            "provider": self.provider,
                            "details": error_str,
                            "action_required": "Please provide a valid API key"
                        }
                    )
                except Exception as broadcast_error:
                    logger.warning(f"Failed to broadcast API key error: {broadcast_error}")
            
            raise
    
    async def astream(
        self,
        prompt: Union[str, List[Dict[str, str]]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        system_message: Optional[str] = None,
        session_id: str = "default"
    ):
        """
        Stream LLM response token-by-token.
        
        Yields string chunks as they arrive from the LLM provider.
        """
        messages = self._prepare_messages(prompt, system_message)
        
        llm = self._llm
        if temperature is not None or max_tokens is not None or model is not None:
            llm = ChatOpenAI(
                model=model or self.config.DEFAULT_MODEL,
                temperature=temperature or self.config.TEMPERATURE,
                max_tokens=max_tokens or self.config.MAX_TOKENS,
                api_key=self.config.OPENAI_API_KEY,
                streaming=True
            )
        
        full_content = ""
        async for chunk in llm.astream(messages):
            token = chunk.content if hasattr(chunk, 'content') else str(chunk)
            if token:
                full_content += token
                yield token
        
        # Track usage (estimated — streaming doesn't always return exact counts)
        if self.tracker:
            self.tracker.track(
                model=model or self.config.DEFAULT_MODEL,
                prompt_tokens=len(str(messages)) // 4,  # rough estimate
                completion_tokens=len(full_content) // 4,
                session_id=session_id
            )
    
    def _prepare_messages(
        self,
        prompt: Union[str, List[Dict[str, str]]],
        system_message: Optional[str] = None
    ) -> List:
        """準備消息列表"""
        messages = []
        
        # 添加系統消息
        if system_message:
            messages.append(SystemMessage(content=system_message))
        
        # 處理提示詞
        if isinstance(prompt, str):
            messages.append(HumanMessage(content=prompt))
        elif isinstance(prompt, list):
            for msg in prompt:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    messages.append(SystemMessage(content=content))
                elif role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
        
        return messages
    
    def get_usage_stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """獲取使用統計"""
        if not self.tracker:
            return {"error": "Tracking not enabled"}
        
        if session_id:
            return {
                "session": self.tracker.session_usage.get(session_id, TokenUsage()).model_dump()
            }
        
        return self.tracker.get_stats()
    
    def reset_session_stats(self, session_id: str):
        """重置 Session 統計"""
        if self.tracker:
            self.tracker.reset_session(session_id)
    
    def clear_cache(self):
        """清空快取"""
        if self.cache:
            self.cache.clear()
            logger.info("[LLMService] Cache cleared")
    
    async def generate_with_structured_output(
        self,
        prompt_key: str,
        output_schema: type,
        variables: Dict[str, Any] = None,
        user_input: str = "",
        temperature: float = 0.1
    ) -> Any:
        """
        生成結構化輸出（使用 LLM with_structured_output）
        
        Args:
            prompt_key: Prompt 配置鍵
            output_schema: Pydantic 模型類
            variables: 插入 prompt 的變數
            user_input: 用戶輸入
            temperature: 溫度參數
        
        Returns:
            output_schema 實例
        """
        try:
            # 創建結構化輸出的 LLM
            structured_llm = self._llm.with_structured_output(output_schema)
            
            # 構建 prompt
            prompt = user_input
            if variables:
                for key, value in variables.items():
                    prompt = prompt.replace(f"{{{key}}}", str(value))
            
            # 調用 LLM
            result = await structured_llm.ainvoke(prompt)
            
            return result
            
        except Exception as e:
            logger.error(f"[LLMService] Structured output generation failed: {e}")
            # 返回默認實例
            if hasattr(output_schema, '__call__'):
                return output_schema()
            raise

# 單例模式（線程安全）
import threading

_llm_service: Optional[LLMService] = None
_llm_service_lock = threading.Lock()


def get_llm_service(
    config: Optional[Config] = None,
    provider: LLMProvider = LLMProvider.OPENAI,
    reset: bool = False
) -> LLMService:
    """獲取 LLM Service 單例（線程安全）"""
    global _llm_service
    
    if not reset and _llm_service is not None:
        return _llm_service
    
    with _llm_service_lock:
        # Double-checked locking
        if reset or _llm_service is None:
            _llm_service = LLMService(
                config=config,
                provider=provider,
                enable_cache=True,
                enable_tracking=True
            )
    
    return _llm_service
