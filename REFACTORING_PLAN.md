# 代碼重構與模組化計劃書
> **生成日期**: 2026-02-03  
> **目標**: 簡化代碼、提高可維護性、減少重複  
> **原則**: 不破壞現有功能，逐步重構

---

## 📊 現狀分析

### 系統規模
- **Agent 總數**: 19+ 個 (Core: 11, Auxiliary: 7, Legacy: 1)
- **API Routers**: 8 個
- **代碼行數**: 估計 15,000+ 行
- **重複模式**: 大量

### 主要問題

#### 1. **重複代碼 (Code Duplication)**
**嚴重程度**: 🔴 高

**問題點**:
- ✅ **LLM 初始化重複** (20+ 處)
  ```python
  # 每個 Agent 都重複這段
  self.llm = ChatOpenAI(
      model=self.config.DEFAULT_MODEL,
      temperature=0.X,
      api_key=self.config.OPENAI_API_KEY
  )
  ```

- ✅ **RAG 查詢邏輯重複**
  - `chat_router.py::get_rag_context()` - 193 行
  - `ws_chat_router.py::rag_search_tool()` - 96 行
  - 幾乎相同的邏輯，略有差異

- ✅ **WebSocket 廣播邏輯重複**
  - `manager_agent.py::_broadcast_status()`
  - `manager_agent_v2.py::_broadcast_status()`
  - 多個 Router 都有自己的 `send_step()` / `broadcast()`

- ✅ **任務處理流程重複**
  - `chat_router.py::process_chat_task()` - 800+ 行
  - `ws_chat_router.py::process_chat_stream()` - 300+ 行
  - 核心邏輯相似，但一個是 REST 一個是 WebSocket


#### 2. **職責混亂 (Mixed Responsibilities)**
**嚴重程度**: 🟡 中

**問題點**:
- ✅ **Manager Agent 過度膨脹**
  - `manager_agent.py`: **1721 行**
  - `manager_agent_v2.py`: **687 行**
  - 兩個版本並存，職責重疊 80%

- ✅ **Router 包含業務邏輯**
  - `chat_router.py` 中有完整的 Entry Classifier 調用、記憶處理、RAG 查詢
  - 應該交給 Service Layer 統一處理

- ✅ **Agent 直接依賴具體實現**
  - 大部分 Agent 直接 `import ChatOpenAI`
  - 難以切換不同的 LLM Provider (如 Anthropic, Google)


#### 3. **配置分散 (Configuration Scattered)**
**嚴重程度**: 🟡 中

**問題點**:
- ✅ **硬編碼的參數**
  ```python
  # 在不同文件中重複出現
  max_iterations=3
  temperature=0.2
  top_k=5
  ```

- ✅ **Agent 能力定義分散**
  - `manager_agent_v2.py` 第 156 行定義了 `agent_capabilities`
  - 應該從外部配置檔案讀取


#### 4. **缺乏抽象層 (Missing Abstraction)**
**嚴重程度**: 🔴 高

**問題點**:
- ✅ **沒有統一的 LLM Service**
  - 每個 Agent 自己初始化 LLM
  - 無法統一控制 Token 使用、費用追蹤

- ✅ **沒有統一的 RAG Service**
  - RAG 查詢邏輯散落在多個地方
  - 難以統一優化、A/B 測試

- ✅ **沒有統一的 Prompt 管理**
  - System Prompt 硬編碼在各個 Agent 中
  - 難以調整、版本控制


#### 5. **測試困難 (Hard to Test)**
**嚴重程度**: 🟡 中

**問題點**:
- ✅ **緊耦合依賴**
  - Agent 直接依賴 `ChatOpenAI`，難以 Mock
  - 測試時必須連接真實 API

- ✅ **缺乏依賴注入**
  - 所有依賴都是內部創建 (`self.llm = ...`)
  - 無法在測試時替換為 Mock Object

---

## 🎯 重構目標

### 短期目標 (1-2 週)
1. ✅ 建立統一的 LLM Service
2. ✅ 提取重複的 RAG 查詢邏輯
3. ✅ 統一 WebSocket 廣播機制
4. ✅ 整合 Manager Agent 兩個版本

