"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import TopicSelector from "@/components/TopicSelector";
import ChatMessages from "@/components/ChatMessages";
import ChatInput from "@/components/ChatInput";
import { useWebSocketChat } from "@/hooks/useWebSocketChat";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useTTS } from "@/hooks/useTTS";
import {
  fetchTopics,
  refreshTopics,
  fetchOllamaStatus,
  type Topic,
} from "@/lib/api";

type Screen = "topics" | "chat";

export default function Home() {
  const [screen, setScreen] = useState<Screen>("topics");
  const [topics, setTopics] = useState<Topic[]>([]);
  const [currentTopic, setCurrentTopic] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [ollamaStatus, setOllamaStatus] = useState<{
    connected: boolean;
    model?: string;
  }>({ connected: false });
  const [apiReachable, setApiReachable] = useState(true);

  const {
    messages,
    streamingContent,
    isStreaming,
    isConnected,
    sendMessage,
    startTopic,
    reconnect,
  } = useWebSocketChat();

  const {
    isListening,
    transcript,
    startListening,
    stopListening,
    isSupported: micSupported,
  } = useSpeechRecognition();

  const { speak: ttsSpeak, stop: ttsStop } = useTTS();
  const [autoSpeak, setAutoSpeak] = useState(true);
  const prevMsgCountRef = useRef(0);

  // Load topics & check status on mount
  useEffect(() => {
    const init = async () => {
      try {
        const [topicList, status] = await Promise.all([
          fetchTopics(),
          fetchOllamaStatus(),
        ]);
        setTopics(topicList);
        setOllamaStatus(status);
        setApiReachable(true);
      } catch {
        setApiReachable(false);
      }
    };
    init();
  }, []);

  // Auto-send transcript when mic stops
  useEffect(() => {
    if (!isListening && transcript) {
      ttsStop(); // stop any ongoing TTS before sending
      sendMessage(transcript);
    }
  }, [isListening, transcript, sendMessage, ttsStop]);

  // Auto-speak new assistant messages
  useEffect(() => {
    if (autoSpeak && messages.length > prevMsgCountRef.current) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg?.role === "assistant") {
        ttsSpeak(lastMsg.content);
      }
    }
    prevMsgCountRef.current = messages.length;
  }, [messages, autoSpeak, ttsSpeak]);

  const handleSelectTopic = useCallback(
    (topic: Topic) => {
      setCurrentTopic(topic.title);
      setScreen("chat");
      startTopic(topic.title, topic.summary || "");
    },
    [startTopic]
  );

  const handleRefreshTopics = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const newTopics = await refreshTopics();
      setTopics(newTopics);
    } catch (err) {
      console.error("Failed to refresh topics:", err);
    }
    setIsRefreshing(false);
  }, []);

  const handlePlayAudio = useCallback(
    (text: string) => {
      ttsSpeak(text);
    },
    [ttsSpeak]
  );

  const handleMicToggle = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  const handleBackToTopics = useCallback(() => {
    setScreen("topics");
    setCurrentTopic("");
  }, []);

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="header">
        <div className="header-brand">
          {screen === "chat" && (
            <button
              className="btn btn-ghost"
              onClick={handleBackToTopics}
              style={{ padding: "6px 10px", marginRight: 4 }}
            >
              ←
            </button>
          )}
          <span className="header-logo">🎙️</span>
          <h1>AI Podcast Buddy</h1>
        </div>
        <div className="header-actions">
          {screen === "chat" && (
            <button
              className="btn btn-ghost"
              onClick={() => {
                setAutoSpeak((v) => {
                  if (v) ttsStop();
                  return !v;
                });
              }}
              style={{ padding: "6px 10px", fontSize: "0.8rem" }}
              title={autoSpeak ? "Auto-speak ON" : "Auto-speak OFF"}
            >
              {autoSpeak ? "🔊" : "🔇"}
            </button>
          )}
          <span
            className={`status-dot ${
              !apiReachable
                ? "disconnected"
                : isConnected
                ? "connected"
                : "loading"
            }`}
            title={
              !apiReachable
                ? "API unreachable"
                : isConnected
                ? "Connected"
                : "Connecting..."
            }
          />
        </div>
      </header>

      {/* Connection warnings */}
      {!apiReachable && (
        <div className="connection-banner error">
          Backend API is unreachable. Start it with: uvicorn api_server:app
          --port 8000
        </div>
      )}
      {apiReachable && !ollamaStatus.connected && (
        <div className="connection-banner warning">
          Ollama is not running. Start it with: ollama serve
        </div>
      )}

      {/* Status bar */}
      {screen === "chat" && (
        <div className="status-bar">
          <span>📡 {isConnected ? "Live" : "Reconnecting..."}</span>
          <span>•</span>
          <span>🎯 {currentTopic}</span>
          {ollamaStatus.model && (
            <>
              <span>•</span>
              <span>🧠 {ollamaStatus.model}</span>
            </>
          )}
        </div>
      )}

      {/* Main content */}
      {screen === "topics" ? (
        <TopicSelector
          topics={topics}
          onSelectTopic={handleSelectTopic}
          onRefresh={handleRefreshTopics}
          isRefreshing={isRefreshing}
        />
      ) : (
        <div className="chat-area">
          <ChatMessages
            messages={messages}
            streamingContent={streamingContent}
            isStreaming={isStreaming}
            onPlayAudio={handlePlayAudio}
          />
          <ChatInput
            onSend={sendMessage}
            disabled={!isConnected || isStreaming}
            isListening={isListening}
            onMicToggle={handleMicToggle}
            micSupported={micSupported}
            transcript={transcript}
          />
        </div>
      )}
    </div>
  );
}
