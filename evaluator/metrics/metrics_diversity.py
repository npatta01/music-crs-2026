from __future__ import annotations
from typing import List, Sequence, Tuple

def _whitespace_tokens(text: str) -> List[str]:
    """Tokenize with whitespace split only (no normalization)."""
    return (text or "").split()


def compute_catalog_diversity(list_of_recommendations: Sequence[str], catalog_size: int) -> float:
    """
    Catalog diversity: (# unique recommended tracks) / (catalog size).
    """
    if catalog_size <= 0:
        return 0.0
    return len(set(list_of_recommendations)) / float(catalog_size)


def compute_lexical_diversity(list_of_responses: Sequence[str], n: int = 2) -> float:
    """
    Lexical diversity with Distinct-2.
    """
    ngrams = set()
    total_ngrams = 0

    for response in list_of_responses:
        tokens = _whitespace_tokens(response.lower())
        if len(tokens) < n:
            continue

        for i in range(len(tokens) - n + 1):
            ngram = tuple(tokens[i:i+n])
            ngrams.add(ngram)
            total_ngrams += 1

    if total_ngrams == 0:
        return 0.0

    return len(ngrams) / float(total_ngrams)