### 中期目標 (2-4 週)
1. ✅ 建立 Service Layer (LLM, RAG, Memory)
2. ✅ Prompt 模板化與外部化
3. ✅ Agent 配置外部化
4. ✅ 簡化 Auxiliary Agents (合併相似功能)

### 長期目標 (1-2 月)
1. ✅ 完整的依賴注入框架
2. ✅ 統一的測試框架
3. ✅ 插件化 Agent 架構
4. ✅ 完整的監控與追蹤系統

---

## 📋 重構任務清單

### Phase 1: 建立 Service Layer (優先級: 🔴 最高)

#### Task 1.1: 統一 LLM Service
**估計時間**: 2-3 天

**目標**: 所有 Agent 通過統一的 Service 訪問 LLM

**新增檔案**:
```
services/
  llm_service.py         # 統一的 LLM 服務
  llm_factory.py         # LLM Provider 工廠
  prompt_manager.py      # Prompt 模板管理
```

**核心設計**:
```python
# services/llm_service.py
class LLMService:
    """統一的 LLM 服務層"""
    
    def __init__(self, config: Config):
        self.config = config
        self.provider = self._create_provider()
        self.token_tracker = TokenUsageTracker()
    
    def _create_provider(self):
        """根據配置創建 LLM Provider"""
        if self.config.LLM_PROVIDER == "openai":
            return ChatOpenAI(...)
        elif self.config.LLM_PROVIDER == "anthropic":
            return ChatAnthropic(...)
        # ... 支持多個 Provider
    
    async def generate(
        self, 
        prompt: str, 
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> str:
        """統一的生成接口"""
        # 追蹤 Token 使用
        # 錯誤處理
        # 重試邏輯
        # 快取
        pass
    
    def get_usage_stats(self) -> Dict:
        """獲取 Token 使用統計"""
        pass
```

**修改範圍**:
- ✅ 修改 `base_agent.py`，注入 `llm_service`
- ✅ 重構所有 19 個 Agent 的 `__init__` 方法
- ✅ 移除重複的 LLM 初始化代碼

**預期收益**:
- 減少 **400+ 行** 重複代碼
- 集中管理 Token 使用
- 方便切換 LLM Provider
- 統一錯誤處理與重試


---

#### Task 1.2: 統一 RAG Service
**估計時間**: 2-3 天

**目標**: 提取重複的 RAG 查詢邏輯

**新增檔案**:
```
services/
  rag_service.py         # 統一的 RAG 查詢服務
  rag_strategies.py      # RAG 查詢策略 (單庫/多庫/智能路由)
```

**核心設計**:
```python
# services/rag_service.py
class RAGService:
    """統一的 RAG 查詢服務"""
    
    def __init__(self, vectordb_manager):
        self.db_manager = vectordb_manager
        self.cache = {}  # 查詢快取
    
    async def query(
        self,
        query: str,
        strategy: RAGStrategy = RAGStrategy.AUTO,
        top_k: int = 5,
        threshold: float = 0.3,
        databases: List[str] = None
    ) -> RAGResult:
        """統一的查詢接口"""
        
        # 1. 策略選擇
        if strategy == RAGStrategy.AUTO:
            strategy = self._auto_select_strategy(query)
        
        # 2. 執行查詢
        if strategy == RAGStrategy.SINGLE_DB:
            return await self._query_single(query, databases[0])
        elif strategy == RAGStrategy.MULTI_DB:
            return await self._query_multi(query, databases)
        elif strategy == RAGStrategy.SMART_ROUTING:
            return await self._smart_routing(query)
    
    async def _query_multi(self, query: str, databases: List[str]) -> RAGResult:
        """多數據庫查詢（提取自 chat_router.py）"""
        # 將現有的 get_rag_context() 邏輯移到這裡
        pass

class RAGResult(BaseModel):
    """統一的 RAG 結果格式"""
    query: str
    context: str
    sources: List[Source]
    strategy_used: str
    databases_queried: List[str]
    total_results: int
    avg_relevance: float
```

