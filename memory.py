"""
Lightweight memory system.
Stores topics discussed, user opinions, preferences.
Persisted as JSON.
"""
import json
import os
import logging
from datetime import datetime

log = logging.getLogger(__name__)


class Memory:
    def __init__(self, filepath=None):
        if filepath is None:
            from config import MEMORY_FILE
            filepath = self.filepath = MEMORY_FILE
        else:
            self.filepath = filepath

        self.data = {
            "topics_discussed": [],
            "user_opinions": [],
            "preferences": {},
            "conversation_count": 0,
            "last_session": None,
        }
        self.load()

    def load(self):
        """Load memory from disk."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self.data.update(saved)
                log.info(f"Memory loaded: {len(self.data['topics_discussed'])} topics, "
                         f"{len(self.data['user_opinions'])} opinions")
            except Exception as e:
                log.warning(f"Could not load memory: {e}")

    def save(self):
        """Persist memory to disk."""
        try:
            self.data["last_session"] = datetime.now().isoformat()
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Could not save memory: {e}")

    def add_topic(self, topic):
        """Record that a topic was discussed."""
        entry = {
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
        }
        self.data["topics_discussed"].append(entry)
        # Keep last 100
        self.data["topics_discussed"] = self.data["topics_discussed"][-100:]
        self.save()

    def add_opinion(self, topic, opinion):
        """Record a user opinion on a topic."""
        entry = {
            "topic": topic,
            "opinion": opinion,
            "timestamp": datetime.now().isoformat(),
        }
        self.data["user_opinions"].append(entry)
        self.data["user_opinions"] = self.data["user_opinions"][-100:]
        self.save()

    def set_preference(self, key, value):
        """Store a user preference."""
        self.data["preferences"][key] = value
        self.save()

    def get_preference(self, key, default=None):
        """Get a user preference."""
        return self.data["preferences"].get(key, default)

    def increment_session(self):
        """Bump session counter."""
        self.data["conversation_count"] += 1
        self.save()

    def get_context_summary(self):
        """
        Build a short summary of memory for LLM context injection.
        """
        parts = []

        # Recent topics
        recent_topics = self.data["topics_discussed"][-5:]
        if recent_topics:
            t_list = ", ".join(t["topic"] for t in recent_topics)
            parts.append(f"Recently discussed topics: {t_list}")

        # Opinions
        recent_ops = self.data["user_opinions"][-5:]
        if recent_ops:
            o_list = "; ".join(f'{o["topic"]}: {o["opinion"]}' for o in recent_ops)
            parts.append(f"User opinions: {o_list}")

        # Preferences
        prefs = self.data["preferences"]
        if prefs:
            p_list = ", ".join(f"{k}={v}" for k, v in prefs.items())
            parts.append(f"User preferences: {p_list}")

        sessions = self.data["conversation_count"]
        if sessions > 0:
            parts.append(f"This is conversation session #{sessions + 1}")

        return "\n".join(parts)

    def extract_opinions_from_text(self, text, topic):
        """
        Simple heuristic: if user text contains opinion words, save it.
        """
        opinion_markers = [
            "i think", "i believe", "i love", "i hate", "i prefer",
            "i like", "i don't like", "my opinion", "in my view",
            "honestly", "actually", "i feel", "i disagree", "i agree",
        ]
        lower = text.lower()
        for marker in opinion_markers:
            if marker in lower:
                self.add_opinion(topic, text)
                log.info(f"Saved user opinion on '{topic}'")
                return True
        return False
