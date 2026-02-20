"""
RAG Service - 統一的 RAG 查詢服務

統一管理所有 RAG 查詢操作：
1. 多數據庫查詢
2. 智能路由
3. 查詢快取
4. 結果去重與排序

使用範例:
    rag_service = get_rag_service()
    result = await rag_service.query("What is RAG?", strategy=RAGStrategy.AUTO)
"""

import asyncio
import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from services.vectordb_manager import vectordb_manager
from services.domain_events import (
    domain_event_bus,
    RAGQueryCompleted,
    RAGQueryFailed,
)

logger = logging.getLogger(__name__)


class RAGStrategy(str, Enum):
    """RAG 查詢策略"""
    SINGLE_DB = "single_db"           # 單一數據庫
    MULTI_DB = "multi_db"             # 多數據庫並行查詢
    SMART_ROUTING = "smart_routing"   # 智能路由（根據查詢選擇最佳數據庫）
    AUTO = "auto"                     # 自動選擇策略


class Source(BaseModel):
    """RAG 來源"""
    database: str
    title: str
    content: str = ""
    relevance: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGResult(BaseModel):
    """RAG 查詢結果"""
    query: str
    context: str
    sources: List[Source]
    strategy_used: str
    databases_queried: List[str]
    total_results: int
    avg_relevance: float
    cached: bool = False


class RAGCache:
    """RAG 查詢快取"""
    
    def __init__(self, max_age_seconds: int = 1800, max_size: int = 500):
        self.cache: Dict[str, tuple[RAGResult, datetime]] = {}
        self.max_age = timedelta(seconds=max_age_seconds)
        self.max_size = max_size
    
    def _generate_key(self, query: str, databases: List[str]) -> str:
        """生成快取鍵"""
        data = f"{query}|{'|'.join(sorted(databases))}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def get(self, query: str, databases: List[str]) -> Optional[RAGResult]:
        """獲取快取的結果"""
        key = self._generate_key(query, databases)
        
        if key in self.cache:
            result, timestamp = self.cache[key]
            
            # 檢查是否過期
            if datetime.now() - timestamp < self.max_age:
                result.cached = True
                return result
            else:
                del self.cache[key]
        
        return None
    
    def set(self, query: str, databases: List[str], result: RAGResult):
        """保存結果到快取"""
        # 如果快取已滿，移除最舊的項目
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        
        key = self._generate_key(query, databases)
        self.cache[key] = (result, datetime.now())
    
    def clear(self):
        """清空快取"""
        self.cache.clear()


