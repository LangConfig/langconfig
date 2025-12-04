# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Token counting service for accurate token measurement.
Uses tiktoken for OpenAI-compatible token counting.
"""

from typing import List, Optional
import tiktoken
from functools import lru_cache


class TokenCounter:
    """Service for counting tokens in text using tiktoken."""

    def __init__(self, encoding_name: str = "cl100k_base"):
        """
        Initialize token counter.

        Args:
            encoding_name: Tiktoken encoding to use. Options:
                - "cl100k_base": GPT-4, GPT-3.5-turbo, text-embedding-ada-002
                - "p50k_base": Codex models, text-davinci-002, text-davinci-003
                - "r50k_base": GPT-3 models like davinci
        """
        self.encoding_name = encoding_name
        self._encoding = None

    @property
    def encoding(self):
        """Lazy load encoding to avoid initialization cost."""
        if self._encoding is None:
            self._encoding = tiktoken.get_encoding(self.encoding_name)
        return self._encoding

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in a single text string.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        if not text:
            return 0

        try:
            tokens = self.encoding.encode(text)
            return len(tokens)
        except Exception as e:
            # Fallback: rough estimate (chars / 4)
            print(f"Token counting error: {e}, using fallback estimate")
            return len(text) // 4

    def count_tokens_batch(self, texts: List[str]) -> List[int]:
        """
        Count tokens for multiple texts efficiently.

        Args:
            texts: List of texts to count tokens for

        Returns:
            List of token counts in same order as input
        """
        return [self.count_tokens(text) for text in texts]

    def count_tokens_with_details(self, text: str) -> dict:
        """
        Count tokens and provide detailed breakdown.

        Args:
            text: Text to analyze

        Returns:
            Dict with token_count, char_count, tokens_per_char ratio
        """
        token_count = self.count_tokens(text)
        char_count = len(text)

        return {
            "token_count": token_count,
            "char_count": char_count,
            "tokens_per_char": token_count / char_count if char_count > 0 else 0,
            "encoding": self.encoding_name
        }


# Global singleton instance
_token_counter_instance: Optional[TokenCounter] = None


def get_token_counter(encoding_name: str = "cl100k_base") -> TokenCounter:
    """
    Get or create global token counter instance.

    Args:
        encoding_name: Tiktoken encoding to use

    Returns:
        TokenCounter instance
    """
    global _token_counter_instance

    if _token_counter_instance is None:
        _token_counter_instance = TokenCounter(encoding_name)

    return _token_counter_instance


@lru_cache(maxsize=1024)
def count_tokens_cached(text: str, encoding_name: str = "cl100k_base") -> int:
    """
    Count tokens with caching for repeated texts.
    Useful for counting same chunks multiple times.

    Args:
        text: Text to count
        encoding_name: Tiktoken encoding

    Returns:
        Number of tokens
    """
    counter = get_token_counter(encoding_name)
    return counter.count_tokens(text)
