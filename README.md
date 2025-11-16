# WordTower

## 开发环境

### 数据库初始化

```
uv run python -m app.scripts.init_db
```

### 数据库迁移

```
cd app
uv run alembic upgrade head
```

### 运行项目

```
uv run uvicorn app.main:app --reload
```