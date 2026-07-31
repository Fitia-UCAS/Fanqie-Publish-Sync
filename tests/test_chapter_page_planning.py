from backend.platforms.fanqie.pages.chapter_list import planned_reverse_page_numbers


def test_reverse_chapter_pages_are_calculated_from_latest_chapter() -> None:
    assert planned_reverse_page_numbers(86, {86, 60, 1}) == [1, 2, 6]


def test_reverse_chapter_pages_ignore_numbers_outside_remote_catalog() -> None:
    assert planned_reverse_page_numbers(86, {0, 87, 71, 70}) == [2]
