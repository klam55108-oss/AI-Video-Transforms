"""
Entity name normalization for consistent matching.

Domain-agnostic design: No hardcoded honorifics or corporate suffixes.
Entity types are inferred at runtime during bootstrap, so we cannot
assume specific name patterns like "Dr." or "Inc."
"""

from __future__ import annotations

import re
import unicodedata


def normalize_entity_name(name: str) -> str:
    """
    Normalize entity name for comparison (domain-agnostic).

    Steps:
    1. Unicode NFKC normalization (compatibility decomposition)
    2. Casefold (better than lower() for Unicode)
    3. Collapse whitespace
    4. Strip leading/trailing punctuation only

    Does NOT strip honorifics/suffixes - "Dr. Pepper" and "Mr. Robot"
    are valid entity names that should NOT be modified.

    Args:
        name: The entity name to normalize.

    Returns:
        Normalized name for comparison.

    Examples:
        >>> normalize_entity_name("  John  Smith  ")
        'john smith'
        >>> normalize_entity_name("Cafe")
        'cafe'
        >>> normalize_entity_name("Dr. Pepper")
        'dr. pepper'
    """
    if not name:
        return ""

    # Unicode normalization (handles cafe->cafe, fi->fi, etc.)
    text = unicodedata.normalize("NFKC", name)

    # Casefold for case-insensitive comparison (handles ss->ss, I->i, etc.)
    text = text.casefold()

    # Normalize whitespace (collapse runs, trim)
    text = " ".join(text.split())

    # Strip only leading/trailing punctuation, preserve internal
    text = text.strip(".,;:!?\"'()[]{}...")

    return text


def generate_ngrams(text: str, n: int = 3) -> set[str]:
    """
    Generate character n-grams for blocking.

    Normalizes first, then extracts overlapping n-grams.
    Short strings (< n chars) return the whole string as a single "gram".

    Args:
        text: The text to generate n-grams from.
        n: The size of each n-gram (default: 3 for trigrams).

    Returns:
        Set of n-gram strings.

    Examples:
        >>> sorted(generate_ngrams("hello"))
        ['ell', 'hel', 'llo']
        >>> generate_ngrams("ab")
        {'ab'}
        >>> generate_ngrams("")
        set()
    """
    normalized = normalize_entity_name(text)
    if len(normalized) < n:
        return {normalized} if normalized else set()
    return {normalized[i : i + n] for i in range(len(normalized) - n + 1)}


def normalize_for_index(name: str) -> str:
    """
    Normalize name for index lookup (more aggressive).

    Used for label_to_id and alias_to_id indices.
    Removes ALL punctuation and spaces for fuzzy key matching.

    Args:
        name: The name to normalize for indexing.

    Returns:
        Normalized key suitable for index lookup.

    Examples:
        >>> normalize_for_index("John Smith")
        'johnsmith'
        >>> normalize_for_index("O'Brien")
        'obrien'
        >>> normalize_for_index("Dr. Jane Doe")
        'drjanedoe'
    """
    normalized = normalize_entity_name(name)
    # Remove spaces and remaining punctuation for index key
    return re.sub(r"[\s\-'.,:;!?\"()[\]{}]", "", normalized)
