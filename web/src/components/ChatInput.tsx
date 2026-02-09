"use client";

import React, { useState, useRef, useEffect } from "react";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  isListening: boolean;
  onMicToggle: () => void;
  micSupported: boolean;
  transcript: string;
}

export default function ChatInput({
  onSend,
  disabled,
  isListening,
  onMicToggle,
  micSupported,
  transcript,
}: ChatInputProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // When speech transcript changes, update text field
  useEffect(() => {
    if (transcript) {
      setText(transcript);
    }
  }, [transcript]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 120) + "px";
    }
  }, [text]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="input-area">
      {micSupported && (
        <button
          className={`btn btn-icon btn-mic ${isListening ? "recording" : ""}`}
          onClick={onMicToggle}
          disabled={disabled}
          title={isListening ? "Stop listening" : "Start voice input"}
          aria-label={isListening ? "Stop listening" : "Start voice input"}
        >
          {isListening ? "⏹️" : "🎤"}
        </button>
      )}

      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={
          isListening
            ? "Listening..."
            : "Type a message or tap the mic..."
        }
        disabled={disabled}
        rows={1}
      />

      <button
        className="btn btn-icon btn-send"
        onClick={handleSubmit}
        disabled={disabled || !text.trim()}
        title="Send message"
        aria-label="Send message"
      >
        ➤
      </button>
    </div>
  );
}
