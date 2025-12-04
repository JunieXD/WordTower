#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清理 StarDict SQLite 数据库（stardict.db）中的无效单词。

无效单词定义：`word` 字段中包含空格、双引号、单引号或逗号的单词。
清理方式：从 stardict 表中直接删除这些记录，并执行 VACUUM 以压缩数据库文件。

用法示例：
    uv run python -m app.scripts.clean_stardict_db              # 使用默认路径 app/scripts/stardict.db
    uv run python -m app.scripts.clean_stardict_db path/to.db   # 指定 sqlite 数据库路径
    uv run python -m app.scripts.clean_stardict_db --dry-run    # 仅统计，不实际删除
"""

import os
import sys
import sqlite3
from pathlib import Path


def get_default_db_path() -> str:
    """获取默认的 stardict.db 路径（位于 app/scripts/stardict.db）。"""
    project_root = Path(__file__).parent.parent.parent
    return str(project_root / "app" / "scripts" / "stardict.db")


def find_invalid_words(conn: sqlite3.Connection) -> tuple[int, list[str]]:
    """统计并抽样展示无效单词。

    返回：(无效单词数量, 示例单词列表)
    """
    where_clause = """
        word LIKE '% %'      -- 包含空格
        OR word LIKE '%"%'  -- 包含双引号
        OR word LIKE '%''%' -- 包含单引号
        OR word LIKE '%,%'  -- 包含逗号
    """

    cur = conn.cursor()

    # 统计无效单词数量
    cur.execute(f"SELECT COUNT(*) FROM stardict WHERE {where_clause};")
    count_row = cur.fetchone()
    invalid_count = count_row[0] if count_row else 0

    # 抽样展示前 20 个无效单词
    cur.execute(
        f"SELECT word FROM stardict WHERE {where_clause} ORDER BY word COLLATE NOCASE LIMIT 20;"
    )
    samples = [row[0] for row in cur.fetchall()]

    return invalid_count, samples


def clean_invalid_words(sqlite_path: str, dry_run: bool = False) -> None:
    """清理 SQLite stardict 数据库中的无效单词。"""
    if not os.path.exists(sqlite_path):
        print(f"错误: 数据库文件不存在: {sqlite_path}")
        return

    file_size_before = os.path.getsize(sqlite_path)

    print(f"正在打开 SQLite 数据库: {sqlite_path}")
    conn = sqlite3.connect(sqlite_path)

    try:
        cur = conn.cursor()

        # 总单词数量
        cur.execute("SELECT COUNT(*) FROM stardict;")
        total_row = cur.fetchone()
        total_count = total_row[0] if total_row else 0
        print(f"stardict 表中共有 {total_count} 条记录")

        invalid_count, samples = find_invalid_words(conn)
        print(f"检测到 {invalid_count} 条无效单词（包含空格/引号/逗号）")

        if not invalid_count:
            print("没有发现需要清理的无效单词。")
            return

        if samples:
            print("\n无效单词示例（最多 20 个）：")
            for w in samples:
                print(f"  - {w!r}")

        if dry_run:
            print("\n当前为 dry-run 模式，不会删除任何数据。")
            return

        confirm = input(f"\n确认从数据库中删除这 {invalid_count} 条无效单词吗？(yes/no): ")
        if confirm.lower() != "yes":
            print("已取消清理操作。")
            return

        # 实际删除
        where_clause = """
            word LIKE '% %'
            OR word LIKE '%"%'
            OR word LIKE '%''%'
            OR word LIKE '%,%'
        """
        print("\n正在删除无效单词...")
        cur.execute(f"DELETE FROM stardict WHERE {where_clause};")
        deleted = cur.rowcount
        conn.commit()
        print(f"已删除 {deleted} 条记录。")

        # VACUUM 以压缩数据库文件
        print("正在执行 VACUUM 以压缩数据库文件，这可能需要一点时间...")
        conn.execute("VACUUM;")
        conn.commit()

        file_size_after = os.path.getsize(sqlite_path)
        diff = file_size_before - file_size_after
        print("\n清理完成！")
        print(f"文件大小: {file_size_before} -> {file_size_after} 字节，减少 {diff} 字节。")

    except Exception as e:  # noqa: BLE001
        print(f"清理过程中发生错误: {e}")
        raise
    finally:
        conn.close()


def main() -> None:
    args = sys.argv[1:]

    # 判断是否是 dry-run
    dry_run = False
    if "--dry-run" in args:
        dry_run = True
        args = [a for a in args if a != "--dry-run"]

    if args:
        sqlite_path = args[0]
    else:
        sqlite_path = get_default_db_path()

    print(f"使用的数据库路径: {sqlite_path}")
    clean_invalid_words(sqlite_path, dry_run=dry_run)


if __name__ == "__main__":
    main()

