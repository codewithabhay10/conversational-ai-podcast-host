"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import type { ChatMessage } from "@/lib/api";

interface WebSocketChatHook {
  messages: ChatMessage[];
  streamingContent: string;
  isStreaming: boolean;
  isConnected: boolean;
  sendMessage: (text: string) => void;
  startTopic: (topic: string, topicContext?: string) => void;
  reconnect: () => void;
  /** Register a callback for sentence events (fired as each sentence completes during streaming) */
  onSentence: (cb: ((sentence: string) => void) | null) => void;
}

export function useWebSocketChat(): WebSocketChatHook {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const historyRef = useRef<ChatMessage[]>([]);
  const topicRef = useRef("");
  const topicContextRef = useRef("");
  const reconnectTimerRef = useRef<NodeJS.Timeout>();
  const sentenceCallbackRef = useRef<((sentence: string) => void) | null>(null);

  /** Register a callback invoked for each server-side sentence event */
  const onSentence = useCallback(
    (cb: ((sentence: string) => void) | null) => {
      sentenceCallbackRef.current = cb;
    },
    []
  );

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    // In dev, connect to FastAPI directly; in prod, use same host
    const host =
      process.env.NODE_ENV === "development" ? "localhost:8000" : window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/ws/chat`);

    ws.onopen = () => {
      setIsConnected(true);
      console.log("WebSocket connected");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case "token":
          setIsStreaming(true);
          setStreamingContent((prev) => prev + data.content);
          break;

        case "sentence":
          // Server detected a complete sentence — fire TTS callback immediately
          if (sentenceCallbackRef.current) {
            sentenceCallbackRef.current(data.content);
          }
          break;

        case "complete":
          setIsStreaming(false);
          const assistantMsg: ChatMessage = {
            role: "assistant",
            content: data.content,
          };
          setMessages((prev) => [...prev, assistantMsg]);
          historyRef.current = data.history || [];
          setStreamingContent("");
          break;

        case "error":
          setIsStreaming(false);
          setStreamingContent("");
          console.error("Server error:", data.message);
          const errorMsg: ChatMessage = {
            role: "assistant",
            content: `⚠️ ${data.message}`,
          };
          setMessages((prev) => [...prev, errorMsg]);
          break;
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log("WebSocket disconnected");
      // Auto-reconnect after 3 seconds
      reconnectTimerRef.current = setTimeout(() => connect(), 3000);
    };

    ws.onerror = (err) => {
      console.error("WebSocket error:", err);
    };

    wsRef.current = ws;
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback((text: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    if (!text.trim()) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);

    wsRef.current.send(
      JSON.stringify({
        type: "message",
        text,
        topic: topicRef.current,
        topicContext: topicContextRef.current,
        history: historyRef.current,
      })
    );
  }, []);

  const startTopic = useCallback(
    (topic: string, topicContext = "") => {
      topicRef.current = topic;
      topicContextRef.current = topicContext;

      setMessages([]);
      historyRef.current = [];
      setStreamingContent("");

      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connect();
        // Wait a moment for connection, then send
        setTimeout(() => {
          wsRef.current?.send(
            JSON.stringify({
              type: "start_topic",
              topic,
              topicContext,
            })
          );
        }, 500);
      } else {
        wsRef.current.send(
          JSON.stringify({
            type: "start_topic",
            topic,
            topicContext,
          })
        );
      }
    },
    [connect]
  );

  const reconnect = useCallback(() => {
    wsRef.current?.close();
    connect();
  }, [connect]);

  return {
    messages,
    streamingContent,
    isStreaming,
    isConnected,
    sendMessage,
    startTopic,
    reconnect,
    onSentence,
  };
}
