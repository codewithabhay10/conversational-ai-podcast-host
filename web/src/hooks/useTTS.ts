"use client";

import { useCallback, useRef } from "react";
import { fetchTTSAudio } from "@/lib/api";

interface TTSHook {
  speak: (text: string) => void;
  stop: () => void;
  isSpeaking: boolean;
}

/**
 * Hybrid TTS hook:
 * - Uses browser SpeechSynthesis for instant playback (no server round-trip)
 * - Falls back to Coqui server TTS if browser TTS unavailable
 */
export function useTTS(): TTSHook {
  const speakingRef = useRef(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  const stopSpeaking = useCallback(() => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    speakingRef.current = false;
  }, []);

  const speak = useCallback(
    (text: string) => {
      if (!text.trim()) return;

      // Clean text for speech
      const clean = text
        .replace(/[*#`~_[\]()>]/g, "")
        .replace(/https?:\/\/\S+/g, "")
        .replace(/\s+/g, " ")
        .trim();
      if (!clean) return;

      // Try browser SpeechSynthesis first (instant, no network)
      if (typeof window !== "undefined" && window.speechSynthesis) {
        stopSpeaking();

        // Truncate for speed — only speak first ~300 chars at sentence boundary
        let toSpeak = clean;
        if (toSpeak.length > 300) {
          const idx = toSpeak.lastIndexOf(".", 300);
          toSpeak = idx > 50 ? toSpeak.slice(0, idx + 1) : toSpeak.slice(0, 300);
        }

        const utterance = new SpeechSynthesisUtterance(toSpeak);
        utterance.rate = 1.15; // slightly faster than default
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        utterance.lang = "en-US";

        // Try to pick a good voice
        const voices = window.speechSynthesis.getVoices();
        const preferred = voices.find(
          (v) =>
            v.lang.startsWith("en") &&
            (v.name.includes("Google") ||
              v.name.includes("Microsoft") ||
              v.name.includes("Daniel") ||
              v.name.includes("Samantha"))
        );
        if (preferred) {
          utterance.voice = preferred;
        }

        utterance.onstart = () => {
          speakingRef.current = true;
        };
        utterance.onend = () => {
          speakingRef.current = false;
        };
        utterance.onerror = () => {
          speakingRef.current = false;
        };

        utteranceRef.current = utterance;
        window.speechSynthesis.speak(utterance);
        return;
      }

      // Fallback: fetch from Coqui TTS server
      speakingRef.current = true;
      fetchTTSAudio(clean)
        .then((blob) => {
          const url = URL.createObjectURL(blob);
          const audio = new Audio(url);
          audio.playbackRate = 1.2; // speed up server TTS playback
          audio.play();
          audio.onended = () => {
            URL.revokeObjectURL(url);
            speakingRef.current = false;
          };
        })
        .catch((err) => {
          console.error("TTS playback failed:", err);
          speakingRef.current = false;
        });
    },
    [stopSpeaking]
  );

  return {
    speak,
    stop: stopSpeaking,
    isSpeaking: speakingRef.current,
  };
}
