#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导入脚本：从 StarDict SQLite 数据库导入单词到 PostgreSQL
用法: uv run python -m app.scripts.import_words <sqlite_db_path>
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session, create_engine, select
from app.models.word import Word
from app.models.library_word_link import LibraryWordLink
from app.utils.config import settings
from app.scripts.stardict import StarDict


def map_difficulty(collins: int = None, oxford: int = None, bnc: int = None, frq: int = None) -> int:
    """
    根据单词的 collins、oxford、bnc、frq 等指标映射难度等级
    返回 1-5 的难度等级，1最简单，5最难
    """
    # Collins 星级 (0-5)
    if collins and collins >= 4:
        return 1  # 高频词，简单
    elif collins and collins >= 2:
        return 2

    # Oxford 3000 核心词汇
    if oxford and oxford > 0:
        return 2

    # BNC 频率 (越小越常用)
    if bnc:
        if bnc <= 3000:
            return 1
        elif bnc <= 8000:
            return 2
        elif bnc <= 15000:
            return 3
        else:
            return 4

    # FRQ 频率
    if frq:
        if frq <= 3000:
            return 1
        elif frq <= 8000:
            return 2
        elif frq <= 15000:
            return 3
        else:
            return 4

    # 默认中等难度
    return 3


def is_valid_word(word_text: str) -> bool:
    """
    验证单词是否有效
    跳过包含空格、引号、逗号的单词
    """
    if not word_text:
        return False
    
    # 检查是否包含空格、引号、逗号
    invalid_chars = [' ', '"', "'", ',']
    for char in invalid_chars:
        if char in word_text:
            return False
    
    return True


def extract_tags(word_data: dict) -> str:
    """
    从单词数据中提取标签
    """
    tags = []

    if word_data.get('collins'):
        tags.append(f"collins:{word_data['collins']}")

    if word_data.get('oxford'):
        tags.append("oxford3000")

    if word_data.get('tag'):
        tags.append(word_data['tag'])

    if word_data.get('bnc'):
        tags.append(f"bnc:{word_data['bnc']}")

    if word_data.get('frq'):
        tags.append(f"frq:{word_data['frq']}")

    return ','.join(tags) if tags else None


def import_words_from_sqlite(sqlite_path: str, batch_size: int = 10000):
    """
    从 SQLite 数据库导入单词到 PostgreSQL

    参数:
        sqlite_path: SQLite 数据库文件路径
        batch_size: 批量插入大小
    """
    if not os.path.exists(sqlite_path):
        print(f"错误: 数据库文件不存在: {sqlite_path}")
        return

    print(f"正在从 {sqlite_path} 导入单词...")

    # 打开 SQLite 数据库
    stardict = StarDict(sqlite_path, verbose=True)
    total_words = stardict.count()
    print(f"SQLite 数据库中共有 {total_words} 个单词")

    # 连接 PostgreSQL
    engine = create_engine(settings.DATABASE_URL)

    # 统计数据
    imported = 0
    skipped = 0
    errors = 0

    batch = []

    try:
        with Session(engine) as session:
            # 获取已存在的单词集合
            existing_words = set()
            result = session.exec(select(Word.text))
            for word_text in result:
                existing_words.add(word_text.lower())

            print(f"PostgreSQL 中已有 {len(existing_words)} 个单词")

            # 遍历 SQLite 中的所有单词
            for idx, word_text in stardict:
                word_data = stardict.query(word_text)

                if not word_data:
                    skipped += 1
                    continue

                # 验证单词是否有效（跳过包含空格、引号、逗号的单词）
                if not is_valid_word(word_text):
                    skipped += 1
                    continue

                # 跳过已存在的单词
                if word_text.lower() in existing_words:
                    skipped += 1
                    continue

                try:
                    # 映射字段
                    new_word = Word(
                        text=word_data['word'],
                        phonetic=word_data.get('phonetic'),
                        meaning=word_data.get('translation'),
                        difficulty=map_difficulty(
                            collins=word_data.get('collins'),
                            oxford=word_data.get('oxford'),
                            bnc=word_data.get('bnc'),
                            frq=word_data.get('frq')
                        ),
                        tags=word_data.get('tag')
                    )

                    batch.append(new_word)

                    # 批量插入
                    if len(batch) >= batch_size:
                        session.add_all(batch)
                        session.commit()
                        imported += len(batch)
                        print(f"已导入 {imported}/{total_words} 个单词 ({imported*100//total_words}%)")
                        batch = []

                except Exception as e:
                    errors += 1
                    print(f"导入单词 '{word_text}' 时出错: {e}")
                    continue

            # 插入剩余的单词
            if batch:
                session.add_all(batch)
                session.commit()
                imported += len(batch)

            print("\n导入完成!")
            print(f"成功导入: {imported} 个单词")
            print(f"跳过: {skipped} 个单词")
            print(f"错误: {errors} 个单词")

    except Exception as e:
        print(f"导入过程中发生错误: {e}")
        raise

    finally:
        stardict.close()


def clean_invalid_words():
    """
    清理数据库中包含空格、引号、逗号的无效单词
    """
    print("正在清理数据库中的无效单词...")
    
    # 连接 PostgreSQL
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with Session(engine) as session:
            # 获取所有单词
            result = session.exec(select(Word))
            all_words = result.all()
            
            print(f"数据库中共有 {len(all_words)} 个单词")
            
            # 找出无效单词
            invalid_words = []
            for word in all_words:
                if not is_valid_word(word.text):
                    invalid_words.append(word)
            
            print(f"发现 {len(invalid_words)} 个无效单词")
            
            if invalid_words:
                # 显示前10个无效单词示例
                print("\n无效单词示例（前10个）：")
                for word in invalid_words[:10]:
                    print(f"  - '{word.text}'")
                
                # 确认删除
                confirm = input(f"\n确认删除这 {len(invalid_words)} 个无效单词？(yes/no): ")
                if confirm.lower() == 'yes':
                    # 先清空整个 library_word_link 表
                    print(f"\n正在清空 library_word_link 表...")
                    session.exec(select(LibraryWordLink)).all()  # 确保表存在
                    session.execute(LibraryWordLink.__table__.delete())
                    session.commit()
                    print("library_word_link 表已清空")
                    
                    # 再删除无效单词
                    print(f"\n正在删除 {len(invalid_words)} 个无效单词...")
                    for word in invalid_words:
                        session.delete(word)
                    session.commit()
                    print(f"\n成功删除 {len(invalid_words)} 个无效单词")
                else:
                    print("\n取消删除操作")
            else:
                print("\n没有发现无效单词")
    
    except Exception as e:
        print(f"清理过程中发生错误: {e}")
        raise


def main():
    if len(sys.argv) < 2:
        print("用法: python -m app.scripts.import_words <sqlite_db_path>")
        print("      python -m app.scripts.import_words --clean  # 清理无效单词")
        print("示例: python -m app.scripts.import_words data/stardict.db")
        sys.exit(1)

    # 检查是否是清理模式
    if sys.argv[1] == '--clean':
        clean_invalid_words()
        return

    sqlite_path = sys.argv[1]

    # 可选参数：批量大小
    batch_size = 10000
    if len(sys.argv) >= 3:
        try:
            batch_size = int(sys.argv[2])
        except ValueError:
            print("警告: 批量大小参数无效，使用默认值 10000")

    import_words_from_sqlite(sqlite_path, batch_size)


if __name__ == '__main__':
    main()
