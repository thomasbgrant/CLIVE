"""
Similarity scoring between user prompt and context text.

Uses Jaccard similarity on word-level token sets as a simple,
scale-independent baseline measure. This module is designed to be
extended with more sophisticated metrics later (e.g., TF-IDF cosine,
embedding-based similarity).
"""
import re
from collections import Counter


def _tokenize(text: str) -> list[str]:
    """
    Simple word-level tokenizer.
    Lowercases, strips punctuation, removes very short tokens.
    """
    # Lowercase and split on non-alphanumeric boundaries
    tokens = re.findall(r"[a-z0-9_]{2,}", text.lower())
    return tokens


def compute_jaccard_similarity(text_a: str, text_b: str) -> float:
    """
    Compute Jaccard similarity between two texts.

    Jaccard = |A ∩ B| / |A ∪ B|

    Returns a value in [0.0, 1.0] where:
        0.0 = no overlap in vocabulary
        1.0 = identical vocabulary

    This is scale-independent — it doesn't matter if one text is
    much longer than the other; it only measures vocabulary overlap.

    Args:
        text_a: First text (typically the user prompt).
        text_b: Second text (typically the aggregated context/tool results).

    Returns:
        Jaccard similarity score.
    """
    if not text_a or not text_b:
        return 0.0

    set_a = set(_tokenize(text_a))
    set_b = set(_tokenize(text_b))

    if not set_a or not set_b:
        return 0.0

    intersection = set_a & set_b
    union = set_a | set_b

    return len(intersection) / len(union)
