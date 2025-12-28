"""
Tests for entity name normalization module.

Tests domain-agnostic normalization that preserves valid entity names
like "Dr. Pepper" and "Mr. Robot" while normalizing for comparison.
"""

from __future__ import annotations

from app.kg.normalization import (
    generate_ngrams,
    normalize_entity_name,
    normalize_for_index,
)


class TestNormalizeEntityName:
    """Tests for normalize_entity_name function."""

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert normalize_entity_name("") == ""

    def test_none_like_handling(self) -> None:
        """Empty-ish strings normalize to empty."""
        assert normalize_entity_name("   ") == ""
        assert normalize_entity_name("\t\n") == ""

    def test_basic_casefold(self) -> None:
        """Basic case folding works."""
        assert normalize_entity_name("JOHN SMITH") == "john smith"
        assert normalize_entity_name("John Smith") == "john smith"
        assert normalize_entity_name("john smith") == "john smith"

    def test_whitespace_normalization(self) -> None:
        """Multiple whitespace collapses to single space."""
        assert normalize_entity_name("  John   Smith  ") == "john smith"
        assert normalize_entity_name("John\tSmith") == "john smith"
        assert normalize_entity_name("John\nSmith") == "john smith"

    def test_unicode_nfkc_normalization(self) -> None:
        """Unicode NFKC normalization handles compatibility characters."""
        # Ligatures
        assert normalize_entity_name("ﬁle") == "file"
        assert normalize_entity_name("ﬂow") == "flow"

        # Fullwidth characters
        assert normalize_entity_name("ABC") == "abc"

        # Accented characters stay (NFKC doesn't strip accents)
        # but casefold handles them
        assert normalize_entity_name("Cafe") == "cafe"

    def test_casefold_unicode_edge_cases(self) -> None:
        """Casefold handles Unicode edge cases better than lower()."""
        # German eszett - casefold converts to "ss"
        # Note: "Strasse" with eszett
        assert normalize_entity_name("STRASSE") == "strasse"

        # Turkish dotless i - casefold handles it
        result = normalize_entity_name("I")
        assert result == "i"

    def test_leading_trailing_punctuation_stripped(self) -> None:
        """Leading/trailing punctuation is stripped."""
        assert normalize_entity_name('"John Smith"') == "john smith"
        assert normalize_entity_name("(John Smith)") == "john smith"
        assert normalize_entity_name("John Smith.") == "john smith"
        assert normalize_entity_name(",John Smith,") == "john smith"

    def test_internal_punctuation_preserved(self) -> None:
        """Internal punctuation is NOT stripped."""
        # This is critical for domain-agnostic design
        assert normalize_entity_name("Dr. Pepper") == "dr. pepper"
        assert normalize_entity_name("Mr. Robot") == "mr. robot"
        assert normalize_entity_name("O'Brien") == "o'brien"
        assert normalize_entity_name("Self-Aware") == "self-aware"

    def test_domain_agnostic_preservation(self) -> None:
        """
        Domain-agnostic design: honorifics and suffixes are NOT stripped.

        "Dr. Pepper" is a valid entity name (the drink).
        "Mr. Robot" is a valid entity name (the TV show).
        We cannot assume what domain we're in.
        """
        # These should NOT have prefixes stripped
        assert normalize_entity_name("Dr. Pepper") == "dr. pepper"
        assert normalize_entity_name("Dr. John Smith") == "dr. john smith"
        assert normalize_entity_name("Mr. Robot") == "mr. robot"
        assert normalize_entity_name("Mrs. Doubtfire") == "mrs. doubtfire"

        # Corporate suffixes - trailing punctuation is stripped but internal preserved
        # "Apple Inc." -> "apple inc" (trailing period stripped)
        # "OpenAI, LLC" -> "openai, llc" (comma preserved, no trailing punct)
        assert normalize_entity_name("Apple Inc.") == "apple inc"
        assert normalize_entity_name("OpenAI, LLC") == "openai, llc"
        # Internal punctuation preserved
        assert normalize_entity_name("AT&T Inc.") == "at&t inc"


