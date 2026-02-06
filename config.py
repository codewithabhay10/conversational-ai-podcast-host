"""
Central configuration for AI Podcast Buddy.
Edit settings here instead of hunting through files.
"""
import os

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")
TOPICS_FILE = os.path.join(DATA_DIR, "topics.json")
INPUT_WAV = os.path.join(DATA_DIR, "input.wav")
OUTPUT_WAV = os.path.join(DATA_DIR, "output.wav")

# --- Ollama ---
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3"  # or "mistral"

# --- STT (faster-whisper) ---
WHISPER_MODEL_SIZE = "base"  # tiny, base, small, medium, large-v2
WHISPER_DEVICE = "cpu"       # "cpu" or "cuda"
WHISPER_COMPUTE = "int8"     # int8, float16, float32

# --- TTS (Coqui) ---
TTS_MODEL = "tts_models/en/vctk/vits"
TTS_SPEAKER = "p273"  # energetic male voice; try p228 for female

# --- Audio Recording ---
RECORD_SAMPLERATE = 16000
RECORD_CHANNELS = 1
RECORD_DURATION_DEFAULT = 5   # seconds
SILENCE_THRESHOLD = 0.02      # RMS below this = silence (auto-calibrated at startup)
SILENCE_TIMEOUT = 1.5         # seconds of silence after speech before auto-stop
MAX_RECORD_SECONDS = 15       # hard cap on recording length

# --- Conversation ---
MAX_HISTORY = 20  # max messages kept in context window

# --- Research ---
HN_FETCH_DAYS = 10
REDDIT_SUBREDDITS = ["technology", "artificial", "MachineLearning", "programming"]
REDDIT_FETCH_LIMIT = 30

# --- System Prompt ---
SYSTEM_PROMPT = """You are a smart, energetic podcast host and driving companion.
You never end conversations.
You explain clearly.
You ask engaging questions.
You speak casually like a friend in a car.
You use examples and stories.
Keep responses concise — under 4 sentences unless explaining something complex.
Always end with a question or invitation to continue."""

# Ensure data dir exists
os.makedirs(DATA_DIR, exist_ok=True)
