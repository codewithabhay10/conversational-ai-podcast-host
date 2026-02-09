# AI Podcast Buddy — Project Workflow & Technology Guide

## Overview

AI Podcast Buddy is a **local-first, voice-powered AI podcast companion** designed for hands-free conversation while driving. It runs entirely on your machine — no cloud APIs, no subscriptions. The system crawls trending tech topics, generates podcast-style conversations using a local LLM, and communicates via voice (speech-to-text + text-to-speech). A modern web interface (Next.js PWA) provides an alternative browser-based experience.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                               │
│                                                                      │
│   ┌──────────────────┐          ┌─────────────────────────────────┐  │
│   │   CLI Voice App  │          │     Next.js Web App (PWA)       │  │
│   │   (main.py)      │          │     localhost:3000              │  │
│   │   Mic → STT      │          │  ┌──────────┐ ┌──────────────┐ │  │
│   │   Speaker → TTS  │          │  │ Chat UI  │ │ Topic Picker │ │  │
│   └────────┬─────────┘          │  │ Voice In │ │ Browser TTS  │ │  │
│            │                     │  └─────┬────┘ └──────────────┘ │  │
│            │                     └────────┼───────────────────────┘  │
│            │                              │                          │
└────────────┼──────────────────────────────┼──────────────────────────┘
             │                              │
             │ Python calls          REST + WebSocket
             │                              │
