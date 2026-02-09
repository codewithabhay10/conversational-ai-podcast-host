"""
LLM module — talks to Ollama via HTTP.
Handles streaming, conversation history, system prompt injection.
"""
import requests
import json
import logging

log = logging.getLogger(__name__)

# Keep session alive for connection pooling
_session = requests.Session()


def _ollama_url():
    from config import OLLAMA_URL
    return OLLAMA_URL


def _ollama_model():
    from config import OLLAMA_MODEL
    return OLLAMA_MODEL


def warmup():
    """Warm up Ollama by sending a tiny request — loads model into memory."""
    try:
        log.info(f"Warming up Ollama ({_ollama_model()})...")
        resp = _session.post(
            f"{_ollama_url()}/api/generate",
            json={"model": _ollama_model(), "prompt": "Hi", "stream": False},
            timeout=120,
        )
        if resp.status_code == 200:
            log.info("Ollama warm-up complete.")
        else:
            log.warning(f"Ollama warm-up returned {resp.status_code}")
    except Exception as e:
        log.error(f"Ollama warm-up failed: {e}")


def _ollama_options():
    """Build Ollama generation options for speed."""
    from config import (
        OLLAMA_NUM_PREDICT, OLLAMA_NUM_CTX,
        OLLAMA_TEMPERATURE, OLLAMA_TOP_K, OLLAMA_TOP_P, OLLAMA_REPEAT_PENALTY,
    )
    return {
        "num_predict": OLLAMA_NUM_PREDICT,
        "num_ctx": OLLAMA_NUM_CTX,
        "temperature": OLLAMA_TEMPERATURE,
        "top_k": OLLAMA_TOP_K,
        "top_p": OLLAMA_TOP_P,
        "repeat_penalty": OLLAMA_REPEAT_PENALTY,
    }


def chat(messages, stream=False):
    """
    Send a chat request to Ollama.
    messages: list of {"role": ..., "content": ...}
    Returns assistant reply as string.
    """
    url = f"{_ollama_url()}/api/chat"
    payload = {
        "model": _ollama_model(),
        "messages": messages,
        "stream": stream,
        "options": _ollama_options(),
    }

    try:
        if stream:
            return _chat_stream(url, payload)
        else:
            resp = _session.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
    except requests.ConnectionError:
        log.error("Cannot connect to Ollama. Is it running? (ollama serve)")
        return "Sorry, I can't reach my brain right now. Is Ollama running?"
    except requests.Timeout:
        log.error("Ollama request timed out.")
        return "Hmm, that took too long. Let me try again."
    except Exception as e:
        log.error(f"LLM error: {e}")
        return "I had a brain glitch. Let's keep going though!"


def _chat_stream(url, payload):
    """Stream Ollama response token by token, return full text."""
    full_text = ""
    try:
        resp = _session.post(url, json=payload, stream=True, timeout=120)
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                full_text += token
                if chunk.get("done", False):
                    break
        return full_text.strip()
    except Exception as e:
        log.error(f"Stream error: {e}")
        return full_text.strip() if full_text else "Sorry, lost my train of thought!"


def build_messages(system_prompt, history, user_input, topic_context=""):
    """
    Build the message list for Ollama chat.
    Injects system prompt + optional topic context + conversation history + new user input.
    """
    from config import MAX_HISTORY

    messages = [{"role": "system", "content": system_prompt}]

    # Inject topic context as a system-level instruction
    if topic_context:
        messages.append({
            "role": "system",
            "content": f"Today's discussion topic context:\n{topic_context}"
        })

    # Add conversation history (trimmed to MAX_HISTORY)
    trimmed = history[-MAX_HISTORY:]
    messages.extend(trimmed)

    # Add the new user message
    messages.append({"role": "user", "content": user_input})

    return messages


def check_ollama():
    """Check if Ollama is reachable and model is available."""
    try:
        resp = _session.get(f"{_ollama_url()}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            target = _ollama_model()
            # Check if any model name starts with target
            found = any(target in m for m in models)
            if found:
                log.info(f"Ollama OK — model '{target}' available.")
                return True
            else:
                log.warning(f"Ollama running but model '{target}' not found. Available: {models}")
                log.warning(f"Run: ollama pull {target}")
                return False
        return False
    except Exception:
        log.error("Ollama is not running. Start it with: ollama serve")
        return False
