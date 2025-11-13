# WordTower

## 开发环境

### 数据库迁移

```
cd app
uv run alembic upgrade head
```

### 运行项目

```
uv run uvicorn app.main:app --reload
```