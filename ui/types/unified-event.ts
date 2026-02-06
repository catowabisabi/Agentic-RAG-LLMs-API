/**
 * 統一事件類型定義 (Unified Event Types)
 *
 * 所有 WebSocket 事件都使用此結構
 */

// ============================================================
// 枚舉
// ============================================================

export type EventType =
  | "init"
  | "thinking"
  | "status"
  | "progress"
  | "stream"
  | "result"
  | "error";

export type Stage =
  | "init"
  | "classifying"
  | "planning"
  | "retrieval"
  | "executing"
  | "synthesis"
  | "complete"
  | "failed";

// ============================================================
// 子類型
// ============================================================

export interface AgentInfo {
  name: string;
  role: string;
  icon: string;
}

export interface TokenInfo {
  prompt: number;
  completion: number;
  total: number;
  cost: number;
}

export interface ContentData {
  message: string;
  data: Record<string, unknown>;
  sources: Array<{
    title?: string;
    content?: string;
    score?: number;
    [key: string]: unknown;
  }>;
  tokens?: TokenInfo | null;
  answer?: string | null;
}

export interface UIHints {
  color: string;
  icon: string;
  priority: number;
  dismissible: boolean;
  show_in_timeline: boolean;
  animate: boolean;
}

export interface EventMetadata {
  intent?: string | null;
  handler?: string | null;
  matched_by?: string | null;
  duration_ms?: number | null;
  step_index?: number | null;
  total_steps?: number | null;
}

// ============================================================
// 主類型
// ============================================================

export interface UnifiedEvent {
  // 識別欄位
  event_id: string;
  session_id: string;
  task_id: string;
  conversation_id?: string | null;

  // 事件類型
  type: EventType;
  stage: Stage;

  // 詳細資訊
  agent: AgentInfo;
  content: ContentData;
  ui: UIHints;
  metadata: EventMetadata;

  // 時間戳
  timestamp: string;
}

// ============================================================
// 時間線項目（簡化版，用於側邊欄）
// ============================================================

export interface TimelineItem {
  event_id: string;
  type: EventType;
  stage: Stage;
  agent: string;
  message: string;
  timestamp: string;
  ui: UIHints;
}

// ============================================================
// 事件過濾器
// ============================================================

export interface EventFilter {
  types?: EventType[];
  stages?: Stage[];
  agents?: string[];
  from?: Date;
  to?: Date;
}

// ============================================================
// 預設 Agent 配置
// ============================================================

export const AGENT_CONFIG: Record<string, AgentInfo> = {
  manager_agent: { name: "manager_agent", role: "協調者", icon: "brain" },
  planning_agent: { name: "planning_agent", role: "規劃師", icon: "clipboard-list" },
  thinking_agent: { name: "thinking_agent", role: "思考者", icon: "lightbulb" },
  rag_agent: { name: "rag_agent", role: "檢索專家", icon: "search" },
  casual_chat_agent: { name: "casual_chat_agent", role: "對話助手", icon: "message-circle" },
  sw_agent: { name: "sw_agent", role: "SolidWorks 專家", icon: "cube" },
  calculation_agent: { name: "calculation_agent", role: "計算專家", icon: "calculator" },
  translate_agent: { name: "translate_agent", role: "翻譯專家", icon: "globe" },
  summarize_agent: { name: "summarize_agent", role: "摘要專家", icon: "file-text" },
  data_agent: { name: "data_agent", role: "資料分析師", icon: "bar-chart" },
  entry_classifier: { name: "entry_classifier", role: "分類器", icon: "tag" },
  system: { name: "system", role: "系統", icon: "server" },
};

// ============================================================
// Stage 顏色配置
// ============================================================

export const STAGE_COLORS: Record<Stage, string> = {
  init: "#6b7280",
  classifying: "#8b5cf6",
  planning: "#f59e0b",
  retrieval: "#10b981",
  executing: "#3b82f6",
  synthesis: "#6366f1",
  complete: "#22c55e",
  failed: "#ef4444",
};

// ============================================================
// 類型守衛
// ============================================================

export function isUnifiedEvent(obj: unknown): obj is UnifiedEvent {
  if (typeof obj !== "object" || obj === null) return false;
  const e = obj as Record<string, unknown>;
  return (
    typeof e.event_id === "string" &&
    typeof e.session_id === "string" &&
    typeof e.task_id === "string" &&
    typeof e.type === "string" &&
    typeof e.stage === "string"
  );
}

// ============================================================
// 輔助函數
// ============================================================

export function getAgentInfo(agentName: string): AgentInfo {
  return (
    AGENT_CONFIG[agentName] || {
      name: agentName,
      role: "Agent",
      icon: "bot",
    }
  );
}

export function getStageColor(stage: Stage): string {
  return STAGE_COLORS[stage] || "#6b7280";
}

export function isTerminalEvent(event: UnifiedEvent): boolean {
  return event.type === "result" || event.type === "error";
}

export function isThinkingEvent(event: UnifiedEvent): boolean {
  return event.type === "thinking" || event.type === "status";
}