**修改範圍**:
- ✅ 移除 `chat_router.py::get_rag_context()` (193 行)
- ✅ 移除 `ws_chat_router.py::rag_search_tool()` (96 行)
- ✅ 修改 `rag_agent.py`，使用統一的 Service
- ✅ 更新所有調用 RAG 的地方

**預期收益**:
- 減少 **300+ 行** 重複代碼
- 統一 RAG 查詢邏輯
- 方便實現查詢快取
- 方便 A/B 測試不同策略


---

#### Task 1.3: 統一 Broadcasting Service
**估計時間**: 1-2 天

**目標**: 統一 WebSocket 廣播機制

**新增檔案**:
```
services/
  broadcast_service.py   # 統一的廣播服務
```

**核心設計**:
```python
# services/broadcast_service.py
class BroadcastService:
    """統一的 WebSocket 廣播服務"""
    
    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
    
    async def broadcast_agent_status(
        self,
        agent_name: str,
        status: str,
        task_id: str,
        data: Dict[str, Any]
    ):
        """廣播 Agent 狀態更新"""
        await self.ws_manager.broadcast_agent_activity({
            "type": f"{agent_name}_{status}",
            "agent": agent_name,
            "task_id": task_id,
            "content": data,
            "timestamp": datetime.now().isoformat()
        })
    
    async def broadcast_thinking_step(
        self,
        agent_name: str,
        step_number: int,
        thought: str,
        action: str = None
    ):
        """廣播思考步驟"""
        # ...
    
    async def broadcast_plan_update(self, plan: ExecutionPlan):
        """廣播計劃更新"""
        # ...
```

**修改範圍**:
- ✅ 修改 `base_agent.py`，注入 `broadcast_service`
- ✅ 移除各個 Agent 中的 `_broadcast_status()` 方法
- ✅ 移除 Router 中的重複廣播邏輯

**預期收益**:
- 減少 **200+ 行** 重複代碼
- 統一廣播格式
- 方便實現廣播過濾、限流


---

### Phase 2: Agent 重構 (優先級: 🟡 高)

#### Task 2.1: 整合 Manager Agent
**估計時間**: 3-4 天

**問題**: 兩個版本並存，功能重疊

**解決方案**:
1. **分析差異**
   - `manager_agent.py`: 傳統 Planning-Driven 模式
   - `manager_agent_v2.py`: Agentic Orchestrator 模式

2. **整合策略**
   - 保留 `manager_agent_v2.py` 作為主版本
   - 將 `manager_agent.py` 中的 Fallback 邏輯整合進去
   - 刪除 `manager_agent.py`

3. **重構步驟**
   ```
   1. 將 manager_agent.py 的特殊功能移到 manager_agent_v2.py
   2. 更新所有引用 manager_agent 的代碼
   3. 測試完整流程
   4. 刪除 manager_agent.py
   ```

**預期收益**:
- 減少 **1721 行** 冗餘代碼
- 統一管理邏輯
- 降低維護成本


---

#### Task 2.2: 簡化 Auxiliary Agents
**估計時間**: 2-3 天

**問題**: 多個相似的小 Agent

**解決方案**:
合併功能相似的 Agent 為 **Tool Agent**

**整合方案**:
```python
# agents/auxiliary/tool_agent.py (重構版)
class ToolAgent(BaseAgent):
    """統一的工具型 Agent"""
    
    def __init__(self):
        super().__init__(...)
        
        # 註冊所有工具
        self.tools = {
            "calculate": CalculationTool(),
            "translate": TranslationTool(),
            "summarize": SummarizationTool(),
            "parse_data": DataParsingTool(),
        }
    
    async def process_task(self, task: TaskAssignment):
        tool_name = task.task_type
        tool = self.tools.get(tool_name)
        
        if tool:
            return await tool.execute(task.input_data)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

# 每個工具變成一個 Tool Class
class CalculationTool:
    async def execute(self, input_data: Dict) -> Dict:
        # 原 calculation_agent 的邏輯
        pass
```

**整合清單**:
- ✅ `calculation_agent.py` → `CalculationTool`
- ✅ `translate_agent.py` → `TranslationTool`
- ✅ `summarize_agent.py` → `SummarizationTool`
- ✅ `data_agent.py` → `DataParsingTool`

