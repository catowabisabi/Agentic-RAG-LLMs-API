# -*- coding: utf-8 -*-
"""
=============================================================================
SolidWorks API Agent
=============================================================================

專門查詢 SolidWorks API 文檔的智能代理。

功能：
-----------
1. 關鍵字搜索 - 使用 SQLite FTS5 全文檢索
2. 語意擴展 - 使用 LLM 擴展查詢詞，找到相似概念
3. 代碼範例 - 返回相關的 VBA/C# 代碼範例
4. API 成員查詢 - 查詢特定 Interface 的方法和屬性

資料來源：
-----------
data/solidworks_db/sw_api_doc.db

=============================================================================
"""

import asyncio
import logging
import sqlite3
from typing import Dict, Any, List, Optional
from pathlib import Path

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import TaskAssignment

logger = logging.getLogger(__name__)


class SWAgent(BaseAgent):
    """
    SolidWorks API 專家代理
    
    透過關鍵字搜索 + LLM 語意擴展，找到最相關的 API 文檔和代碼範例。
    """
    
    def __init__(self, agent_name: str = "sw_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="SolidWorks API Specialist",
            agent_description="Searches SolidWorks API documentation and code examples"
        )
        
        # Database path
        self.db_path = Path("data/solidworks_db/sw_api_doc.db")
        
        # 確保資料庫存在
        if not self.db_path.exists():
            logger.warning(f"SolidWorks DB not found at {self.db_path}")
        else:
            logger.info(f"SolidWorks DB loaded from {self.db_path}")
        
        logger.info("SWAgent initialized")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get SQLite connection"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    # =========================================================================
    # 核心搜索方法
    # =========================================================================
    
    async def search(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        混合搜索：關鍵字 + 語意擴展
        
        Args:
            query: 用戶查詢（例如 "怎麼畫圓"、"OpenDoc6 參數"）
            top_k: 返回結果數量
            
        Returns:
            包含文檔、代碼範例、API 成員的結果
        """
        # Step 1: 用 LLM 擴展查詢詞（找同義詞和相關概念）
        expanded_terms = await self._expand_query(query)
        logger.info(f"[SWAgent] Query expanded: {query} -> {expanded_terms}")
        
        # Step 2: 執行多維度搜索
        results = {
            "query": query,
            "expanded_terms": expanded_terms,
            "documents": [],
            "code_examples": [],
            "api_members": []
        }
        
        # 對每個關鍵詞進行搜索
        all_terms = [query] + expanded_terms
        
        for term in all_terms[:5]:  # 限制搜索次數
            docs = self._search_documents(term, limit=top_k // 2)
            codes = self._search_code_examples(term, limit=top_k // 2)
            members = self._search_api_members(term, limit=top_k // 2)
            
            results["documents"].extend(docs)
            results["code_examples"].extend(codes)
            results["api_members"].extend(members)
        
        # Step 3: 去重並排序
        results["documents"] = self._deduplicate(results["documents"], "id")[:top_k]
        results["code_examples"] = self._deduplicate(results["code_examples"], "id")[:top_k]
        results["api_members"] = self._deduplicate(results["api_members"], "id")[:top_k]
        
        return results
    
    async def _expand_query(self, query: str) -> List[str]:
        """
        使用 LLM 擴展查詢詞，找到 SolidWorks API 中的相關術語
        """
        system_message = """You are a SolidWorks API expert. Given a user query, generate related API terms and synonyms.

Rules:
1. Output ONLY a comma-separated list of terms
2. Include English API method names (like InsertSketchCircle, OpenDoc6)
3. Include related concepts (like Sketch, Feature, Body)
4. Maximum 5 terms
5. No explanations, just the terms

Example:
Query: 怎麼畫圓
Output: Circle, InsertSketchCircle, CreateCircle, Sketch, Arc

Query: 打開文件
Output: OpenDoc, OpenDoc6, OpenDoc7, LoadFile, swOpenDoc"""

        try:
            response = await self.llm_service.generate(
                prompt=f"Query: {query}\nOutput:",
                system_message=system_message,
                temperature=0.3
            )
            
            # 解析返回的詞彙
            terms = [t.strip() for t in response.content.split(",") if t.strip()]
            return terms[:5]
        except Exception as e:
            logger.warning(f"[SWAgent] Query expansion failed: {e}")
            return []
    
    def _search_documents(self, term: str, limit: int = 5) -> List[Dict]:
        """使用 FTS5 搜索文檔"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # FTS5 搜索
            cursor.execute("""
                SELECT d.id, d.title, d.doc_type, d.interface_name, d.description,
                       d.full_text, d.source_url
                FROM documents d
                JOIN documents_fts fts ON d.rowid = fts.rowid
                WHERE documents_fts MATCH ?
                LIMIT ?
            """, (term, limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "title": row["title"],
                    "doc_type": row["doc_type"],
                    "interface_name": row["interface_name"],
                    "description": row["description"][:500] if row["description"] else "",
                    "url": row["source_url"]
                })
            
            conn.close()
            return results
        except Exception as e:
            logger.warning(f"[SWAgent] Document search failed for '{term}': {e}")
            return []
    
    def _search_code_examples(self, term: str, limit: int = 5) -> List[Dict]:
        """搜索代碼範例"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 在代碼和標題中搜索
            cursor.execute("""
                SELECT id, language, code, title, description, related_method, related_interface
                FROM code_examples
                WHERE code LIKE ? OR title LIKE ? OR related_method LIKE ?
                LIMIT ?
            """, (f"%{term}%", f"%{term}%", f"%{term}%", limit))
            
            results = []
            for row in cursor.fetchall():
                code = row["code"]
                # 截斷過長的代碼
                if code and len(code) > 1000:
                    code = code[:1000] + "\n... (truncated)"
                
                results.append({
                    "id": row["id"],
                    "language": row["language"],
                    "code": code,
                    "title": row["title"],
                    "method": row["related_method"],
                    "interface": row["related_interface"]
                })
            
            conn.close()
            return results
        except Exception as e:
            logger.warning(f"[SWAgent] Code search failed for '{term}': {e}")
            return []
    
    def _search_api_members(self, term: str, limit: int = 5) -> List[Dict]:
        """搜索 API 成員（方法、屬性）"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, interface_name, name, member_type, syntax_vb, syntax_csharp,
                       description, return_type, remarks
                FROM api_members
                WHERE name LIKE ? OR interface_name LIKE ? OR description LIKE ?
                LIMIT ?
            """, (f"%{term}%", f"%{term}%", f"%{term}%", limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "interface": row["interface_name"],
                    "name": row["name"],
                    "type": row["member_type"],
                    "syntax_vb": row["syntax_vb"],
                    "syntax_csharp": row["syntax_csharp"],
                    "description": row["description"][:300] if row["description"] else "",
                    "return_type": row["return_type"]
                })
            
            conn.close()
            return results
        except Exception as e:
            logger.warning(f"[SWAgent] API member search failed for '{term}': {e}")
            return []
    
    def _deduplicate(self, items: List[Dict], key: str) -> List[Dict]:
        """去重"""
        seen = set()
        unique = []
        for item in items:
            if item.get(key) not in seen:
                seen.add(item.get(key))
                unique.append(item)
        return unique
    
    # =========================================================================
    # 特定查詢方法
    # =========================================================================
    
    def get_interface_members(self, interface_name: str) -> List[Dict]:
        """獲取特定 Interface 的所有成員"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name, member_type, syntax_vb, description, return_type
                FROM api_members
                WHERE interface_name LIKE ?
                ORDER BY member_type, name
            """, (f"%{interface_name}%",))
            
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except Exception as e:
            logger.warning(f"[SWAgent] Interface lookup failed: {e}")
            return []
    
    def get_method_details(self, method_name: str) -> Optional[Dict]:
        """獲取特定方法的詳細資訊"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT m.*, d.full_text, d.remarks as doc_remarks
                FROM api_members m
                LEFT JOIN documents d ON m.doc_id = d.id
                WHERE m.name = ?
                LIMIT 1
            """, (method_name,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.warning(f"[SWAgent] Method lookup failed: {e}")
            return None
    
    # =========================================================================
    # BaseAgent 必須實現的方法
    # =========================================================================
    
    async def process_task(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        處理任務
        
        支援的任務類型：
        - search: 混合搜索
        - interface: 獲取 Interface 成員
        - method: 獲取方法詳情
        """
        task_type = task.input_data.get("type", "search")
        query = task.input_data.get("query", task.description)
        
        await self.broadcast.agent_status(
            self.agent_name, "processing", task.task_id,
            {"query": query, "type": task_type}
        )
        
        try:
            if task_type == "interface":
                interface_name = task.input_data.get("interface", query)
                members = self.get_interface_members(interface_name)
                result = {
                    "interface": interface_name,
                    "members": members,
                    "count": len(members)
                }
            elif task_type == "method":
                method_name = task.input_data.get("method", query)
                details = self.get_method_details(method_name)
                result = {"method": method_name, "details": details}
            else:
                # Default: 混合搜索
                result = await self.search(query, top_k=10)
            
            # 用 LLM 生成回答
            answer = await self._generate_answer(query, result)
            
            await self.broadcast.agent_status(
                self.agent_name, "completed", task.task_id
            )
            
            return {
                "response": answer,
                "search_results": result,
                "source": "solidworks_api_db"
            }
            
        except Exception as e:
            logger.error(f"[SWAgent] Task failed: {e}")
            await self.broadcast.agent_status(
                self.agent_name, "error", task.task_id, {"error": str(e)}
            )
            return {"response": f"搜索失敗: {str(e)}", "error": str(e)}
    
    async def _generate_answer(self, query: str, search_results: Dict) -> str:
        """根據搜索結果生成回答"""
        
        # 準備上下文
        context_parts = []
        
        # 加入 API 成員資訊
        if search_results.get("api_members"):
            context_parts.append("## API Methods Found:")
            for m in search_results["api_members"][:3]:
                context_parts.append(f"- **{m.get('interface', '')}.{m.get('name', '')}**")
                if m.get('syntax_vb'):
                    context_parts.append(f"  VB: `{m['syntax_vb']}`")
                if m.get('description'):
                    context_parts.append(f"  {m['description']}")
        
        # 加入代碼範例
        if search_results.get("code_examples"):
            context_parts.append("\n## Code Examples:")
            for c in search_results["code_examples"][:2]:
                context_parts.append(f"### {c.get('title', 'Example')} ({c.get('language', 'VB')})")
                context_parts.append(f"```{c.get('language', 'vb')}")
                context_parts.append(c.get('code', '')[:800])
                context_parts.append("```")
        
        # 加入文檔摘要
        if search_results.get("documents"):
            context_parts.append("\n## Related Documentation:")
            for d in search_results["documents"][:3]:
                context_parts.append(f"- **{d.get('title', '')}** ({d.get('doc_type', '')})")
                if d.get('description'):
                    context_parts.append(f"  {d['description'][:200]}")
        
        context = "\n".join(context_parts)
        
        if not context.strip():
            return f"抱歉，沒有找到關於 '{query}' 的 SolidWorks API 資訊。請嘗試用英文關鍵詞搜索。"
        
        system_message = """You are a SolidWorks API expert. Based on the search results, provide a helpful answer.

Rules:
1. Answer in the same language as the user's query (Chinese or English)
2. Include relevant code examples if available
3. Explain the API methods clearly
4. If the information is incomplete, say so
5. Format code blocks properly"""

        prompt = f"""User Query: {query}

Search Results:
{context}

Please provide a helpful answer based on these results:"""

        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                system_message=system_message,
                temperature=0.5
            )
            return response.content
        except Exception as e:
            logger.warning(f"[SWAgent] Answer generation failed: {e}")
            return f"找到了以下資訊：\n\n{context}"
