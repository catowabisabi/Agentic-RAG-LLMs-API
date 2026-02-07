/**
 * EventTimeline Component
 * 
 * 使用 UnifiedEvents 顯示處理時間線
 */

import React from 'react';
import {
  UnifiedEvent,
  Stage,
  STAGE_COLORS,
  getAgentInfo,
  isThinkingEvent,
} from '@/types/unified-event';

interface EventTimelineProps {
  events: UnifiedEvent[];
  currentStage: Stage;
  isProcessing: boolean;
}

// 圖標映射（使用 Lucide React 或類似庫）
const STAGE_ICONS: Record<Stage, string> = {
  init: '📥',
  classifying: '🏷️',
  planning: '📋',
  retrieval: '🔍',
  executing: '⚙️',
  synthesis: '✨',
  complete: '✅',
  failed: '❌',
};

export function EventTimeline({ events, currentStage, isProcessing }: EventTimelineProps) {
  // 只顯示 timeline 事件
  const timelineEvents = events.filter(e => e.ui.show_in_timeline);
  
  return (
    <div className="event-timeline">
      {/* 當前階段指示器 */}
      {isProcessing && (
        <div 
          className="current-stage-indicator"
          style={{ 
            backgroundColor: STAGE_COLORS[currentStage],
            animation: 'pulse 2s infinite'
          }}
        >
          {STAGE_ICONS[currentStage]} {currentStage}
        </div>
      )}
      
      {/* 時間線 */}
      <div className="timeline-container">
        {timelineEvents.map((event, index) => (
          <TimelineItem 
            key={event.event_id} 
            event={event} 
            isLast={index === timelineEvents.length - 1}
          />
        ))}
      </div>
    </div>
  );
}

interface TimelineItemProps {
  event: UnifiedEvent;
  isLast: boolean;
}

function TimelineItem({ event, isLast }: TimelineItemProps) {
  const agentInfo = getAgentInfo(event.agent.name);
  const isThinking = isThinkingEvent(event);
  
  // Defensive check: ensure we only use string properties from agentInfo
  const agentRole = typeof agentInfo.role === 'string' ? agentInfo.role : 'Agent';
  
  return (
    <div 
      className={`timeline-item ${isLast ? 'latest' : ''} ${isThinking ? 'thinking' : ''}`}
      style={{ borderLeftColor: event.ui.color }}
    >
      {/* 圖標 */}
      <div 
        className="timeline-icon"
        style={{ backgroundColor: event.ui.color }}
      >
        {STAGE_ICONS[event.stage]}
      </div>
      
      {/* 內容 */}
      <div className="timeline-content">
        <div className="timeline-header">
          <span className="agent-name">{agentRole}</span>
          <span className="timestamp">
            {new Date(event.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <div className="timeline-message">
          {event.content.message}
        </div>
        
        {/* 來源（如果有） */}
        {event.content.sources.length > 0 && (
          <div className="timeline-sources">
            📚 {event.content.sources.length} 個來源
          </div>
        )}
      </div>
      
      {/* 動畫指示器 */}
      {event.ui.animate && isLast && (
        <div className="processing-indicator">
          <div className="dot" />
          <div className="dot" />
          <div className="dot" />
        </div>
      )}
    </div>
  );
}

// 進度條組件
interface StageProgressProps {
  currentStage: Stage;
  isProcessing: boolean;
}

export function StageProgress({ currentStage, isProcessing }: StageProgressProps) {
  const stages: Stage[] = ['init', 'classifying', 'planning', 'retrieval', 'executing', 'synthesis', 'complete'];
  const currentIndex = stages.indexOf(currentStage);
  
  return (
    <div className="stage-progress">
      {stages.map((stage, index) => {
        const isActive = index === currentIndex && isProcessing;
        const isCompleted = index < currentIndex;
        const isFuture = index > currentIndex;
        
        return (
          <React.Fragment key={stage}>
            <div 
              className={`stage-dot ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''} ${isFuture ? 'future' : ''}`}
              style={{ 
                backgroundColor: isCompleted ? STAGE_COLORS.complete : 
                                isActive ? STAGE_COLORS[stage] : 
                                '#e5e7eb'
              }}
              title={stage}
            >
              {isCompleted && '✓'}
              {isActive && STAGE_ICONS[stage]}
            </div>
            {index < stages.length - 1 && (
              <div 
                className={`stage-connector ${isCompleted ? 'completed' : ''}`}
                style={{ 
                  backgroundColor: isCompleted ? STAGE_COLORS.complete : '#e5e7eb'
                }}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

export default EventTimeline;