**預期收益**:
- 減少 **4 個** Agent 文件
- 統一工具調用接口
- 方便動態添加/移除工具


---

#### Task 2.3: Prompt 外部化
**估計時間**: 2-3 天

**問題**: System Prompt 硬編碼在各個 Agent 中

**解決方案**:
建立統一的 Prompt 管理系統

**新增檔案**:
```
config/
  prompts/
    casual_chat.yaml
    rag_agent.yaml
    thinking_agent.yaml
    manager.yaml
    tools.yaml
```

**範例格式**:
```yaml
# config/prompts/casual_chat.yaml
agent_name: casual_chat_agent

system_prompt: |
  You are a friendly AI assistant having a casual conversation.
  
  ## CRITICAL LANGUAGE RULE (MUST FOLLOW):
  You MUST respond in the SAME LANGUAGE as the user's message.
  
  ## Guidelines:
  - Be warm, friendly, and conversational
  - Keep responses brief and natural (1-3 sentences)

capabilities_response:
  zh: |
    我可以幫助你：
    - 回答問題和對話
    - 搜索知識庫
    - 規劃和分析
  
  en: |
    I can help you with:
    - Answering questions and chatting
    - Searching knowledge bases
    - Planning and analysis

temperature: 0.7
max_tokens: 256
```

**Prompt Manager**:
```python
# services/prompt_manager.py
class PromptManager:
    """Prompt 模板管理器"""
    
    def __init__(self, prompts_dir: str = "config/prompts"):
        self.prompts_dir = prompts_dir
        self.cache = {}
    
    def get_prompt(self, agent_name: str) -> PromptTemplate:
        """獲取 Agent 的 Prompt 模板"""
        if agent_name not in self.cache:
            self.cache[agent_name] = self._load_prompt(agent_name)
        return self.cache[agent_name]
    
    def _load_prompt(self, agent_name: str) -> PromptTemplate:
        """從 YAML 加載 Prompt"""
        file_path = f"{self.prompts_dir}/{agent_name}.yaml"
        with open(file_path) as f:
            data = yaml.safe_load(f)
        return PromptTemplate(**data)
```

**修改範圍**:
- ✅ 將所有 Agent 的 System Prompt 提取到 YAML
- ✅ 修改 Agent 初始化邏輯，從 PromptManager 讀取
- ✅ 支持 Prompt 版本控制與 A/B 測試

**預期收益**:
- Prompt 集中管理
- 方便調整與實驗
- 支持多語言版本
- 版本控制與回滾


---

### Phase 3: Router 重構 (優先級: 🟡 中)

#### Task 3.1: 提取業務邏輯到 Service Layer
**估計時間**: 3-4 天

**問題**: Router 包含太多業務邏輯

**解決方案**:
建立 **Chat Service** 統一處理聊天邏輯

**新增檔案**:
```
services/
  chat_service.py        # 統一的聊天處理服務
```

**核心設計**:
```python
# services/chat_service.py
class ChatService:
    """統一的聊天處理服務"""
    
    def __init__(
        self,
        llm_service: LLMService,
        rag_service: RAGService,
        broadcast_service: BroadcastService,
        registry: AgentRegistry
    ):
        self.llm = llm_service
        self.rag = rag_service
        self.broadcast = broadcast_service
        self.registry = registry
    
    async def process_message(
        self,
        message: str,
        session_id: str,
        user_id: str,
        use_rag: bool = True,
        enable_memory: bool = True
    ) -> ChatResponse:
        """
        統一的消息處理入口
        
        這裡整合了：
        - Entry Classifier 邏輯
        - 記憶處理
        - RAG 查詢
        - Agent 調度
        """
        # 1. 加載用戶上下文
        user_context = await self._get_user_context(user_id, enable_memory)
        
        # 2. Entry Classifier 分類
        classification = await self._classify_intent(message, user_context)
        
        # 3. 路由到對應的處理流程
        if classification.is_casual:
            return await self._handle_casual_chat(message, user_context)
        else:
            return await self._handle_task(message, user_context, use_rag)
    
    async def _handle_task(self, message: str, context: str, use_rag: bool):
        """處理任務型請求（原 process_chat_task 邏輯）"""
        # ...
```

