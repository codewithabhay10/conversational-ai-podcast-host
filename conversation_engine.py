"""
Conversation Engine — manages podcast-style flow.
State machine: INTRO → EXPLAIN → ASK → REACT → EXPAND → LOOP
Prevents dead silence, drives engaging dialogue.
"""
import logging

log = logging.getLogger(__name__)


class ConversationState:
    INTRO = "INTRO"
    EXPLAIN = "EXPLAIN"
    ASK = "ASK"
    REACT = "REACT"
    EXPAND = "EXPAND"


class ConversationEngine:
    def __init__(self, memory=None):
        self.state = ConversationState.INTRO
        self.history = []  # list of {"role": ..., "content": ...}
        self.current_topic = ""
        self.topic_context = ""
        self.turn_count = 0
        self.memory = memory
        self.silence_count = 0  # consecutive empty inputs

    def set_topic(self, topic, context=""):
        """Set today's topic and optional research context."""
        self.current_topic = topic
        self.topic_context = context
        self.state = ConversationState.INTRO
        self.turn_count = 0
        if self.memory:
            self.memory.add_topic(topic)

    def get_system_prompt(self):
        """Build the full system prompt with state-specific instructions."""
        from config import SYSTEM_PROMPT

        state_instructions = {
            ConversationState.INTRO: (
                "You are starting a new topic. Introduce it with excitement and energy. "
                "Give a brief hook about why this is interesting. End with a question."
            ),
            ConversationState.EXPLAIN: (
                "Explain the current topic in a clear, simple way. "
                "Use analogies and real-world examples. Keep it conversational."
            ),
            ConversationState.ASK: (
                "Ask the user a thought-provoking question about the topic. "
                "Make it personal — 'what do you think?', 'have you ever...?'"
            ),
            ConversationState.REACT: (
                "React to what the user just said. Show genuine interest. "
                "Build on their point. Add your perspective."
            ),
            ConversationState.EXPAND: (
                "Expand the discussion. Bring in a related angle, a counter-argument, "
                "or a fun fact. Keep the energy up."
            ),
        }

        prompt = SYSTEM_PROMPT + "\n\n"
        prompt += f"Current conversation state: {self.state}\n"
        prompt += state_instructions.get(self.state, "")

        # Add memory context
        if self.memory:
            mem_ctx = self.memory.get_context_summary()
            if mem_ctx:
                prompt += f"\n\nUser memory:\n{mem_ctx}"

        return prompt

    def advance_state(self, user_input=""):
        """
        Advance the state machine based on current state and input.
        """
        self.turn_count += 1

        if not user_input.strip():
            self.silence_count += 1
        else:
            self.silence_count = 0

        # Handle silence — host should fill in
        if self.silence_count >= 2:
            self.state = ConversationState.ASK
            self.silence_count = 0
            return

        # State transitions
        if self.state == ConversationState.INTRO:
            self.state = ConversationState.EXPLAIN
        elif self.state == ConversationState.EXPLAIN:
            self.state = ConversationState.ASK
        elif self.state == ConversationState.ASK:
            self.state = ConversationState.REACT
        elif self.state == ConversationState.REACT:
            self.state = ConversationState.EXPAND
        elif self.state == ConversationState.EXPAND:
            # Loop back
            self.state = ConversationState.ASK

        # Extract opinions if we have memory
        if self.memory and user_input.strip() and self.current_topic:
            self.memory.extract_opinions_from_text(user_input, self.current_topic)

    def process_turn(self, user_input):
        """
        Process a full conversation turn.
        Returns the messages list for the LLM.
        """
        from llm.llm import build_messages

        system_prompt = self.get_system_prompt()

        # Handle empty input (silence)
        if not user_input.strip():
            user_input = "(The user is silent — prompt them with something interesting or ask a question)"

        messages = build_messages(
            system_prompt=system_prompt,
            history=self.history,
            user_input=user_input,
            topic_context=self.topic_context,
        )

        return messages

    def add_to_history(self, role, content):
        """Add a message to conversation history."""
        self.history.append({"role": role, "content": content})
        # Trim to prevent context overflow
        from config import MAX_HISTORY
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]

    def get_intro_prompt(self):
        """Generate the first message to kick off the podcast."""
        topic = self.current_topic or "something interesting"
        return (
            f"Let's start today's podcast episode! The topic is: {topic}. "
            f"Introduce it with energy and excitement. Hook the listener."
        )

    def handle_silence(self):
        """Generate a prompt when the user is silent too long."""
        prompts = [
            "The user has been quiet. Ask them an engaging question.",
            "Fill the silence with an interesting fact, then ask for their take.",
            "The user might be thinking. Offer a perspective and invite them to respond.",
            "Keep the conversation going! Share a story related to the topic.",
        ]
        idx = self.turn_count % len(prompts)
        return prompts[idx]
