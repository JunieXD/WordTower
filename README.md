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

- [ ] 