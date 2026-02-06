/**
 * ThinkingSteps 組件
 * 
 * 使用舊版 UI 樣式 + 可展開箭頭 + 支持 UnifiedEvent
 * 
 * 功能：
 * 1. 即時顯示 Agent 處理流程（WS 事件）
 * 2. 回應完成後，步驟保存在消息下方
 * 3. 每個步驟可展開查看詳細內容
 */

import React, { useState } from 'react';

// ============================================================
// 類型定義
// ============================================================

interface ThinkingStep {
  // 支持舊版格式
  type?: string;
  agent?: string;
  content?: string;
  status?: string;
  timestamp?: string;
  
  // 支持 UnifiedEvent 格式
  stage?: string;
  event_type?: string;
  data?: Record<string, any>;
  ui?: {
    color?: string;
    icon?: string;
    animate?: boolean;
  };
  agent_info?: {
    name?: string;
    role?: string;
    icon?: string;
  };
}

interface ThinkingStepsProps {
  steps: ThinkingStep[];
  isProcessing?: boolean;
  compact?: boolean;      // true = 嵌入消息下方模式
}

// ============================================================
// 圖標映射
// ============================================================

const STAGE_ICONS: Record<string, string> = {
  init: '📋',
  classifying: '🏷️',
  planning: '📝',
  retrieval: '🔍',
  executing: '⚙️',
  synthesis: '✨',
  complete: '✅',
  failed: '❌',
  // 舊版兼容
  thinking: '💭',
  searching: '🔍',
  analyzing: '🧠',
};

const AGENT_ICONS: Record<string, string> = {
  manager_agent: '🧠',
  manager: '🧠',
  planning_agent: '📝',
  planning: '📝',
  thinking_agent: '💭',
  thinking: '💭',
  rag_agent: '🔍',
  rag: '🔍',
  casual_chat_agent: '💬',
  casual_chat: '💬',
  sw_agent: '🔧',
  entry_classifier: '🏷️',
  system: '📋',
  calculation_agent: '🧮',
  translate_agent: '🌐',
  summarize_agent: '📄',
  data_agent: '📊',
  memory_capture_agent: '🧠',
};

const STAGE_COLORS: Record<string, string> = {
  init: '#6b7280',
  classifying: '#8b5cf6',
  planning: '#f59e0b',
  retrieval: '#10b981',
  executing: '#3b82f6',
  synthesis: '#6366f1',
  complete: '#22c55e',
  failed: '#ef4444',
};

// ============================================================
// 單個步驟組件
// ============================================================

interface StepItemProps {
  step: ThinkingStep;
  index: number;
  isLast: boolean;
  isProcessing: boolean;
}

const StepItem: React.FC<StepItemProps> = ({ step, index, isLast, isProcessing }) => {
  const [expanded, setExpanded] = useState(false);

  // 標準化欄位（兼容舊版和 UnifiedEvent）
  const agentName = step.agent_info?.name || step.agent || 'system';
  const stage = step.stage || step.type || 'executing';
  const message = step.content || step.status || '';
  const icon = AGENT_ICONS[agentName] || STAGE_ICONS[stage] || '▶️';
  const color = step.ui?.color || STAGE_COLORS[stage] || '#3b82f6';

  // 判斷是否有詳細資料
  const hasDetails = step.data && Object.keys(step.data).length > 0;
  const isAnimating = isLast && isProcessing && (step.ui?.animate !== false);

  return (
    <div className="thinking-step-item">
      {/* 時間線連接線 */}
      <div className="step-timeline">
        <div 
          className={`step-dot ${isAnimating ? 'step-dot-pulse' : ''}`}
          style={{ backgroundColor: color }}
        />
        {!isLast && <div className="step-line" />}
      </div>

      {/* 步驟內容 */}
      <div className="step-content">
        {/* 標題行 - 可點擊展開 */}
        <div 
          className={`step-header ${hasDetails ? 'step-clickable' : ''}`}
          onClick={() => hasDetails && setExpanded(!expanded)}
        >
          {/* 展開箭頭 */}
          {hasDetails && (
            <span className="step-arrow">
              {expanded ? '▼' : '▶'}
            </span>
          )}

          {/* 圖標 + Agent 名稱 */}
          <span className="step-icon">{icon}</span>
          <span className="step-agent" style={{ color }}>
            {step.agent_info?.role || agentName}
          </span>
          
          {/* 消息內容 */}
          <span className="step-message">
            {message}
          </span>

          {/* 動畫指示器 */}
          {isAnimating && (
            <span className="step-spinner">⏳</span>
          )}
        </div>

        {/* 展開的詳細內容 */}
        {expanded && hasDetails && (
          <div className="step-details">
            <pre className="step-details-json">
              {JSON.stringify(step.data, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================
// 主組件：即時顯示模式（WS 事件進行中）
// ============================================================

export const LiveThinkingSteps: React.FC<ThinkingStepsProps> = ({ 
  steps, 
  isProcessing = false 
}) => {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="thinking-steps-live">
      <div className="thinking-steps-header">
        <span className="thinking-steps-title">
          {isProcessing ? '🔄 處理中...' : '✅ 處理完成'}
        </span>
      </div>
      <div className="thinking-steps-list">
        {steps.map((step, i) => (
          <StepItem
            key={i}
            step={step}
            index={i}
            isLast={i === steps.length - 1}
            isProcessing={isProcessing}
          />
        ))}
      </div>
    </div>
  );
};

// ============================================================
// 主組件：消息內嵌模式（回應完成後）
// ============================================================

export const MessageThinkingSteps: React.FC<ThinkingStepsProps> = ({
  steps,
  compact = true
}) => {
  const [isOpen, setIsOpen] = useState(false);
  
  if (!steps || steps.length === 0) return null;

  return (
    <div className="message-thinking-steps">
      {/* 折疊按鈕 */}
      <button
        className="thinking-toggle-btn"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="thinking-toggle-arrow">
          {isOpen ? '▼' : '▶'}
        </span>
        <span className="thinking-toggle-icon">🧠</span>
        <span className="thinking-toggle-text">
          處理步驟 ({steps.length})
        </span>
      </button>

      {/* 展開的步驟列表 */}
      {isOpen && (
        <div className="thinking-steps-expanded">
          {steps.map((step, i) => (
            <StepItem
              key={i}
              step={step}
              index={i}
              isLast={i === steps.length - 1}
              isProcessing={false}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default LiveThinkingSteps;