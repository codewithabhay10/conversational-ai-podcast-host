const API_BASE = "";

export interface Topic {
  id?: number;
  title: string;
  summary?: string;
  source?: string;
  score?: number;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatResponse {
  reply: string;
  history: ChatMessage[];
  state: string;
  turn: number;
}

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error("API unreachable");
  return res.json();
}

export async function fetchOllamaStatus(): Promise<{
  connected: boolean;
  model?: string;
  error?: string;
}> {
  const res = await fetch(`${API_BASE}/api/ollama/status`);
  return res.json();
}

export async function fetchTopics(): Promise<Topic[]> {
  const res = await fetch(`${API_BASE}/api/topics`);
  const data = await res.json();
  return data.topics || [];
}

export async function refreshTopics(): Promise<Topic[]> {
  const res = await fetch(`${API_BASE}/api/topics/refresh`, { method: "POST" });
  const data = await res.json();
  return data.topics || [];
}

export async function sendChat(
  message: string,
  topic: string,
  topicContext: string,
  history: ChatMessage[]
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, topic, topic_context: topicContext, history }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
  return res.json();
}

export async function fetchTTSAudio(text: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error("TTS failed");
  return res.blob();
}

export function createChatWebSocket(): WebSocket {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  return new WebSocket(`${protocol}//${host}/ws/chat`);
}

export async function fetchMemory(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/memory`);
  return res.json();
}
