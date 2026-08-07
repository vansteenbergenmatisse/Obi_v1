"""Token counting and token-window splitting for chunk sizing.

Phase-3 chunk-size targets are expressed in tokens. Counting uses ``tiktoken`` when it is
installed (accurate for OpenAI models); otherwise a calibrated character/word heuristic is used.
Both backends satisfy the same invariants, so tests and behaviour do not depend on which is
present:

* ``count("") == 0`` and count grows with length;
* ``split`` never emits a window whose ``count`` exceeds ``max_tokens``;
* ``split`` cuts only on whitespace word boundaries (never mid-word), so chunk text stays
  human-readable — an over-long single token-less word is the sole exception and is hard-split.

The module is pure domain code: no I/O, no network, no framework imports.
"""

from __future__ import annotations

from math import ceil

# tiktoken is an optional dependency; degrade to the heuristic when it is absent.
try:  # pragma: no cover - import guard
    import tiktoken  # pyright: ignore[reportMissingImports]

    _TIKTOKEN_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    tiktoken = None  # type: ignore[assignment]
    _TIKTOKEN_AVAILABLE = False

# OpenAI text-embedding-3-* and gpt-4-class models use the cl100k_base encoding.
_DEFAULT_ENCODING = "cl100k_base"
_HEURISTIC_CHARS_PER_TOKEN = 4  # ~English average


class TokenCounter:
    """Counts tokens and splits text into token-bounded, word-aligned windows."""

    def __init__(self, encoding_name: str = _DEFAULT_ENCODING) -> None:
        self._enc = None
        if _TIKTOKEN_AVAILABLE:
            try:
                self._enc = tiktoken.get_encoding(  # pyright: ignore[reportOptionalMemberAccess]
                    encoding_name
                )
            except Exception:
                self._enc = None

    @property
    def backend(self) -> str:
        return "tiktoken" if self._enc is not None else "heuristic"

    def count(self, text: str) -> int:
        if not text or not text.strip():
            return 0
        if self._enc is not None:
            return len(self._enc.encode(text))
        # Heuristic: whichever of word-count / (chars/4) is larger, so we never badly under-count.
        words = len(text.split())
        chars_est = ceil(len(text) / _HEURISTIC_CHARS_PER_TOKEN)
        return max(words, chars_est)

    def split(self, text: str, max_tokens: int, overlap_tokens: int = 0) -> list[str]:
        """Split ``text`` into windows of at most ``max_tokens`` tokens, aligned to word breaks.

        Consecutive windows share ~``overlap_tokens`` of trailing context. Returns ``[]`` for
        empty input and ``[text]`` when the whole thing already fits.
        """
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if overlap_tokens >= max_tokens:
            raise ValueError("overlap_tokens must be < max_tokens")
        if not text or not text.strip():
            return []
        if self.count(text) <= max_tokens:
            return [text]

        atoms = self._atomize(text, max_tokens)
        windows: list[str] = []
        cur: list[str] = []
        for atom in atoms:
            if cur and self.count(" ".join(cur + [atom])) > max_tokens:
                windows.append(" ".join(cur))
                cur = self._overlap_tail(cur, overlap_tokens)
                cur.append(atom)
                # overlap tail + atom may still exceed max; trim from the front to restore invariant
                while len(cur) > 1 and self.count(" ".join(cur)) > max_tokens:
                    cur.pop(0)
            else:
                cur.append(atom)
        if cur:
            windows.append(" ".join(cur))
        return windows

    def _atomize(self, text: str, max_tokens: int) -> list[str]:
        """Whitespace words, with any over-long token-less word hard-split to fit ``max_tokens``."""
        atoms: list[str] = []
        for word in text.split():
            if self.count(word) <= max_tokens:
                atoms.append(word)
            else:
                atoms.extend(self._hard_split_word(word, max_tokens))
        return atoms

    def _hard_split_word(self, word: str, max_tokens: int) -> list[str]:
        if self._enc is not None:
            ids = self._enc.encode(word)
            return [
                self._enc.decode(ids[i : i + max_tokens])
                for i in range(0, len(ids), max_tokens)
            ]
        step = max(1, max_tokens * _HEURISTIC_CHARS_PER_TOKEN)
        return [word[i : i + step] for i in range(0, len(word), step)]

    def _overlap_tail(self, atoms: list[str], overlap_tokens: int) -> list[str]:
        if overlap_tokens <= 0:
            return []
        tail: list[str] = []
        total = 0
        for atom in reversed(atoms):
            c = self.count(atom)
            if total + c > overlap_tokens:
                break
            tail.insert(0, atom)
            total += c
        return tail