class TestGenerateNgrams:
    """Tests for generate_ngrams function."""

    def test_empty_string(self) -> None:
        """Empty string returns empty set."""
        assert generate_ngrams("") == set()
        assert generate_ngrams("   ") == set()

    def test_short_string_less_than_n(self) -> None:
        """Strings shorter than n return the whole string."""
        assert generate_ngrams("ab") == {"ab"}
        assert generate_ngrams("a") == {"a"}
        assert generate_ngrams("AB") == {"ab"}  # Also normalized

    def test_normal_trigrams(self) -> None:
        """Normal strings generate correct trigrams."""
        result = generate_ngrams("hello")
        expected = {"hel", "ell", "llo"}
        assert result == expected

    def test_trigrams_with_spaces(self) -> None:
        """Spaces are included in ngrams."""
        result = generate_ngrams("ab cd")
        # Normalized: "ab cd" (5 chars)
        # Trigrams: "ab ", "b c", " cd"
        expected = {"ab ", "b c", " cd"}
        assert result == expected

    def test_ngrams_are_normalized(self) -> None:
        """Input is normalized before generating ngrams."""
        # Uppercase should be casefolded
        result = generate_ngrams("HELLO")
        expected = {"hel", "ell", "llo"}
        assert result == expected

        # Whitespace should be collapsed
        result = generate_ngrams("ab  cd")
        expected = {"ab ", "b c", " cd"}
        assert result == expected

    def test_custom_n_value(self) -> None:
        """Custom n values work correctly."""
        # Bigrams
        result = generate_ngrams("hello", n=2)
        expected = {"he", "el", "ll", "lo"}
        assert result == expected

        # 4-grams
        result = generate_ngrams("hello", n=4)
        expected = {"hell", "ello"}
        assert result == expected

    def test_ngrams_for_short_names(self) -> None:
        """Short entity names still produce useful output."""
        # "Li" - common Chinese surname
        assert generate_ngrams("Li") == {"li"}

        # "Xu" - common Chinese surname
        assert generate_ngrams("Xu") == {"xu"}


class TestNormalizeForIndex:
    """Tests for normalize_for_index function."""

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert normalize_for_index("") == ""

    def test_removes_spaces(self) -> None:
        """Spaces are removed for index keys."""
        assert normalize_for_index("John Smith") == "johnsmith"
        assert normalize_for_index("John  Smith") == "johnsmith"

    def test_removes_punctuation(self) -> None:
        """Common punctuation is removed."""
        assert normalize_for_index("O'Brien") == "obrien"
        assert normalize_for_index("Self-Aware") == "selfaware"
        assert normalize_for_index("Dr. Jane Doe") == "drjanedoe"

    def test_casefolds(self) -> None:
        """Casefolding is applied."""
        assert normalize_for_index("JOHN SMITH") == "johnsmith"
        assert normalize_for_index("John Smith") == "johnsmith"

    def test_fuzzy_matching_use_case(self) -> None:
        """
        Index normalization enables fuzzy key matching.

        These should all produce the same index key.
        """
        variations = [
            "John Smith",
            "john smith",
            "JOHN SMITH",
            "John  Smith",
            "John-Smith",
        ]
        keys = [normalize_for_index(v) for v in variations]
        assert all(k == "johnsmith" for k in keys)


class TestNormalizationIntegration:
    """Integration tests for normalization across the resolution system."""

    def test_consistent_normalization_for_matching(self) -> None:
        """
        Same entity with different representations should normalize similarly.
        """
        # Person with variations
        assert normalize_entity_name("Elon Musk") == normalize_entity_name("elon musk")
        assert normalize_entity_name("Elon Musk") == normalize_entity_name("ELON MUSK")

        # Organization with variations
        assert normalize_entity_name("OpenAI") == normalize_entity_name("openai")

    def test_ngrams_catch_typos(self) -> None:
        """
        N-gram blocking should catch common typos.

        Names with similar trigrams will share blocking buckets.
        """
        # "Smith" vs "Smtih" (transposition)
        ngrams_correct = generate_ngrams("John Smith")
        ngrams_typo = generate_ngrams("John Smtih")

        # They should share some ngrams (at least "joh", "ohn", "hn ")
        shared = ngrams_correct & ngrams_typo
        assert len(shared) >= 2  # Enough for blocking

    def test_index_normalization_for_dedup(self) -> None:
        """
        Index normalization helps with deduplication lookups.
        """
        # These should all map to same key
        assert (
            normalize_for_index("Dr. John Smith")
            == normalize_for_index("Dr John Smith")
        )


class TestEdgeCases:
    """Edge case tests."""

    def test_unicode_combining_characters(self) -> None:
        """Combining characters are handled via NFKC."""
        # e + combining acute accent
        composed = "caf\u00e9"  # cafe with e-acute
        decomposed = "cafe\u0301"  # cafe + combining acute

        # After NFKC normalization, these should be equivalent
        assert normalize_entity_name(composed) == normalize_entity_name(decomposed)

    def test_special_punctuation(self) -> None:
        """Special punctuation characters are handled."""
        # Guillemets (French quotes)
        assert normalize_entity_name("...John...") == "john"

        # Various quotes
        assert normalize_entity_name("'John'") == "john"
        assert normalize_entity_name('"John"') == "john"

    def test_numbers_preserved(self) -> None:
        """Numbers in entity names are preserved."""
        assert normalize_entity_name("Agent 007") == "agent 007"
        assert normalize_entity_name("F-16") == "f-16"
        assert normalize_entity_name("3M Company") == "3m company"

    def test_long_strings(self) -> None:
        """Long strings are handled correctly."""
        long_name = "The Very Long Organization Name That Goes On And On"
        result = normalize_entity_name(long_name)
        assert result == long_name.casefold()

        # Ngrams should work on long strings
        ngrams = generate_ngrams(long_name)
        assert len(ngrams) > 0

    def test_single_character(self) -> None:
        """Single character entities work."""
        assert normalize_entity_name("X") == "x"
        assert generate_ngrams("X") == {"x"}
        assert normalize_for_index("X") == "x"