**修改範圍**:
- ✅ 提取 `chat_router.py::process_chat_task()` (800+ 行) 到 Service
- ✅ 提取 `ws_chat_router.py::process_chat_stream()` (300+ 行) 到 Service
- ✅ Router 只負責參數解析與調用 Service

**重構後的 Router**:
```python
# fast_api/routers/chat_router.py (簡化版)
@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """聊天接口（簡化版）"""
    
    chat_service = get_chat_service()
    
    try:
        response = await chat_service.process_message(
            message=request.message,
            session_id=request.conversation_id,
            user_id=request.user_id,
            use_rag=request.use_rag,
            enable_memory=request.enable_memory
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**預期收益**:
- Router 代碼減少 **70%**
- 業務邏輯統一
- REST 和 WebSocket 共用相同邏輯
- 方便單元測試


---

### Phase 4: 配置外部化 (優先級: 🟢 中低)

#### Task 4.1: Agent 配置外部化
**估計時間**: 2 天

**新增檔案**:
```
config/
  agents/
    manager.yaml
    rag.yaml
    thinking.yaml
    casual_chat.yaml
    tools.yaml
```

**範例格式**:
```yaml
# config/agents/manager.yaml
agent_name: manager_agent
agent_role: Agentic Manager
description: Central coordinator with metacognition

llm_config:
  temperature: 0.2
  max_tokens: 2000
  model: gpt-4o-mini

capabilities:
  can_interrupt: true
  priority: 1
  max_concurrent_tasks: 5

agent_mapping:
  rag_agent:
    tasks: [search_knowledge, retrieve_documents]
    description: Search uploaded documents and knowledge bases
  
  thinking_agent:
    tasks: [analyze, reason, evaluate]
    description: Deep reasoning and analysis
  
  calculation_agent:
    tasks: [calculate, compute, math]
    description: Mathematical calculations
```

**修改範圍**:
- ✅ 移除 `manager_agent_v2.py` 第 156 行的硬編碼 `agent_capabilities`
- ✅ 建立 Agent Config Loader
- ✅ 所有 Agent 從配置檔案讀取參數

**預期收益**:
- 配置與代碼分離
- 方便調整 Agent 行為
- 支持動態添加/移除 Agent


---

### Phase 5: 依賴注入與測試 (優先級: 🟢 低)

#### Task 5.1: 實現依賴注入
**估計時間**: 3-5 天

**目標**: 降低耦合度，方便測試

**新增檔案**:
```
services/
  dependency_injection.py   # DI 容器
```

**核心設計**:
```python
# services/dependency_injection.py
class DIContainer:
    """依賴注入容器"""
    
    def __init__(self):
        self._services = {}
        self._singletons = {}
    
    def register(self, interface: type, implementation: type, singleton: bool = True):
        """註冊服務"""
        self._services[interface] = implementation
        if singleton:
            self._singletons[interface] = None
    
    def resolve(self, interface: type):
        """解析依賴"""
        if interface in self._singletons:
            if self._singletons[interface] is None:
                self._singletons[interface] = self._services[interface]()
            return self._singletons[interface]
        else:
            return self._services[interface]()

# 使用範例
container = DIContainer()
container.register(LLMService, LLMService, singleton=True)
container.register(RAGService, RAGService, singleton=True)

# Agent 初始化
class ThinkingAgent(BaseAgent):
    def __init__(self, llm_service: LLMService, rag_service: RAGService):
        self.llm = llm_service
        self.rag = rag_service
```

**修改範圍**:
- ✅ 修改所有 Agent 的 `__init__` 支持依賴注入
- ✅ 建立 Service 註冊邏輯
- ✅ 更新 `main.py` 初始化流程

**預期收益**:
- 方便單元測試 (可以注入 Mock)
- 降低耦合度
- 支持不同環境配置


---

#### Task 5.2: 建立測試框架
**估計時間**: 3-5 天

**新增檔案**:
```
tests/
  unit/
    test_llm_service.py
    test_rag_service.py
    test_chat_service.py
    agents/
      test_manager_agent.py
      test_rag_agent.py
  
  integration/
    test_chat_flow.py
    test_websocket_flow.py
  
  mocks/
    mock_llm.py
    mock_vectordb.py
