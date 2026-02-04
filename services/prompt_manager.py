"""
Prompt Manager - Prompt 模板管理

統一管理所有 Agent 的 Prompt 模板：
1. 從外部 YAML 文件加載
2. 支持多語言版本
3. 支持 Prompt 版本控制
4. 支持動態變量替換

使用範例:
    pm = get_prompt_manager()
    prompt = pm.get_prompt("casual_chat_agent")
    rendered = pm.render(prompt, {"user_name": "Alice"})
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PromptTemplate(BaseModel):
    """Prompt 模板"""
    agent_name: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 2000
    variables: Dict[str, str] = Field(default_factory=dict)
    examples: List[Dict[str, str]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PromptManager:
    """
    Prompt 模板管理器
    
    特性：
    - 從 YAML 文件加載 Prompt
    - 快取機制
    - 動態變量替換
    - 多語言支持
    """
    
    def __init__(self, prompts_dir: str = "config/prompts"):
        self.prompts_dir = Path(prompts_dir)
        self.cache: Dict[str, PromptTemplate] = {}
        
        # 確保目錄存在
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[PromptManager] Initialized with dir: {prompts_dir}")
    
    def get_prompt(self, agent_name: str, reload: bool = False) -> PromptTemplate:
        """
        獲取 Agent 的 Prompt 模板
        
        Args:
            agent_name: Agent 名稱
            reload: 是否重新加載（不使用快取）
        
        Returns:
            PromptTemplate
        """
        # 檢查快取
        if not reload and agent_name in self.cache:
            return self.cache[agent_name]
        
        # 從文件加載
        template = self._load_from_file(agent_name)
        
        # 保存到快取
        self.cache[agent_name] = template
        
        return template
    
    def _load_from_file(self, agent_name: str) -> PromptTemplate:
        """從 YAML 文件加載 Prompt"""
        file_path = self.prompts_dir / f"{agent_name}.yaml"
        
        if not file_path.exists():
            logger.warning(f"[PromptManager] Prompt file not found: {file_path}")
            return self._create_default_prompt(agent_name)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            return PromptTemplate(**data)
            
        except Exception as e:
            logger.error(f"[PromptManager] Failed to load prompt: {e}")
            return self._create_default_prompt(agent_name)
    
    def _create_default_prompt(self, agent_name: str) -> PromptTemplate:
        """創建默認 Prompt"""
        return PromptTemplate(
            agent_name=agent_name,
            system_prompt=f"You are a helpful assistant for {agent_name}.",
            temperature=0.7,
            max_tokens=2000
        )
    
    def render(
        self,
        template: PromptTemplate,
        variables: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        渲染 Prompt 模板（替換變量）
        
        Args:
            template: Prompt 模板
            variables: 變量字典
        
        Returns:
            渲染後的 Prompt
        """
        prompt = template.system_prompt
        
        if variables:
            for key, value in variables.items():
                placeholder = f"{{{key}}}"
                if placeholder in prompt:
                    prompt = prompt.replace(placeholder, str(value))
        
        return prompt
    
    def save_prompt(self, template: PromptTemplate):
        """保存 Prompt 模板到文件"""
        file_path = self.prompts_dir / f"{template.agent_name}.yaml"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(template.model_dump(), f, allow_unicode=True, sort_keys=False)
            
            # 更新快取
            self.cache[template.agent_name] = template
            
            logger.info(f"[PromptManager] Saved prompt: {template.agent_name}")
            
        except Exception as e:
            logger.error(f"[PromptManager] Failed to save prompt: {e}")
    
    def list_prompts(self) -> List[str]:
        """列出所有可用的 Prompt"""
        if not self.prompts_dir.exists():
            return []
        
        return [
            f.stem for f in self.prompts_dir.glob("*.yaml")
        ]
    
    def reload_all(self):
        """重新加載所有 Prompt"""
        self.cache.clear()
        logger.info("[PromptManager] All prompts reloaded")


# 單例模式
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager(prompts_dir: str = "config/prompts") -> PromptManager:
    """獲取 Prompt Manager 單例"""
    global _prompt_manager
    
    if _prompt_manager is None:
        _prompt_manager = PromptManager(prompts_dir)
    
    return _prompt_manager
