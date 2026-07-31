from backend.platforms.fanqie.text_utils import (
    chapter_len,
    count_non_whitespace_chars,
    count_platform_estimated_chars,
    is_platform_count_compatible,
)


def test_platform_estimate_ignores_whitespace_and_non_ascii_symbols() -> None:
    assert count_platform_estimated_chars("你 好\n★░😀世界") == 4


def test_platform_estimate_collapses_ascii_word_and_number_runs() -> None:
    assert count_platform_estimated_chars("你好 worker30 世界") == 5
    assert count_platform_estimated_chars("A1B2") == 1


def test_platform_estimate_keeps_ascii_punctuation() -> None:
    assert count_platform_estimated_chars("你~好!") == 4


def test_generic_non_whitespace_counter_keeps_utf16_semantics() -> None:
    assert count_non_whitespace_chars("你 😀") == 3


def test_chapter_length_uses_platform_estimate_and_keeps_tolerance() -> None:
    assert chapter_len("你好 worker30 世界") == 5
    assert is_platform_count_compatible(actual=1000, expected=1080) is True
