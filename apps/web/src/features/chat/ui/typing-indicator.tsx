/**
 * TypingIndicator — replaces the greeting/thread while waiting for the first token,
 * citations, or `done` event on the live SSE stream (PLAN 4.7.2). Real backend timing, not
 * the mockup's fake `setTimeout` — this component only owns the word-cycling animation.
 *
 * Feature-internal (used once, by `MessageBubble`).
 */
"use client";

import { useEffect, useState } from "react";
import { AssistantMark } from "./assistant-mark";

/** The mockup's exact ~90-word list (`Obi Assistant.dc.html`'s `THINK` constant) — personality
 * flavor text with no product-specific content, safe to reuse verbatim. */
const THINK_WORDS = [
  "Thinking", "Pondering", "Mulling", "Noodling", "Percolating", "Brewing", "Cogitating",
  "Ruminating", "Marinating", "Simmering", "Scheming", "Tinkering", "Puzzling", "Musing",
  "Contemplating", "Deliberating", "Reflecting", "Considering", "Processing", "Computing",
  "Crunching", "Untangling", "Unravelling", "Connecting dots", "Consulting the manual",
  "Digging in", "Sleuthing", "Investigating", "Cross-referencing", "Double-checking",
  "Reasoning", "Weighing options", "Herding thoughts", "Warming up neurons", "Spinning gears",
  "Turning cogs", "Assembling ideas", "Gathering context", "Reading the docs",
  "Flipping through notes", "Sharpening pencils", "Brainstorming", "Ideating", "Synthesizing",
  "Distilling", "Polishing", "Formulating", "Drafting", "Hatching a plan", "Conjuring",
  "Summoning knowledge", "Channeling expertise", "Focusing", "Zeroing in",
  "Piecing it together", "Doing the math", "Checking twice", "Looking it up",
  "Wrangling data", "Aligning the stars", "Dusting off archives", "Squinting thoughtfully",
  "Rummaging", "Decoding", "Calibrating", "Triangulating", "Incubating", "Fermenting",
  "Whirring", "Buzzing", "Booping", "Beeping", "Levitating ideas", "Stacking blocks",
  "Sorting thoughts", "Combing through", "Sifting", "Panning for gold", "Excavating",
  "Mapping it out", "Charting a course", "Plotting", "Orchestrating", "Composing",
  "Harmonizing", "Tuning", "Rehearsing", "Warming up", "Stretching", "Limbering up",
  "Taking a breath", "Counting to ten", "Consulting Obi-wisdom", "Peering into the docs",
  "Untying knots", "Ironing wrinkles", "Smoothing edges", "Finding the thread",
  "Following the trail", "Chasing the answer", "Almost there",
] as const;

function pickWord(excluding: string): string {
  let word: string;
  do {
    word = THINK_WORDS[Math.floor(Math.random() * THINK_WORDS.length)];
  } while (word === excluding && THINK_WORDS.length > 1);
  return word;
}

export function TypingIndicator() {
  const [word, setWord] = useState(() => pickWord(""));

  useEffect(() => {
    const interval = setInterval(() => {
      setWord((current) => pickWord(current));
    }, 3800);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-[9px] py-xs" data-testid="typing-indicator">
      <AssistantMark size={17} className="motion-safe:animate-[typing-spin_1.4s_ease-in-out_infinite]" />
      <span
        data-testid="typing-word"
        className="bg-[linear-gradient(90deg,#9aa1b2_30%,#30313d_50%,#9aa1b2_70%)] bg-[length:200%_100%] bg-clip-text text-[13.5px] font-medium text-transparent motion-safe:animate-[typing-shimmer_1.6s_linear_infinite]"
        aria-hidden="true"
      >
        {word}…
      </span>
      <span className="sr-only">Assistant is thinking</span>
    </div>
  );
}
