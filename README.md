# WordTower

## 开发环境

### 数据库初始化

```
uv run python -m app.scripts.init_db
```

### 数据库迁移

```
cd app
# 迁移到最新
uv run alembic upgrade head
# 生成迁移文件
uv run alembic revision --autogenerate -m "描述本次迁移"
# 回滚
uv run alembic downgrade -1
```

### 导入词库

```
uv run python -m app.scripts.import_words <sqlite_db_path>
```

### 创建基于tag的词库

```
uv run python -m app.scripts.create_tag_libraries
```

### 运行项目

```
uv run uvicorn app.main:app --reload
```

## TODOS

- [ ] 对AI返回的JSON进行check
    - [ ] 原文中包含目标单词
    - [ ] 正确选项为 ABCD 中的一个
    - [ ] 没有两个选项内容完全相同
- [ ] 好友功能
- [ ] 排行榜相关API
- [ ] 固定层数出现 Boss、休息层
- [ ] 切换词库清空redis
- [x] prompt：不同选项出现同样内容；选项里标明了错误选项；abcd均匀出现的伪随机方法