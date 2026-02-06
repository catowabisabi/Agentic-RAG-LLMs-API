/**
 * useUnifiedEvents Hook
 *
 * 提供統一事件處理的 React Hook
 */

import { useState, useEffect, useCallback, useRef } from "react";
import {
  UnifiedEvent,
  EventType,
  Stage,
  TimelineItem,
  EventFilter,
  isUnifiedEvent,
  isTerminalEvent,
} from "../types/unified-event";

// ============================================================
// Types
// ============================================================

export interface UseUnifiedEventsOptions {
  sessionId: string;
  onEvent?: (event: UnifiedEvent) => void;
  onResult?: (event: UnifiedEvent) => void;
  onError?: (event: UnifiedEvent) => void;
  filter?: EventFilter;
  maxEvents?: number;
}

export interface UnifiedEventsState {
  events: UnifiedEvent[];
  timeline: TimelineItem[];
  currentStage: Stage;
  isProcessing: boolean;
  latestResult: UnifiedEvent | null;
  latestError: UnifiedEvent | null;
}

export interface UseUnifiedEventsReturn extends UnifiedEventsState {
  // 方法
  clearEvents: () => void;
  getEventsByType: (type: EventType) => UnifiedEvent[];
  getEventsByStage: (stage: Stage) => UnifiedEvent[];
  getEventsByAgent: (agentName: string) => UnifiedEvent[];

  // 計算值
  thinkingEvents: UnifiedEvent[];
  statusEvents: UnifiedEvent[];
  sources: Array<{ title?: string; content?: string; score?: number }>;
  hasErrors: boolean;
}

// ============================================================
// Hook Implementation
// ============================================================

export function useUnifiedEvents(
  options: UseUnifiedEventsOptions
): UseUnifiedEventsReturn {
  const {
    sessionId,
    onEvent,
    onResult,
    onError,
    filter,
    maxEvents = 100,
  } = options;

  // State
  const [events, setEvents] = useState<UnifiedEvent[]>([]);
  const [currentStage, setCurrentStage] = useState<Stage>("init");
  const [isProcessing, setIsProcessing] = useState(false);
  const [latestResult, setLatestResult] = useState<UnifiedEvent | null>(null);
  const [latestError, setLatestError] = useState<UnifiedEvent | null>(null);

  // Refs for callbacks
  const onEventRef = useRef(onEvent);
  const onResultRef = useRef(onResult);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onEventRef.current = onEvent;
    onResultRef.current = onResult;
    onErrorRef.current = onError;
  }, [onEvent, onResult, onError]);

  // 處理收到的事件
  const handleEvent = useCallback(
    (event: UnifiedEvent) => {
      // 檢查 session_id 匹配
      if (event.session_id !== sessionId) {
        return;
      }

      // 應用過濾器
      if (filter) {
        if (filter.types && !filter.types.includes(event.type)) return;
        if (filter.stages && !filter.stages.includes(event.stage)) return;
        if (filter.agents && !filter.agents.includes(event.agent.name)) return;
      }

      // 更新 events
      setEvents((prev) => {
        const newEvents = [...prev, event];
        // 限制最大數量
        if (newEvents.length > maxEvents) {
          return newEvents.slice(-maxEvents);
        }
        return newEvents;
      });

      // 更新 stage
      setCurrentStage(event.stage);

      // 更新處理狀態
      if (event.type === "init" || event.type === "status") {
        setIsProcessing(true);
      }

      // 處理終結事件
      if (isTerminalEvent(event)) {
        setIsProcessing(false);

        if (event.type === "result") {
          setLatestResult(event);
          onResultRef.current?.(event);
        } else if (event.type === "error") {
          setLatestError(event);
          onErrorRef.current?.(event);
        }
      }

      // 觸發 onEvent callback
      onEventRef.current?.(event);
    },
    [sessionId, filter, maxEvents]
  );

  // 清除事件
  const clearEvents = useCallback(() => {
    setEvents([]);
    setCurrentStage("init");
    setIsProcessing(false);
    setLatestResult(null);
    setLatestError(null);
  }, []);

  // 按類型獲取事件
  const getEventsByType = useCallback(
    (type: EventType) => {
      return events.filter((e) => e.type === type);
    },
    [events]
  );

  // 按階段獲取事件
  const getEventsByStage = useCallback(
    (stage: Stage) => {
      return events.filter((e) => e.stage === stage);
    },
    [events]
  );

  // 按 Agent 獲取事件
  const getEventsByAgent = useCallback(
    (agentName: string) => {
      return events.filter((e) => e.agent.name === agentName);
    },
    [events]
  );

  // 計算時間線
  const timeline: TimelineItem[] = events
    .filter((e) => e.ui.show_in_timeline)
    .map((e) => ({
      event_id: e.event_id,
      type: e.type,
      stage: e.stage,
      agent: e.agent.name,
      message: e.content.message.slice(0, 100),
      timestamp: e.timestamp,
      ui: e.ui,
    }));

  // 計算思考事件
  const thinkingEvents = events.filter((e) => e.type === "thinking");

  // 計算狀態事件
  const statusEvents = events.filter((e) => e.type === "status");

  // 收集所有來源
  const sources = events.flatMap((e) => e.content.sources || []);

  // 是否有錯誤
  const hasErrors = events.some((e) => e.type === "error");

  return {
    // State
    events,
    timeline,
    currentStage,
    isProcessing,
    latestResult,
    latestError,

    // Methods
    clearEvents,
    getEventsByType,
    getEventsByStage,
    getEventsByAgent,

    // Computed
    thinkingEvents,
    statusEvents,
    sources,
    hasErrors,

    // 暴露 handleEvent 供外部使用
    handleEvent,
  } as UseUnifiedEventsReturn & { handleEvent: (event: UnifiedEvent) => void };
}

// ============================================================
// WebSocket 整合 Hook
// ============================================================

export function useUnifiedEventsWithWebSocket(
  wsUrl: string,
  options: Omit<UseUnifiedEventsOptions, "sessionId"> & { sessionId: string }
): UseUnifiedEventsReturn & {
  wsConnected: boolean;
  wsError: string | null;
} {
  const eventsHook = useUnifiedEvents(options);
  const [wsConnected, setWsConnected] = useState(false);
  const [wsError, setWsError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const handleEventRef = useRef(
    (eventsHook as unknown as { handleEvent: (e: UnifiedEvent) => void })
      .handleEvent
  );

  useEffect(() => {
    handleEventRef.current = (
      eventsHook as unknown as { handleEvent: (e: UnifiedEvent) => void }
    ).handleEvent;
  }, [eventsHook]);

  useEffect(() => {
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      setWsError(null);
      console.log("[UnifiedEvents] WebSocket connected");
    };

    ws.onclose = () => {
      setWsConnected(false);
      console.log("[UnifiedEvents] WebSocket disconnected");
    };

    ws.onerror = (error) => {
      setWsError("WebSocket connection error");
      console.error("[UnifiedEvents] WebSocket error:", error);
    };

    ws.onmessage = (messageEvent) => {
      try {
        const data = JSON.parse(messageEvent.data);

        // 檢查是否為統一事件
        if (isUnifiedEvent(data)) {
          handleEventRef.current(data);
        }
      } catch (e) {
        console.warn("[UnifiedEvents] Failed to parse WS message:", e);
      }
    };

    return () => {
      ws.close();
    };
  }, [wsUrl]);

  return {
    ...eventsHook,
    wsConnected,
    wsError,
  };
}

export default useUnifiedEvents;