```

**範例測試**:
```python
# tests/unit/test_llm_service.py
import pytest
from services.llm_service import LLMService
from tests.mocks.mock_llm import MockLLM

@pytest.fixture
def llm_service():
    config = Config()
    service = LLMService(config)
    service.provider = MockLLM()  # 注入 Mock
    return service

async def test_generate_response(llm_service):
    response = await llm_service.generate("Hello")
    assert len(response) > 0
    assert llm_service.token_tracker.total_tokens > 0
```

**預期收益**:
- 提高代碼品質
- 快速發現問題
- 支持持續集成


---

## 📈 預期成果

### 代碼量減少
- **Phase 1**: 減少 ~900 行重複代碼
- **Phase 2**: 減少 ~2000 行冗餘代碼
- **Phase 3**: 減少 ~700 行業務邏輯重複
- **總計**: 減少 **3600+ 行** (約 24% 代碼量)

### 維護性提升
- ✅ 統一的 Service Layer，修改一處即可影響全局
- ✅ 配置外部化，無需修改代碼即可調整行為
- ✅ 依賴注入，方便單元測試

### 擴展性提升
- ✅ 插件化 Agent 架構，方便添加新 Agent
- ✅ 統一的 LLM Service，輕鬆切換 Provider
- ✅ 統一的 RAG Service，方便實驗新策略

---

## 🚀 執行計劃

### 時間線
- **Week 1-2**: Phase 1 (Service Layer)
- **Week 3-4**: Phase 2 (Agent 重構)
- **Week 5-6**: Phase 3 (Router 重構)
- **Week 7-8**: Phase 4 (配置外部化)
- **Week 9-12**: Phase 5 (DI 與測試)

### 執行原則
1. **逐步重構**: 每次只改一個模組，確保系統可運行
2. **先寫測試**: 重構前先寫測試，確保行為不變
3. **保留舊代碼**: 重構完成前保留舊代碼，方便回滾
4. **持續集成**: 每次提交都跑測試，確保沒有破壞功能

### 風險控制
- ✅ 每個 Phase 完成後進行完整測試
- ✅ 使用 Feature Flag 控制新舊代碼切換
- ✅ 保留完整的 Git 歷史，方便回滾

---

## 📝 注意事項

### 不要做的事情
1. ❌ **不要一次性重構所有代碼** - 風險太大
2. ❌ **不要改變 API 接口** - 會影響前端
3. ❌ **不要刪除功能** - 除非確認沒人用
4. ❌ **不要在重構時加新功能** - 一次只做一件事

### 必須做的事情
1. ✅ **每次重構前先寫測試** - 確保行為不變
2. ✅ **每次提交都要能運行** - 不能破壞系統
3. ✅ **保持文檔同步** - 更新 README 和註釋
4. ✅ **Code Review** - 重要的重構要有人 Review

---

## 🎁 額外收益

完成重構後，未來可以輕鬆實現：

1. **多租戶支持** (Task 1.1 + 4.1)
   - 不同公司使用不同的 LLM Config
   - 不同公司使用不同的 Prompt

2. **A/B 測試** (Task 1.2)
   - 測試不同的 RAG 策略
   - 測試不同的 Prompt 版本

3. **成本優化** (Task 1.1)
   - 統一的 Token 追蹤
   - 智能的 LLM 選擇 (便宜的用 GPT-3.5，複雜的用 GPT-4)

4. **快速整合新 Agent** (Phase 2.2)
   - 只需實現一個 Tool Class
   - 自動註冊到系統中

5. **無縫切換 LLM Provider** (Task 1.1)
   - 從 OpenAI 切換到 Anthropic 只需改配置

---

## 結論

這份計劃書提供了一個**漸進式、低風險**的重構路徑。重點是：

1. **先建立 Service Layer** - 這是最大的收益點
2. **整合重複的 Agent** - 減少維護負擔
3. **配置外部化** - 提高靈活性
4. **依賴注入** - 提高可測試性

建議從 **Phase 1** 開始，一步一步執行，不要急於求成。
