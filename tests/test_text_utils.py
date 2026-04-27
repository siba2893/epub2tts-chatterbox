"""Unit tests for epub2tts_chatterbox.text_utils."""
import pytest

from epub2tts_chatterbox.text_utils import (
    combine_short_paragraphs,
    combine_short_sentences,
    conditional_sentence_case,
    format_time_adaptive,
    sort_key,
)


class TestConditionalSentenceCase:
    def test_three_uppercase_words_triggers_lowercase(self):
        assert conditional_sentence_case("HELLO WORLD FOO bar") == "Hello world foo bar"

    def test_two_uppercase_words_left_alone(self):
        # Only two consecutive uppercase words => no transform
        assert conditional_sentence_case("HELLO WORLD bar baz") == "HELLO WORLD bar baz"

    def test_normal_sentence_unchanged(self):
        s = "The quick brown fox jumps over the lazy dog."
        assert conditional_sentence_case(s) == s

    def test_empty_string(self):
        assert conditional_sentence_case("") == ""

    def test_single_word(self):
        assert conditional_sentence_case("HELLO") == "HELLO"

    def test_uppercase_run_in_middle(self):
        # "ALL CAPS HERE" is 3 consecutive uppercase => transform
        assert (
            conditional_sentence_case("the cat said ALL CAPS HERE loudly")
            == "The cat said all caps here loudly"
        )

    def test_mixed_punctuation_preserved_after_lowercase(self):
        # Punctuation rides along with the word; .lower().capitalize() preserves it
        result = conditional_sentence_case("THE END IS NIGH!")
        assert result == "The end is nigh!"


class TestFormatTimeAdaptive:
    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (0, "0s"),
            (1, "1s"),
            (59, "59s"),
            (60, "1m 0s"),
            (90, "1m 30s"),
            (3599, "59m 59s"),
            (3600, "1h 0m"),
            (3660, "1h 1m"),
            (7325, "2h 2m"),
            (36000, "10h 0m"),
        ],
    )
    def test_boundaries_and_examples(self, seconds, expected):
        assert format_time_adaptive(seconds) == expected

    def test_floats_truncated(self):
        # 75.9 seconds => 1m 15s (int truncation, not rounding)
        assert format_time_adaptive(75.9) == "1m 15s"


class TestSortKey:
    def test_simple_numeric_filename(self):
        assert sort_key("part1.flac") == 1

    def test_first_number_used(self):
        assert sort_key("part12.flac") == 12

    def test_picks_first_number_only(self):
        # By spec, sort_key uses the FIRST number it finds
        assert sort_key("sntnc7_v2.wav") == 7

    def test_sorts_numerically_not_lexically(self):
        files = ["part10.flac", "part2.flac", "part1.flac"]
        assert sorted(files, key=sort_key) == ["part1.flac", "part2.flac", "part10.flac"]

    def test_no_number_raises(self):
        with pytest.raises(IndexError):
            sort_key("noNumberHere.wav")


class TestCombineShortParagraphs:
    def test_empty_input(self):
        assert combine_short_paragraphs([]) == []

    def test_short_single_sentence_merges_into_next(self):
        # "He left." (2 words) merges with the next paragraph
        paragraphs = [
            "He left.",
            "The morning came and the city woke up to a quiet hum of distant traffic.",
        ]
        result = combine_short_paragraphs(paragraphs)
        assert len(result) == 1
        assert result[0].startswith("He left. The morning")

    def test_long_paragraph_left_alone(self):
        long_para = "This paragraph has more than six words in it definitely."
        result = combine_short_paragraphs([long_para, "Another long paragraph follows after this one here."])
        assert result == [long_para, "Another long paragraph follows after this one here."]

    def test_multi_sentence_short_paragraph_left_alone(self):
        # Two short sentences but multiple sentences => not merged
        para = "Yes. No."
        result = combine_short_paragraphs([para, "Long enough paragraph follows now okay."])
        assert result[0] == "Yes. No."

    def test_short_final_paragraph_kept_as_is(self):
        # No next paragraph to merge with => stays
        result = combine_short_paragraphs(["Hi there."])
        assert result == ["Hi there."]

    def test_min_words_threshold_respected(self):
        # With min_words=3, "Yes I know." (3 words) should NOT merge
        paragraphs = ["Yes I know.", "Long enough paragraph follows."]
        result = combine_short_paragraphs(paragraphs, min_words=3)
        assert result == paragraphs


class TestCombineShortSentences:
    def test_empty_input(self):
        assert combine_short_sentences([]) == []

    def test_long_sentences_pass_through(self):
        sents = [
            "This sentence has more than eight words inside it for sure.",
            "Another long sentence with plenty of words to clear the threshold.",
        ]
        result = combine_short_sentences(sents)
        assert result == sents

    def test_short_sentences_combined(self):
        # Each sentence is short; should be merged into fewer chunks
        sents = ["Yes.", "No.", "Maybe.", "I am unsure."]
        result = combine_short_sentences(sents)
        # Result should have fewer items than input and each chunk should
        # combine the original text in order.
        assert len(result) < len(sents)
        joined = " ".join(result)
        for s in sents:
            assert s in joined

    def test_trailing_short_chunk_merged_with_previous(self):
        sents = [
            "This is a long enough sentence to stand on its own absolutely.",
            "Tiny.",
        ]
        result = combine_short_sentences(sents)
        # "Tiny." is 1 word (< min_words=6); it should attach to the previous chunk
        assert len(result) == 1
        assert result[0].endswith("Tiny.")

    def test_keep_threshold_respected(self):
        # A 9-word sentence (>= keep_threshold=8) at the start should be emitted
        # standalone. The trailing run is sized to reach min_words on its own so
        # the end-of-loop merge rule does not absorb it back into the long sentence.
        sents = [
            "One two three four five six seven eight nine.",
            "Tiny.", "Bit.", "More.", "Words.", "Here.", "Now.",
        ]
        result = combine_short_sentences(sents, min_words=6, keep_threshold=8)
        assert result[0] == "One two three four five six seven eight nine."
        assert len(result) >= 2

    def test_word_order_preserved(self):
        sents = ["Alpha.", "Beta.", "Gamma.", "Delta epsilon zeta eta theta iota."]
        result = combine_short_sentences(sents)
        joined = " ".join(result)
        for token in ["Alpha", "Beta", "Gamma", "Delta", "epsilon", "iota"]:
            assert token in joined
        assert joined.index("Alpha") < joined.index("Beta") < joined.index("Gamma")
