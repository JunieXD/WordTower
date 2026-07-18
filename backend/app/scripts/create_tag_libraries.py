"""
创建基于tag的词库脚本

从word表的tags字段中提取所有唯一的tag，
为每个tag创建一个公开词库，并在library_word_link表中建立关联关系。

uv run python -m app.scripts.create_tag_libraries
"""

from sqlmodel import Session, select
from app.db.database import engine
from app.models.word import Word
from app.models.library import Library, LibraryVisibility
from app.models.library_word_link import LibraryWordLink
from collections import defaultdict


# tag到中文名称的映射
TAG_NAME_MAPPING = {
    "zk": "中考",
    "gk": "高考",
    "cet4": "英语四级",
    "cet6": "英语六级",
    "ky": "考研",
    "ielts": "雅思",
    "toefl": "托福",
    "gre": "美国研究生入学考试",
}


def extract_all_tags(session: Session):
    """从所有单词中提取唯一的tags"""
    print("正在提取所有单词的tags...")

    # 查询所有单词的tags字段
    statement = select(Word.tags).where(Word.tags.isnot(None))
    results = session.exec(statement).all()

    # 提取唯一的tags
    unique_tags = set()
    for tags_str in results:
        if tags_str and tags_str.strip():
            # 按空格分隔tags
            tags = tags_str.strip().split()
            unique_tags.update(tags)

    print(f"提取到 {len(unique_tags)} 个唯一的tag: {sorted(unique_tags)}")
    return sorted(unique_tags)


def create_tag_libraries(session: Session, tags: list[str]):
    """为每个tag创建对应的词库，如果已存在则更新名称和描述"""
    print("\n正在创建/更新tag对应的词库...")

    tag_to_library = {}

    for tag in tags:
        # 获取中文名称，如果没有映射则使用原tag
        chinese_name = TAG_NAME_MAPPING.get(tag, tag)
        description = f"{chinese_name}词汇"

        # 先检查是否已存在用tag作为名称的词库（旧版本）
        statement = select(Library).where(Library.name == tag)
        existing_library = session.exec(statement).first()

        if existing_library:
            # 更新现有词库的名称和描述
            old_name = existing_library.name
            existing_library.name = chinese_name
            existing_library.description = description
            tag_to_library[tag] = existing_library
            print(f"更新词库: '{old_name}' -> '{chinese_name}' (ID: {existing_library.id})")
        else:
            # 再检查是否已存在用中文名称的词库（新版本）
            statement = select(Library).where(Library.name == chinese_name)
            existing_library = session.exec(statement).first()

            if existing_library:
                # 词库已存在且名称正确
                tag_to_library[tag] = existing_library
                print(f"词库 '{chinese_name}' 已存在 (ID: {existing_library.id})")
            else:
                # 创建新词库
                library = Library(
                    name=chinese_name,
                    description=description,
                    creator_id=None,
                    visibility=LibraryVisibility.PUBLIC,
                    created_at=None,
                    updated_at=None,
                    word_count=0
                )
                session.add(library)
                session.flush()  # 获取生成的ID
                tag_to_library[tag] = library
                print(f"创建词库: {chinese_name} (ID: {library.id})")

    session.commit()
    print(f"\n成功创建/更新 {len(tag_to_library)} 个词库")
    return tag_to_library


def build_tag_word_mapping(session: Session, tags: list[str]):
    """构建tag到word_id列表的映射"""
    print("\n正在构建tag到单词的映射关系...")

    tag_word_map = defaultdict(list)

    # 查询所有带tags的单词
    statement = select(Word).where(Word.tags.isnot(None))
    words = session.exec(statement).all()

    for word in words:
        if word.tags and word.tags.strip():
            word_tags = word.tags.strip().split()
            for tag in word_tags:
                if tag in tags:
                    tag_word_map[tag].append(word.id)

    # 统计信息
    for tag in sorted(tag_word_map.keys()):
        print(f"  {tag}: {len(tag_word_map[tag])} 个单词")

    return tag_word_map


def create_library_word_links(session: Session, tag_to_library: dict, tag_word_map: dict):
    """创建词库和单词的关联关系"""
    print("\n正在创建词库-单词关联关系...")

    total_links = 0
    skipped_links = 0

    for tag, library in tag_to_library.items():
        word_ids = tag_word_map.get(tag, [])
        if not word_ids:
            print(f"  {tag}: 没有对应的单词，跳过")
            continue

        # 查询已存在的关联
        statement = select(LibraryWordLink.word_id).where(
            LibraryWordLink.library_id == library.id
        )
        existing_word_ids = set(session.exec(statement).all())

        # 批量创建新关联
        new_links = []
        for word_id in word_ids:
            if word_id not in existing_word_ids:
                new_links.append(
                    LibraryWordLink(
                        library_id=library.id,
                        word_id=word_id
                    )
                )
            else:
                skipped_links += 1

        if new_links:
            session.add_all(new_links)
            total_links += len(new_links)
            print(f"  {tag}: 添加 {len(new_links)} 个关联")
        else:
            print(f"  {tag}: 所有关联已存在，跳过")

        # 更新词库的word_count
        library.word_count = len(word_ids)

    session.commit()
    print(f"\n成功创建 {total_links} 个新关联，跳过 {skipped_links} 个已存在的关联")


def update_library_word_counts(session: Session):
    """更新所有词库的word_count字段"""
    print("\n正在更新词库的单词数量...")

    statement = select(Library)
    libraries = session.exec(statement).all()

    for library in libraries:
        count_statement = select(LibraryWordLink).where(
            LibraryWordLink.library_id == library.id
        )
        count = len(session.exec(count_statement).all())
        library.word_count = count

    session.commit()
    print(f"已更新 {len(libraries)} 个词库的单词数量")


def main():
    """主函数"""
    print("=" * 60)
    print("开始创建基于tag的词库")
    print("=" * 60)

    with Session(engine) as session:
        # 1. 提取所有唯一的tags
        tags = extract_all_tags(session)

        if not tags:
            print("没有找到任何tag，退出")
            return

        # 2. 创建tag对应的词库
        tag_to_library = create_tag_libraries(session, tags)

        # 3. 构建tag到word的映射
        tag_word_map = build_tag_word_mapping(session, tags)

        # 4. 创建词库-单词关联关系
        create_library_word_links(session, tag_to_library, tag_word_map)

        # 5. 更新词库的word_count
        update_library_word_counts(session)

    print("\n" + "=" * 60)
    print("完成！所有基于tag的词库已创建")
    print("=" * 60)


if __name__ == "__main__":
    main()
