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


def test_single_file_keeps_last_duplicate_chapter(tmp_path: Path) -> None:
    novel = tmp_path / "novel.txt"
    novel.write_text(
        "第1章 开始\n\n正文一\n\n第2章 重复\n\n旧正文\n\n第2章 重复\n\n新正文\n\n第3章 收尾\n\n正文三",
        encoding="utf-8",
    )

    chapters = parse_chapters_file(novel)

    assert [chapter.number for chapter in chapters] == [1, 2, 3]
    chapter_two = next(chapter for chapter in chapters if chapter.number == 2)
    assert chapter_two.body == "新正文"


def test_single_file_rejects_out_of_order_chapters(tmp_path: Path) -> None:
    novel = tmp_path / "novel.txt"
    novel.write_text("第2章 在前\n\n正文\n\n第1章 在后\n\n正文", encoding="utf-8")

    with pytest.raises(ValueError, match="章节顺序异常"):
        parse_chapters_file(novel)


def test_folder_source_orders_chapter_files_by_number(tmp_path: Path) -> None:
    (tmp_path / "第十二章-后章.txt").write_text("后章正文", encoding="utf-8")
    (tmp_path / "第2章-前章.txt").write_text("前章正文", encoding="utf-8")
    (tmp_path / "说明.txt").write_text("这不是章节", encoding="utf-8")

    chapters = parse_chapter_source(tmp_path)

    assert [chapter.number for chapter in chapters] == [2, 12]
    assert [chapter.subtitle for chapter in chapters] == ["前章", "后章"]


def test_multiple_sources_keep_last_duplicate_chapter_when_loaded(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("第1章 第一版\n\n旧正文", encoding="utf-8")
    second.write_text("第1章 第二版\n\n新正文", encoding="utf-8")

    loaded = load_chapters_by_number(f"{first}\n{second}", [1])

    assert loaded[1].body == "新正文"
