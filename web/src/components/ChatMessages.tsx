"use client";

import React, { useRef, useEffect } from "react";
import type { ChatMessage } from "@/lib/api";

interface ChatMessagesProps {
  messages: ChatMessage[];
  streamingContent: string;
  isStreaming: boolean;
  onPlayAudio?: (text: string) => void;
}

export default function ChatMessages({
  messages,
  streamingContent,
  isStreaming,
  onPlayAudio,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="empty-state">
        <div className="icon">🎙️</div>
        <p>Starting the podcast...</p>
      </div>
    );
  }

  return (
    <div className="messages-container">
      {messages.map((msg, i) => (
        <div key={i} className={`message ${msg.role}`}>
          <div className="message-avatar">
            {msg.role === "user" ? "🧑" : "🤖"}
          </div>
          <div className="message-bubble">
            {msg.content}
            {msg.role === "assistant" && onPlayAudio && (
              <button
                className="audio-btn"
                onClick={() => onPlayAudio(msg.content)}
                title="Play as speech"
              >
                🔊 Listen
              </button>
            )}
          </div>
        </div>
      ))}

      {/* Streaming message */}
      {isStreaming && streamingContent && (
        <div className="message assistant">
          <div className="message-avatar">🤖</div>
          <div className="message-bubble">
            {streamingContent}
            <span className="typing-cursor">▎</span>
          </div>
        </div>
      )}

      {/* Typing indicator when streaming hasn't started yet */}
      {isStreaming && !streamingContent && (
        <div className="message assistant">
          <div className="message-avatar">🤖</div>
          <div className="message-bubble">
            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
