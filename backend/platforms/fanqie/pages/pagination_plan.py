from __future__ import annotations


CHAPTERS_PER_PAGE = 15


def planned_reverse_page_numbers(
    latest_chapter_no: int,
    chapter_numbers: set[int] | list[int],
    *,
    page_size: int = CHAPTERS_PER_PAGE,
) -> list[int]:
    """番茄列表按新到旧排列：用最新章号推算目标章所在页。"""
    if latest_chapter_no < 1 or page_size < 1:
        return []
    return sorted(
        {
            ((latest_chapter_no - int(chapter_no)) // page_size) + 1
            for chapter_no in chapter_numbers
            if 0 < int(chapter_no) <= latest_chapter_no
        }
    )


__all__ = ["CHAPTERS_PER_PAGE", "planned_reverse_page_numbers"]
