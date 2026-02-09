"""
FastAPI backend for AI Podcast Buddy Web Interface.
Exposes chat, topics, memory, TTS via REST + WebSocket.

Run:  uvicorn api_server:app --reload --port 8000
"""
import os
import sys
import json
import logging
import asyncio
import base64
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api_server")

app = FastAPI(title="AI Podcast Buddy API", version="1.0.0")

# CORS — allow Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Lazy-loaded singletons ────────────────────────────────────
_memory = None
_ollama_ready = False


def get_memory():
    global _memory
    if _memory is None:
        from memory import Memory
        _memory = Memory()
        _memory.increment_session()
    return _memory


_tts_ready = False


def ensure_ollama():
    global _ollama_ready
    if not _ollama_ready:
        from llm.llm import check_ollama, warmup
        if not check_ollama():
            raise HTTPException(503, "Ollama is not running. Start it with: ollama serve")
        warmup()
        _ollama_ready = True


def ensure_tts():
    """Warm up TTS on first use (load model + JIT)."""
    global _tts_ready
    if not _tts_ready:
        try:
            from tts.tts_engine import warmup_tts
            warmup_tts()
            _tts_ready = True
        except Exception as e:
            log.warning(f"TTS warmup skipped: {e}")


# ── Pydantic models ───────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    topic: Optional[str] = None
    topic_context: Optional[str] = ""
    history: Optional[list] = []


class TopicSelectRequest(BaseModel):
    topic: str
    context: Optional[str] = ""


# ── REST Endpoints ────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Health check."""
    return {"status": "ok", "service": "AI Podcast Buddy"}


@app.get("/api/ollama/status")
async def ollama_status():
    """Check if Ollama is running and model is available."""
    try:
        from llm.llm import check_ollama
        ok = check_ollama()
        from config import OLLAMA_MODEL
        return {"connected": ok, "model": OLLAMA_MODEL}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@app.get("/api/topics")
async def get_topics():
    """Get available podcast topics from research."""
    try:
        from research import load_topics
        topics = load_topics()
        return {"topics": topics}
    except Exception as e:
        log.error(f"Failed to load topics: {e}")
        return {"topics": [], "error": str(e)}


@app.post("/api/topics/refresh")
async def refresh_topics():
    """Run the research crawler to fetch fresh topics."""
    try:
        from research import main as run_research
        run_research()
        from research import load_topics
        topics = load_topics()
        return {"topics": topics, "refreshed": True}
    except Exception as e:
        raise HTTPException(500, f"Research failed: {e}")


