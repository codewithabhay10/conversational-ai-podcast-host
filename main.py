"""
AI Driving Podcast Buddy — Main Voice Loop
==========================================
Run:  python main.py
Stop: say "stop", "quit", "exit" or press Ctrl+C
"""
import sys
import os
import logging
import signal

# ── Logging setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

# ── Ensure project root is on path ────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ── Graceful shutdown ─────────────────────────────────────────
def _signal_handler(sig, frame):
    print("\n\n👋 Podcast over. See you next time!")
    sys.exit(0)

signal.signal(signal.SIGINT, _signal_handler)


# ── Topic picker ──────────────────────────────────────────────
def pick_topic(topics):
    """Display topics and let user pick one."""
    if not topics:
        print("\n📭 No research topics found.")
        print("   Run 'python research.py' first, or type a topic manually.\n")
        user = input("Enter a topic (or press Enter for free chat): ").strip()
        if user:
            return {"title": user, "summary": f"User-chosen topic: {user}", "id": 0}
        return {"title": "General tech chat", "summary": "Open conversation about technology", "id": 0}

    print("\n" + "=" * 50)
    print("🎙️  TODAY'S PODCAST TOPICS")
    print("=" * 50)
    for t in topics:
        print(f"\n  [{t.get('id', '?')}] {t['title']}")
        summary = t.get("summary", "")
        if summary:
            print(f"      {summary[:100]}")
    print(f"\n  [0] Free chat — pick your own topic")
    print("=" * 50)

    while True:
        try:
            choice = input("\nPick a topic number: ").strip()
            if choice == "0":
                user = input("Enter your topic: ").strip()
                return {"title": user or "General chat", "summary": "", "id": 0}
            idx = int(choice) - 1
            if 0 <= idx < len(topics):
                return topics[idx]
            print(f"Enter a number between 0 and {len(topics)}")
        except ValueError:
            print("Enter a number.")


# ── Stop-word detection ──────────────────────────────────────
STOP_WORDS = {"stop", "quit", "exit", "bye", "goodbye", "end podcast", "shut up"}

def should_stop(text):
    return text.strip().lower() in STOP_WORDS


# ── Main loop ────────────────────────────────────────────────
def main():
    print("\n" + "=" * 50)
    print("🎙️  AI DRIVING PODCAST BUDDY")
    print("    Local-first  •  Free  •  Voice-powered")
    print("=" * 50)

    # 1) Check Ollama
    print("\n⏳ Checking Ollama...")
    from llm.llm import check_ollama, warmup, chat as llm_chat
    if not check_ollama():
        print("\n❌ Ollama is not running or model not found.")
        print("   Start it:  ollama serve")
        print("   Pull model: ollama pull llama3")
        sys.exit(1)

    # 2) Warm up Ollama
    print("⏳ Warming up LLM...")
    warmup()

    # 3) Load memory
    print("⏳ Loading memory...")
    from memory import Memory
    memory = Memory()
    memory.increment_session()

    # 4) Load topics
    print("⏳ Loading topics...")
    from research import load_topics
    topics = load_topics()

    # 5) Pick topic
    topic = pick_topic(topics)
    topic_title = topic["title"]
    topic_context = topic.get("summary", "")
    print(f"\n🎯 Topic: {topic_title}\n")

    # 6) Initialize conversation engine
    from conversation_engine import ConversationEngine
    engine = ConversationEngine(memory=memory)
    engine.set_topic(topic_title, topic_context)

    # 7) Pre-load STT model + calibrate mic + load TTS
    print("⏳ Loading speech models (first time may take a minute)...")
    from stt.stt import listen, warmup_stt
    from tts.tts_engine import speak, warmup_tts
    warmup_stt()   # pre-load whisper model + dummy transcription + calibrate mic
    warmup_tts()   # pre-load TTS model + dummy synthesis (JIT warmup)

    # 8) Generate intro
    print("\n" + "─" * 50)
    print("🎙️  PODCAST STARTING — say 'stop' to end")
    print("─" * 50)

    intro_prompt = engine.get_intro_prompt()
    messages = engine.process_turn(intro_prompt)
    intro_reply = llm_chat(messages)

    print(f"\n🤖 Host: {intro_reply}\n")
    engine.add_to_history("user", intro_prompt)
    engine.add_to_history("assistant", intro_reply)
    engine.advance_state(intro_prompt)

    speak(intro_reply)

    # 9) Voice loop
    while True:
        try:
            # Listen
            user_text = listen()

            if not user_text:
                print("   (no speech detected)")
                # Handle silence
                engine.advance_state("")
                silence_prompt = engine.handle_silence()
                messages = engine.process_turn(silence_prompt)
                reply = llm_chat(messages)

                print(f"\n🤖 Host: {reply}\n")
                engine.add_to_history("assistant", reply)
                speak(reply)
                continue

            print(f"\n🧑 You: {user_text}")

            # Check for stop
            if should_stop(user_text):
                farewell_messages = engine.process_turn(
                    "The user wants to end the podcast. Give a warm, short farewell. Thank them."
                )
                farewell = llm_chat(farewell_messages)
                print(f"\n🤖 Host: {farewell}\n")
                speak(farewell)
                memory.save()
                print("\n👋 Podcast ended. See you next time!")
                break

            # Process turn
            engine.advance_state(user_text)
            messages = engine.process_turn(user_text)
            reply = llm_chat(messages)

            print(f"\n🤖 Host: {reply}\n")

            # Update history
            engine.add_to_history("user", user_text)
            engine.add_to_history("assistant", reply)

            # Speak
            speak(reply)

        except KeyboardInterrupt:
            print("\n\n👋 Podcast interrupted. See you next time!")
            memory.save()
            break
        except Exception as e:
            log.error(f"Error in voice loop: {e}", exc_info=True)
            print(f"\n⚠️ Hiccup: {e}. Continuing...")
            continue

    memory.save()


if __name__ == "__main__":
    main()