┌────────────┼──────────────────────────────┼──────────────────────────┐
│            ▼                              ▼                          │
│   ┌─────────────────────────────────────────────────────────┐        │
│   │              BACKEND LAYER                               │        │
│   │                                                          │        │
│   │  ┌────────────────────┐    ┌─────────────────────────┐  │        │
│   │  │ Conversation       │    │ FastAPI Server           │  │        │
│   │  │ Engine             │    │ (api_server.py)          │  │        │
│   │  │ (State Machine)    │    │ REST: /api/*             │  │        │
│   │  │ INTRO→EXPLAIN→     │    │ WS:   /ws/chat           │  │        │
│   │  │ ASK→REACT→EXPAND   │    │ Streaming tokens         │  │        │
│   │  └─────────┬──────────┘    └────────┬────────────────┘  │        │
│   │            │                         │                    │        │
│   │            ▼                         ▼                    │        │
│   │  ┌──────────────────────────────────────────────────┐    │        │
│   │  │           LLM Module (llm/llm.py)                │    │        │
│   │  │  • Builds message payloads (system + history)    │    │        │
│   │  │  • HTTP to Ollama API (chat + streaming)         │    │        │
│   │  │  • Connection pooling, warm-up, speed tuning     │    │        │
│   │  └──────────────────────┬───────────────────────────┘    │        │
│   │                         │                                 │        │
│   │  ┌─────────────┐  ┌────┴──────────┐  ┌───────────────┐  │        │
│   │  │ Memory      │  │ Research      │  │ Config        │  │        │
│   │  │ (memory.py) │  │ (research.py) │  │ (config.py)   │  │        │
│   │  │ JSON store  │  │ HN + Reddit   │  │ All settings  │  │        │
│   │  └─────────────┘  └───────────────┘  └───────────────┘  │        │
│   └──────────────────────────────────────────────────────────┘        │
│                                                                       │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │ HTTP :11434
                                    ▼
                            ┌───────────────┐
                            │    Ollama      │
                            │  (llama3 /     │
                            │   mistral)     │
                            │  Local LLM     │
                            └───────────────┘
```

---

## Technology Stack

### Backend (Python)

| Technology | Purpose | Why Chosen |
|---|---|---|
| **Python 3.11** | Core language | Rich ML/AI ecosystem, rapid development |
| **Ollama** | Local LLM inference | Free, no API keys, runs LLaMA/Mistral locally |
| **faster-whisper** | Speech-to-Text | CTranslate2-optimized Whisper — fast on CPU |
| **Coqui TTS** | Text-to-Speech (server) | High-quality neural voices, multi-speaker VITS model |
| **FastAPI** | Web API server | Async, WebSocket support, auto-docs, fast |
| **httpx** | Async HTTP client | Streaming support for Ollama token-by-token relay |
| **uvicorn** | ASGI server | Production-grade, WebSocket support |
| **sounddevice** | Microphone recording | Cross-platform audio capture |
| **scipy** | WAV file I/O | Audio processing utilities |
| **requests** | HTTP client (sync) | Ollama communication in CLI mode |
| **praw / feedparser** | Reddit / RSS parsing | Topic research crawling |

### Frontend (TypeScript)

| Technology | Purpose | Why Chosen |
|---|---|---|
| **Next.js 14** | React framework | App Router, SSR, API rewrites, production-ready |
| **React 18** | UI library | Component model, hooks, reactive state |
| **TypeScript** | Type safety | Catch errors at compile time |
| **next-pwa** | PWA support | Service worker generation, offline caching |
| **Web Speech API** | Browser voice input | Native speech recognition, no server needed |
| **SpeechSynthesis API** | Browser TTS | Instant playback, zero latency, no server load |
| **WebSocket** | Real-time streaming | Token-by-token LLM response streaming |

### Infrastructure

| Component | Role |
|---|---|
| **Ollama** (localhost:11434) | LLM inference engine |
| **FastAPI** (localhost:8000) | Backend API + WebSocket server |
| **Next.js** (localhost:3000) | Frontend dev server |
| **JSON files** (data/) | Memory persistence, topic storage |

---

## Detailed Workflow

### 1. Research Phase (Nightly)

```
python research.py
```

**Flow:**
1. **Fetch Hacker News** — Queries the Algolia API for top tech stories from the last 10 days
2. **Fetch Reddit** — Hits the public JSON API for top posts from r/technology, r/artificial, r/MachineLearning, r/programming
3. **Rank & Deduplicate** — Scores each item by `points + comments × 2`, deduplicates by title similarity, picks top 5
4. **Generate Summaries** — Sends each topic to Ollama for a 2-3 sentence conversational summary
5. **Save** — Writes ranked topics to `data/topics.json`

**Data flow:**
```
Hacker News API ──┐
                  ├─→ rank_and_extract_topics() ─→ generate_summaries_with_llm() ─→ topics.json
Reddit JSON API ──┘
```

---

### 2. CLI Voice Loop (main.py)

```
python main.py
```

**Startup sequence:**
1. Check Ollama connection + model availability
2. Warm up LLM (send a tiny prompt to load model into GPU/RAM)
3. Load persistent memory from `data/memory.json`
4. Load pre-crawled topics from `data/topics.json`
5. User picks a topic via terminal menu
6. Load faster-whisper STT model + calibrate mic ambient noise
7. Generate intro via LLM → speak it via Coqui TTS

**Voice loop (repeating):**
```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  🎤 Record mic audio (auto-stop on silence)         │
│         │                                           │
│         ▼                                           │
│  📝 Transcribe with faster-whisper                  │
│         │                                           │
│         ├─── Empty? → Handle silence (fill-in)      │
│         ├─── Stop word? → Generate farewell → Exit  │
│         │                                           │
│         ▼                                           │
│  🧠 Advance conversation state machine              │
│  📦 Build message payload (system + history + input)│
│  🤖 Send to Ollama → get reply                     │
│         │                                           │
│         ▼                                           │
│  🔊 Speak reply via Coqui TTS                      │
│  💾 Update conversation history + memory            │
│         │                                           │
│         └──────────── loop ─────────────────────────┘
```

---

### 3. Conversation Engine (State Machine)

The conversation engine prevents dead air and drives engaging dialogue through a deterministic state machine:

```
 INTRO ──→ EXPLAIN ──→ ASK ──→ REACT ──→ EXPAND
                        ▲                    │
                        └────────────────────┘
                              (loops)
```

| State | Behavior | Trigger |
|---|---|---|
| **INTRO** | Introduce topic with energy, hook the listener | Topic selected |
| **EXPLAIN** | Clear explanation with analogies | After intro |
| **ASK** | Personal question to the user | After explain, or 2+ silences |
| **REACT** | React to user's answer, build on it | After user speaks |
| **EXPAND** | New angle, counter-argument, fun fact | After reacting |

Each state injects specific behavioral instructions into the system prompt, steering the LLM's personality.

---

### 4. Memory System

Persistent JSON-based memory that survives across sessions:

```json
{
  "topics_discussed": [{"topic": "...", "timestamp": "..."}],
  "user_opinions": [{"topic": "...", "opinion": "...", "timestamp": "..."}],
  "preferences": {},
  "conversation_count": 5,
  "last_session": "2026-02-07T10:30:00"
}
```

**How it works:**
- **Topics** are logged when selected
- **Opinions** are auto-extracted using keyword matching ("I think...", "I love...", "I hate...")
- **Context summary** is injected into the system prompt so the LLM remembers past conversations
- Session counter tracks how many times the user has chatted

---

### 5. Web Interface Workflow (Next.js PWA)

**Startup:**
```
Terminal 1: python api_server.py     → localhost:8000
Terminal 2: cd web && npm run dev    → localhost:3000
```

**User flow:**
```
┌─────────────────────────────────────────────────┐
│  Browser opens localhost:3000                   │
│         │                                       │
│         ▼                                       │
│  📡 Check API health + Ollama status            │
│  📋 Fetch topics from /api/topics               │
│         │                                       │
│         ▼                                       │
│  🎯 TOPIC SELECTOR SCREEN                       │
│     • Browse trending topics (from research)    │
│     • Enter custom topic                        │
│     • Refresh topics button                     │
│         │                                       │
│         ▼ (user picks topic)                    │
│                                                 │
│  💬 CHAT SCREEN                                 │
│     • WebSocket connects to /ws/chat            │
│     • Sends "start_topic" message               │
│     • AI generates intro (streamed token-by-    │
│       token via WebSocket)                      │
│     • Browser SpeechSynthesis auto-speaks reply  │
│         │                                       │
│         ▼ (conversation loop)                   │
│                                                 │
│  🧑 User types text OR taps mic (Web Speech API)│
│         │                                       │
│         ▼                                       │
│  📤 Send via WebSocket                          │
│  📥 Receive streamed tokens → render live       │
│  🔊 Auto-speak completed reply                  │
│  💾 Server updates memory + history             │
│         │                                       │
│         └──── loop ─────────────────────────────┘
```

**WebSocket message protocol:**

| Direction | Type | Payload |
|---|---|---|
| Client → Server | `start_topic` | `{topic, topicContext}` |
| Client → Server | `message` | `{text, topic, history}` |
| Server → Client | `token` | `{content}` (single token) |
| Server → Client | `complete` | `{content, history, state}` |
| Server → Client | `error` | `{message}` |

---

### 6. TTS Pipeline

Two TTS paths are available:

**Browser TTS (default — instant):**
```
AI reply text → SpeechSynthesis API → speaker
               (runs entirely in browser)
               Rate: 1.15x, auto-selects best voice
```

**Server TTS (fallback — Coqui):**
```
AI reply text → POST /api/tts → Coqui VITS model → WAV file → HTTP response → Audio element
               (requires TTS model loaded on server)
               Speaker: p273 (energetic male)
```

---

### 7. LLM Communication

All LLM interaction goes through Ollama's local HTTP API:

**Message construction:**
```
[
  { role: "system",    content: SYSTEM_PROMPT + state instructions + memory context },
  { role: "system",    content: topic research context },
  { role: "user",      content: <history msg 1> },
  { role: "assistant", content: <history msg 2> },
  ...last 10 messages...
  { role: "user",      content: <current user input> }
]
```

**Speed tuning parameters:**
| Parameter | Value | Effect |
|---|---|---|
| `num_predict` | 150 | Caps response to ~150 tokens |
| `num_ctx` | 2048 | Smaller context window = faster |
| `temperature` | 0.7 | Balanced creativity |
| `top_k` | 40 | Limits token sampling pool |
| `top_p` | 0.9 | Nucleus sampling threshold |
| `repeat_penalty` | 1.1 | Reduces repetition |

---

## File Structure

```
ai-host/
├── main.py                   # CLI voice loop entry point
├── api_server.py             # FastAPI backend for web UI
├── config.py                 # All configuration in one place
├── conversation_engine.py    # State machine for dialogue flow
├── memory.py                 # JSON-based persistent memory
├── research.py               # Nightly topic crawler (HN + Reddit)
├── generate_icons.py         # PWA icon generator
├── requirements.txt          # Python dependencies
│
├── llm/
│   └── llm.py                # Ollama communication (chat, stream, warmup)
│
├── stt/
│   └── stt.py                # Mic recording + faster-whisper transcription
│
├── tts/
│   └── tts_engine.py         # Coqui TTS synthesis + audio playback
│
├── data/
│   ├── memory.json           # Persistent user memory
│   └── topics.json           # Pre-crawled discussion topics
│
└── web/                      # Next.js PWA frontend
    ├── next.config.js        # PWA config + API proxy rewrites
    ├── package.json
    ├── tsconfig.json
    ├── public/
    │   ├── manifest.json     # PWA manifest
    │   ├── sw.js             # Service worker
    │   └── icons/            # App icons (72–512px)
    └── src/
        ├── app/
        │   ├── layout.tsx    # Root layout + PWA meta tags
        │   ├── globals.css   # Dark theme styles
        │   └── page.tsx      # Main app (topic selector + chat)
        ├── components/
        │   ├── TopicSelector.tsx   # Topic browsing UI
        │   ├── ChatMessages.tsx    # Message bubbles + streaming
        │   └── ChatInput.tsx       # Text input + mic button
        ├── hooks/
        │   ├── useWebSocketChat.ts      # WebSocket streaming hook
        │   ├── useSpeechRecognition.ts  # Browser voice input hook
        │   └── useTTS.ts               # Hybrid TTS (browser + server)
        └── lib/
            └── api.ts        # REST API client functions
```

---

## Running the Project

```bash
# 1. Start Ollama
ollama serve
ollama pull llama3

# 2. (Optional) Crawl fresh topics
python research.py

# 3a. CLI mode (voice)
python main.py

# 3b. Web mode
python api_server.py          # Terminal 1 → localhost:8000
cd web && npm install && npm run dev   # Terminal 2 → localhost:3000
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **Local-first (Ollama)** | No API costs, no internet dependency, full privacy |
| **State machine conversation** | Prevents awkward silence, maintains podcast energy |
| **Browser TTS over server TTS** | Zero latency — no network round-trip for speech |
| **WebSocket streaming** | Token-by-token display feels responsive even on slow hardware |
| **JSON memory persistence** | Simple, no database dependency, human-readable |
| **PWA** | Installable on phone, works offline for cached content |
| **num_predict cap (150)** | Forces concise replies, reduces generation time |
| **Separated research phase** | Crawling is slow; doing it nightly keeps startup fast |
