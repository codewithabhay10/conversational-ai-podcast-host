# AI Podcast Buddy — Web Interface

Modern web UI for the AI Podcast Buddy, built with **Next.js 14** + **PWA**.

## Architecture

```
┌─────────────┐     WebSocket/REST     ┌──────────────┐     HTTP      ┌─────────┐
│   Next.js   │ ◄──────────────────► │  FastAPI     │ ◄──────────► │ Ollama  │
│   (PWA)     │     localhost:3000    │  API Server  │   :11434     │  LLM    │
│   Browser   │                       │  :8000       │              └─────────┘
└─────────────┘                       └──────────────┘
       │                                     │
  Web Speech API                    STT / TTS / Memory
  (browser mic)                     (Python modules)
```

## Quick Start

### 1. Start Ollama
```bash
ollama serve
ollama pull llama3
```

### 2. Start the API Server
```bash
cd ai-host
pip install fastapi uvicorn[standard] httpx python-multipart
python api_server.py
# → running on http://localhost:8000
```

### 3. Start the Web UI
```bash
cd ai-host/web
npm install
npm run dev
# → running on http://localhost:3000
```

### 4. Generate PWA Icons (optional)
```bash
pip install Pillow
python generate_icons.py
```

## Features

- **Real-time streaming** — AI responses stream token-by-token via WebSocket
- **Voice input** — Browser-native speech recognition (Web Speech API)
- **TTS playback** — Click "Listen" on any AI response to hear it spoken
- **Topic discovery** — Browse trending topics from HN/Reddit or enter your own
- **PWA installable** — Add to home screen on mobile for app-like experience
- **Responsive** — Works on desktop, mobile, and landscape (driving mode)
- **Dark theme** — Comfortable for driving at night

## PWA Installation

1. Open `http://localhost:3000` in Chrome/Edge
2. Click the install icon in the address bar (or browser menu → "Install app")
3. The app will appear as a standalone window / home screen icon

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/ollama/status` | GET | Check Ollama connection |
| `/api/topics` | GET | List available topics |
| `/api/topics/refresh` | POST | Crawl fresh topics |
| `/api/chat` | POST | Send message, get reply |
| `/api/tts` | POST | Generate speech audio |
| `/api/memory` | GET | View memory state |
| `/ws/chat` | WS | Streaming chat WebSocket |