@app.get("/api/memory")
async def get_memory_data():
    """Get current memory state."""
    mem = get_memory()
    return mem.data


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Synchronous chat endpoint.
    Sends user message, returns AI response.
    """
    ensure_ollama()

    from conversation_engine import ConversationEngine
    from llm.llm import chat as llm_chat

    mem = get_memory()
    engine = ConversationEngine(memory=mem)

    if req.topic:
        engine.set_topic(req.topic, req.topic_context or "")

    # Rebuild history
    engine.history = req.history or []

    # Process turn
    engine.advance_state(req.message)
    messages = engine.process_turn(req.message)
    reply = llm_chat(messages)

    # Update history
    engine.add_to_history("user", req.message)
    engine.add_to_history("assistant", reply)

    return {
        "reply": reply,
        "history": engine.history,
        "state": engine.state,
        "turn": engine.turn_count,
    }


@app.post("/api/tts")
async def tts_endpoint(req: dict):
    """Generate TTS audio for given text. Returns wav file.
    Synthesizes only the first 2-sentence chunk for speed."""
    text = req.get("text", "")
    if not text.strip():
        raise HTTPException(400, "No text provided")

    from config import OUTPUT_WAV, TTS_SPEAKER, TTS_MODEL

    ensure_tts()  # warm up on first call

    try:
        from tts.tts_engine import _clean_for_speech, _get_engine, split_by_sentence
        clean = _clean_for_speech(text)
        if not clean:
            raise HTTPException(400, "Text cleaned to empty string")

        # Only synthesize first 2-sentence chunk (fast perceived latency)
        chunks = split_by_sentence(clean, max_sentences=2)
        first_chunk = chunks[0] if chunks else clean

        engine = _get_engine()
        engine.tts_to_file(text=first_chunk, file_path=OUTPUT_WAV, speaker=TTS_SPEAKER)
        return FileResponse(OUTPUT_WAV, media_type="audio/wav", filename="response.wav")
    except ImportError:
        raise HTTPException(501, "TTS engine not available. Install Coqui TTS.")
    except Exception as e:
        log.error(f"TTS generation failed: {e}")
        raise HTTPException(500, f"TTS failed: {e}")


# ── WebSocket for streaming chat ──────────────────────────────

@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """
    WebSocket endpoint for real-time streaming chat.
    
    Client sends JSON:
      { "type": "message", "text": "...", "topic": "...", "topicContext": "...", "history": [...] }
      { "type": "start_topic", "topic": "...", "topicContext": "..." }
    
    Server sends JSON:
      { "type": "token", "content": "..." }         — streaming token
      { "type": "complete", "content": "...", "history": [...], "state": "..." }
      { "type": "error", "message": "..." }
    """
    await ws.accept()
    log.info("WebSocket client connected")

    from conversation_engine import ConversationEngine
    from llm.llm import build_messages
    from config import OLLAMA_URL, OLLAMA_MODEL

    mem = get_memory()
    engine = ConversationEngine(memory=mem)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "start_topic":
                topic = data.get("topic", "General chat")
                context = data.get("topicContext", "")
                engine.set_topic(topic, context)
                engine.history = []

                # Generate intro
                intro_prompt = engine.get_intro_prompt()
                messages = engine.process_turn(intro_prompt)

                # Stream the response
                reply = await _stream_ollama(ws, messages, OLLAMA_URL, OLLAMA_MODEL)

                engine.add_to_history("user", intro_prompt)
                engine.add_to_history("assistant", reply)
                engine.advance_state(intro_prompt)

                await ws.send_json({
                    "type": "complete",
                    "content": reply,
                    "history": engine.history,
                    "state": engine.state,
                })

            elif msg_type == "message":
                text = data.get("text", "")
                if not text.strip():
                    continue

                # Restore history if provided
                if data.get("history"):
                    engine.history = data["history"]

                if data.get("topic"):
                    engine.current_topic = data["topic"]
                    engine.topic_context = data.get("topicContext", "")

                engine.advance_state(text)
                messages = engine.process_turn(text)

                # Stream the response
                reply = await _stream_ollama(ws, messages, OLLAMA_URL, OLLAMA_MODEL)

                engine.add_to_history("user", text)
                engine.add_to_history("assistant", reply)

                await ws.send_json({
                    "type": "complete",
                    "content": reply,
                    "history": engine.history,
                    "state": engine.state,
                })

    except WebSocketDisconnect:
        log.info("WebSocket client disconnected")
    except Exception as e:
        log.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except:
            pass


# Persistent async HTTP client for Ollama (avoids connection setup per request)
_httpx_client = None

def _get_httpx_client():
    global _httpx_client
    if _httpx_client is None:
        import httpx
        _httpx_client = httpx.AsyncClient(timeout=120.0)
    return _httpx_client


async def _stream_ollama(ws, messages, ollama_url, model):
    """Stream Ollama chat response, sending tokens via WebSocket."""
    from llm.llm import _ollama_options

    full_text = ""
    url = f"{ollama_url}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": _ollama_options(),
    }

    try:
        client = _get_httpx_client()
        async with client.stream("POST", url, json=payload) as resp:
            async for line in resp.aiter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full_text += token
                        await ws.send_json({"type": "token", "content": token})
                    if chunk.get("done", False):
                        break
    except Exception as e:
        log.error(f"Ollama stream error: {e}")
        await ws.send_json({"type": "error", "message": f"LLM error: {e}"})

    return full_text.strip()


# ── Run directly ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
