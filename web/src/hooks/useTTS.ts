"use client";

import { useCallback, useRef } from "react";
import { fetchTTSAudio } from "@/lib/api";

interface TTSHook {
  speak: (text: string) => void;
  /** Speak a single sentence immediately (used for streaming TTS). */
  speakSentence: (sentence: string) => void;
  stop: () => void;
  isSpeaking: boolean;
}

/**
 * Split text into chunks of max N sentences.
 * Returns array of chunk strings.
 */
function splitBySentence(text: string, maxSentences = 2): string[] {
  const sentences = text.split(/(?<=[.!?])\s+/).filter((s) => s.trim());
  if (sentences.length === 0) return text.trim() ? [text] : [];
  const chunks: string[] = [];
  for (let i = 0; i < sentences.length; i += maxSentences) {
    chunks.push(sentences.slice(i, i + maxSentences).join(" "));
  }
  return chunks;
}

/** Clean markdown/URLs for voice output */
function cleanForSpeech(text: string): string {
  return text
    .replace(/[*#`~_[\]()>]/g, "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Pick a good English voice if available */
function pickVoice(): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find(
      (v) =>
        v.lang.startsWith("en") &&
        (v.name.includes("Google") ||
          v.name.includes("Microsoft") ||
          v.name.includes("Daniel") ||
          v.name.includes("Samantha"))
    ) || null
  );
}

/**
 * Hybrid TTS hook with sentence-chunked playback:
 * - Splits reply into 2-sentence chunks
 * - Speaks chunk 1 immediately, queues chunk 2 while chunk 1 plays
 * - Perceived latency collapses from "wait→hear" to "hear in ~0s"
 * - Falls back to Coqui server TTS if browser TTS unavailable
 */
export function useTTS(): TTSHook {
  const speakingRef = useRef(false);
  const queueRef = useRef<string[]>([]);

  const stopSpeaking = useCallback(() => {
    queueRef.current = [];
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    speakingRef.current = false;
  }, []);

  /**
   * Speak a single chunk of text via browser SpeechSynthesis.
   * When it ends, automatically speaks the next queued chunk.
   */
  const speakNextChunk = useCallback(
    (chunk: string) => {
      if (typeof window === "undefined" || !window.speechSynthesis) return;

      const utterance = new SpeechSynthesisUtterance(chunk);
      utterance.rate = 1.15;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;
      utterance.lang = "en-US";

      const voice = pickVoice();
      if (voice) utterance.voice = voice;

      utterance.onstart = () => {
        speakingRef.current = true;
      };
      utterance.onend = () => {
        // If more chunks in queue, speak the next one
        const next = queueRef.current.shift();
        if (next) {
          speakNextChunk(next);
        } else {
          speakingRef.current = false;
        }
      };
      utterance.onerror = () => {
        // Try next chunk even on error
        const next = queueRef.current.shift();
        if (next) {
          speakNextChunk(next);
        } else {
          speakingRef.current = false;
        }
      };

      window.speechSynthesis.speak(utterance);
    },
    []
  );

  /**
   * Speak full text in sentence-chunked mode.
   * Splits into 2-sentence chunks, speaks first immediately,
   * queues the rest for sequential playback.
   */
  const speak = useCallback(
    (text: string) => {
      const clean = cleanForSpeech(text);
      if (!clean) return;

      // Try browser SpeechSynthesis first (instant, no network)
      if (typeof window !== "undefined" && window.speechSynthesis) {
        stopSpeaking();

        const chunks = splitBySentence(clean, 2);
        if (chunks.length === 0) return;

        // Queue chunks 2+ for sequential playback after chunk 1 finishes
        queueRef.current = chunks.slice(1);

        // Speak chunk 1 immediately
        speakNextChunk(chunks[0]);
        return;
      }

      // Fallback: Coqui TTS server (only speaks first chunk for speed)
      const chunks = splitBySentence(clean, 2);
      const firstChunk = chunks[0] || clean;

      speakingRef.current = true;
      fetchTTSAudio(firstChunk)
        .then((blob) => {
          const url = URL.createObjectURL(blob);
          const audio = new Audio(url);
          audio.playbackRate = 1.2;
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
    [stopSpeaking, speakNextChunk]
  );

  /**
   * Speak a single sentence immediately (for streaming TTS).
   * Does NOT clear the existing queue — appends to it so sentences
   * play back-to-back without gaps.
   */
  const speakSentence = useCallback(
    (sentence: string) => {
      const clean = cleanForSpeech(sentence);
      if (!clean) return;

      if (typeof window === "undefined" || !window.speechSynthesis) return;

      // If already speaking, queue it; otherwise start immediately
      if (speakingRef.current) {
        queueRef.current.push(clean);
      } else {
        speakNextChunk(clean);
      }
    },
    [speakNextChunk]
  );

  return {
    speak,
    speakSentence,
    stop: stopSpeaking,
    isSpeaking: speakingRef.current,
  };
}
