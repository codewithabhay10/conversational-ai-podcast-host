"use client";

import React from "react";
import type { Topic } from "@/lib/api";

interface TopicSelectorProps {
  topics: Topic[];
  onSelectTopic: (topic: Topic) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export default function TopicSelector({
  topics,
  onSelectTopic,
  onRefresh,
  isRefreshing,
}: TopicSelectorProps) {
  const [customTopic, setCustomTopic] = React.useState("");

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (customTopic.trim()) {
      onSelectTopic({ title: customTopic.trim(), summary: "" });
      setCustomTopic("");
    }
  };

  const getSourceIcon = (source?: string) => {
    if (!source) return "💡";
    if (source.includes("hackernews")) return "🔶";
    if (source.includes("reddit")) return "🟠";
    return "💡";
  };

  return (
    <div className="topic-screen">
      <div className="header-logo" style={{ fontSize: "3rem" }}>
        🎙️
      </div>
      <h2>Choose Today&apos;s Topic</h2>
      <p>Pick a trending topic or enter your own to start the podcast</p>

      <form className="custom-topic-input" onSubmit={handleCustomSubmit}>
        <input
          type="text"
          value={customTopic}
          onChange={(e) => setCustomTopic(e.target.value)}
          placeholder="Enter a custom topic..."
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!customTopic.trim()}
        >
          Start
        </button>
      </form>

      {topics.length > 0 && (
        <div className="topic-list">
          {topics.map((topic, i) => (
            <div
              key={i}
              className="topic-card"
              onClick={() => onSelectTopic(topic)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && onSelectTopic(topic)}
            >
              <span className="topic-icon">{getSourceIcon(topic.source)}</span>
              <div className="topic-info">
                <h3>{topic.title}</h3>
                {topic.summary && (
                  <p>{topic.summary.slice(0, 120)}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <button
        className="btn btn-ghost refresh-btn"
        onClick={onRefresh}
        disabled={isRefreshing}
      >
        {isRefreshing ? "⏳ Fetching..." : "🔄 Refresh Topics"}
      </button>
    </div>
  );
}
