from pathlib import Path

import pytest

from backend.features.novel_processing.chapter_parser import (
    load_chapters_by_number,
    parse_chapter_blocks,
    parse_chapter_source,
    parse_chapters_file,
)


def test_parser_supports_chinese_and_full_width_chapter_numbers() -> None:
    chapters = parse_chapter_blocks("第十二章 风起\n\n正文一\n\n第１３章 云涌\n\n正文二")

    assert [chapter.number for chapter in chapters] == [12, 13]
    assert [chapter.subtitle for chapter in chapters] == ["风起", "云涌"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("第1章 开始\n\n正文\n\n第1章 重复\n\n正文", "重复章节"),
        ("第2章 在前\n\n正文\n\n第1章 在后\n\n正文", "章节顺序异常"),
    ],
)
def test_single_file_rejects_duplicate_or_out_of_order_chapters(
    tmp_path: Path,
    text: str,
    message: str,
) -> None:
    novel = tmp_path / "novel.txt"
    novel.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        parse_chapters_file(novel)


def test_folder_source_orders_chapter_files_by_number(tmp_path: Path) -> None:
    (tmp_path / "第十二章-后章.txt").write_text("后章正文", encoding="utf-8")
    (tmp_path / "第2章-前章.txt").write_text("前章正文", encoding="utf-8")
    (tmp_path / "说明.txt").write_text("这不是章节", encoding="utf-8")

    chapters = parse_chapter_source(tmp_path)

    assert [chapter.number for chapter in chapters] == [2, 12]
    assert [chapter.subtitle for chapter in chapters] == ["前章", "后章"]


def test_multiple_sources_reject_duplicate_chapter_numbers_when_loaded(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("第1章 第一版\n\n正文", encoding="utf-8")
    second.write_text("第1章 第二版\n\n正文", encoding="utf-8")

    with pytest.raises(ValueError, match="重复章节"):
        load_chapters_by_number(f"{first}\n{second}", [1])
