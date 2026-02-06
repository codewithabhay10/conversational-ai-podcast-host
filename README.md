# 🎙️ AI Driving Podcast Buddy

Local-first, free-to-run AI voice companion for your commute.

## Folder Structure

```
ai-host/
├── main.py                  # Main voice loop — run this
├── config.py                # All settings in one place
├── research.py              # Night crawler — fetch trending topics
├── memory.py                # Lightweight JSON memory
├── conversation_engine.py   # Podcast state machine
├── requirements.txt
├── README.md
├── stt/
│   ├── __init__.py
│   └── stt.py               # Speech-to-Text (faster-whisper)
├── llm/
│   ├── __init__.py
│   └── llm.py               # LLM via Ollama
├── tts/
│   ├── __init__.py
│   └── tts_engine.py        # Text-to-Speech (Coqui TTS)
└── data/                    # Auto-created at runtime
    ├── memory.json
    ├── topics.json
    ├── input.wav
    └── output.wav
```

## Prerequisites

| Tool | Install |
|------|---------|
| Python 3.11 | https://python.org (3.11.x specifically) |
| Ollama | https://ollama.com |
| C++ Build Tools | https://visualstudio.microsoft.com/visual-cpp-build-tools/ |
| Microphone | Any USB/built-in mic |

## Setup (one-time)

```bash
# 1. Create virtual environment with Python 3.11
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Mac/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Pull an Ollama model
ollama pull llama3
# or: ollama pull mistral

# 4. Start Ollama (keep running in background)
ollama serve
```

## Run

```bash
# Morning — start the podcast
python main.py

# Night — fetch fresh topics (optional)
python research.py
```

## How It Works

1. **Startup**: loads memory + topics, you pick a topic
2. **Voice loop**: records your voice → transcribes → LLM generates reply → TTS speaks it
3. **State machine**: INTRO → EXPLAIN → ASK → REACT → EXPAND → loops back
4. **Memory**: remembers topics discussed, your opinions, preferences
5. **Say "stop"** to end the podcast

## Config

Edit `config.py` to change:
- Ollama model (`llama3` / `mistral`)
- Whisper model size (`tiny` / `base` / `small`)
- TTS voice speaker
- Recording settings
- System prompt personality

## Common Errors

| Error | Fix |
|-------|-----|
| `Ollama not running` | Run `ollama serve` in a separate terminal |
| `Model not found` | Run `ollama pull llama3` |
| `No microphone` | Check sound settings, allow mic access |
| `TTS model download` | First run downloads ~100MB model — wait |
| `Microsoft Visual C++ required` | Install C++ Build Tools (see Prerequisites) |
| `CUDA out of memory` | Set `WHISPER_DEVICE = "cpu"` in config.py |
| `No speech detected` | Speak louder / check mic is default device |

## Tech Stack

- **STT**: faster-whisper (local, offline)
- **LLM**: Ollama + llama3/mistral (local, offline)
- **TTS**: Coqui TTS VITS (local, offline)
- **Storage**: JSON files
- **UI**: Terminal