class RAGService:
    """
    統一的 RAG 查詢服務
    
    特性：
    - 多種查詢策略
    - 自動策略選擇
    - 查詢快取
    - 結果去重與排序
    """
    
    def __init__(
        self,
        vectordb_manager=None,
        enable_cache: bool = True
    ):
        self.db_manager = vectordb_manager or globals()['vectordb_manager']
        self.cache = RAGCache() if enable_cache else None
        
        logger.info("[RAGService] Initialized")
    
    async def query(
        self,
        query: str,
        strategy: RAGStrategy = RAGStrategy.AUTO,
        top_k: int = 5,
        threshold: float = 0.3,
        databases: Optional[List[str]] = None,
        use_cache: bool = True
    ) -> RAGResult:
        """
        統一的 RAG 查詢接口
        
        Args:
            query: 查詢字符串
            strategy: 查詢策略
            top_k: 每個數據庫返回的結果數
            threshold: 相似度閾值（0-1）
            databases: 指定的數據庫列表（None = 所有）
            use_cache: 是否使用快取
        
        Returns:
            RAGResult
        """
        # 獲取可用的數據庫
        if databases is None:
            databases = await self._get_active_databases()
        
        if not databases:
            logger.warning("[RAGService] No active databases found")
            return RAGResult(
                query=query,
                context="",
                sources=[],
                strategy_used=strategy.value,
                databases_queried=[],
                total_results=0,
                avg_relevance=0.0
            )
        
        # 檢查快取
        if use_cache and self.cache:
            cached_result = self.cache.get(query, databases)
            if cached_result:
                logger.debug("[RAGService] Cache hit")
                domain_event_bus.publish(
                    RAGQueryCompleted(
                        query_preview=query[:120],
                        databases=databases,
                        result_count=cached_result.total_results,
                        avg_relevance=cached_result.avg_relevance,
                        strategy_used=cached_result.strategy_used,
                        cached=True,
                    )
                )
                return cached_result
        
        # 策略選擇
        if strategy == RAGStrategy.AUTO:
            strategy = self._auto_select_strategy(query, databases)
        
        # 執行查詢
        try:
            if strategy == RAGStrategy.SINGLE_DB:
                result = await self._query_single(query, databases[0], top_k, threshold)
            elif strategy == RAGStrategy.MULTI_DB:
                result = await self._query_multi(query, databases, top_k, threshold)
            elif strategy == RAGStrategy.SMART_ROUTING:
                result = await self._smart_routing(query, databases, top_k, threshold)
            else:
                result = await self._query_multi(query, databases, top_k, threshold)
        except Exception as e:
            logger.error(f"[RAGService] Query failed: {e}")
            domain_event_bus.publish(
                RAGQueryFailed(
                    query_preview=query[:120],
                    error=str(e),
                )
            )
            raise
        
        # 保存到快取
        if use_cache and self.cache:
            self.cache.set(query, databases, result)

        # 發布領域事件
        domain_event_bus.publish(
            RAGQueryCompleted(
                query_preview=query[:120],
                databases=databases,
                result_count=result.total_results,
                avg_relevance=result.avg_relevance,
                strategy_used=result.strategy_used,
                cached=False,
            )
        )

        return result
    
    async def _get_active_databases(self) -> List[str]:
        """獲取所有有數據的數據庫"""
        try:
            db_list = self.db_manager.list_databases()
            return [
                db["name"] for db in db_list 
                if db.get("document_count", 0) > 0
            ]
        except Exception as e:
            logger.error(f"[RAGService] Failed to get databases: {e}")
            return []
    
    def _auto_select_strategy(self, query: str, databases: List[str]) -> RAGStrategy:
        """自動選擇查詢策略"""
        # 如果只有一個數據庫，使用單庫查詢
        if len(databases) == 1:
            return RAGStrategy.SINGLE_DB
        
        # 如果數據庫數量較少（<=3），使用多庫並行
        if len(databases) <= 3:
            return RAGStrategy.MULTI_DB
        
        # 數據庫很多時，使用智能路由
        return RAGStrategy.SMART_ROUTING
    
    async def _query_single(
        self,
        query: str,
        database: str,
        top_k: int,
        threshold: float
    ) -> RAGResult:
        """單一數據庫查詢"""
        try:
            result = await self.db_manager.query(query, database, n_results=top_k)
            sources = self._extract_sources(result, database, threshold)
            
            context = self._build_context(sources)
            
            return RAGResult(
                query=query,
                context=context,
                sources=sources,
                strategy_used=RAGStrategy.SINGLE_DB.value,
                databases_queried=[database],
                total_results=len(sources),
                avg_relevance=self._calculate_avg_relevance(sources)
            )
            
        except Exception as e:
            logger.error(f"[RAGService] Single query failed: {e}")
            return self._empty_result(query, RAGStrategy.SINGLE_DB)
    
    async def _query_multi(
        self,
        query: str,
        databases: List[str],
        top_k: int,
        threshold: float
    ) -> RAGResult:
        """
        多數據庫平行查詢 (asyncio.gather 版本)

        原本的 for-loop 是逐一等待每個 DB 回應，N 個 DB 各需 T 毫秒則
        總延遲為 N×T。改用 asyncio.gather() 後所有 DB 同時查詢，
        總延遲接近 max(T_i)，通常大幅縮短整體等待時間。
        """

        async def _query_single(db_name: str):
            """查詢單一 DB，返回 (db_name, sources) 或 None（失敗時）"""
            try:
                result = await self.db_manager.query(query, db_name, n_results=top_k)
                sources = self._extract_sources(result, db_name, threshold)
                return db_name, sources
            except Exception as e:
                logger.warning(f"[RAGService] Error querying {db_name}: {e}")
                return None

        # 同時發射所有 DB 查詢
        raw_results = await asyncio.gather(
            *[_query_single(db) for db in databases],
            return_exceptions=False   # 異常已在 _query_single 內部處理
        )

        all_sources = []
        queried_dbs = []
        for item in raw_results:
            if item is not None:
                db_name, sources = item
                if sources:
                    all_sources.extend(sources)
                    queried_dbs.append(db_name)

        # 去重與排序
        all_sources = self._deduplicate_sources(all_sources)
        all_sources = sorted(all_sources, key=lambda x: x.relevance, reverse=True)
        
        # 限制總結果數量
        all_sources = all_sources[:top_k * 2]
        
        context = self._build_context(all_sources)
        
        return RAGResult(
            query=query,
            context=context,
            sources=all_sources,
            strategy_used=RAGStrategy.MULTI_DB.value,
            databases_queried=queried_dbs,
            total_results=len(all_sources),
            avg_relevance=self._calculate_avg_relevance(all_sources)
        )
    
    async def _smart_routing(
        self,
        query: str,
        databases: List[str],
        top_k: int,
        threshold: float
    ) -> RAGResult:
        """
        智能路由查詢
        
        根據查詢內容選擇最相關的數據庫
        """
        # 簡化版：選擇前 3 個數據庫進行查詢
        # 未來可以根據數據庫的 metadata 或歷史查詢進行智能選擇
        selected_dbs = databases[:3]
        
        return await self._query_multi(query, selected_dbs, top_k, threshold)
    
    def _extract_sources(
        self,
        result: Dict[str, Any],
        database: str,
        threshold: float
    ) -> List[Source]:
        """從查詢結果中提取 Sources"""
        sources = []
        db_results = result.get("results", [])
        
        if not isinstance(db_results, list):
            return sources
        
        for item in db_results:
            if not isinstance(item, dict):
                continue
            
            content = item.get("content", item.get("page_content", ""))
            if not content:
                continue
            
            metadata = item.get("metadata", {})
            distance = item.get("distance", 999)
            
            # 轉換 distance 為 similarity (0-1)
            # 距離越小，相似度越高
            similarity = max(0, min(1, 1 - (distance / 2)))
            
            # 過濾低相似度結果
            if similarity < threshold:
                continue
            
            sources.append(Source(
                database=database,
                title=metadata.get("title", metadata.get("source", "Unknown")),
                content=content[:500],  # 限制長度
                relevance=round(similarity, 2),
                metadata=metadata
            ))
        
        return sources
    
    def _build_context(self, sources: List[Source]) -> str:
        """從 Sources 構建上下文字符串"""
        if not sources:
            return ""
        
        context_parts = [
            f"[From {s.database}]: {s.content}"
            for s in sources
        ]
        
        return "\n\n".join(context_parts)
    
    def _deduplicate_sources(self, sources: List[Source]) -> List[Source]:
        """去重 Sources（基於內容相似度）"""
        if not sources:
            return sources
        
        unique_sources = []
        seen_content = set()
        
        for source in sources:
            # 使用內容的前 200 字符作為去重標準
            content_key = source.content[:200]
            
            if content_key not in seen_content:
                unique_sources.append(source)
                seen_content.add(content_key)
        
        return unique_sources
    
    def _calculate_avg_relevance(self, sources: List[Source]) -> float:
        """計算平均相似度"""
        if not sources:
            return 0.0
        
        return round(sum(s.relevance for s in sources) / len(sources), 2)
    
    def _empty_result(self, query: str, strategy: RAGStrategy) -> RAGResult:
        """創建空結果"""
        return RAGResult(
            query=query,
            context="",
            sources=[],
            strategy_used=strategy.value,
            databases_queried=[],
            total_results=0,
            avg_relevance=0.0
        )
    
    def clear_cache(self):
        """清空快取"""
        if self.cache:
            self.cache.clear()
            logger.info("[RAGService] Cache cleared")


# 單例模式
_rag_service: Optional[RAGService] = None


def get_rag_service(reset: bool = False) -> RAGService:
    """獲取 RAG Service 單例"""
    global _rag_service
    
    if reset or _rag_service is None:
        _rag_service = RAGService(
            vectordb_manager=vectordb_manager,
            enable_cache=True
        )
    
    return _rag_service
