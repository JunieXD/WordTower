# WordTower

## 开发环境

### 数据库初始化

使用 PostgreSQL，创建名为 wordtower 的 database。

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

下载 [ecdict-sqlite-28.zip](https://github.com/skywind3000/ECDICT/releases/tag/1.0.28) 将其解压至任意路径 `<sqlite_db_path>`

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

- [x] 对AI返回的JSON进行check
- [ ] 好友功能
- [ ] 排行榜相关API
- [ ] 固定层数出现 Boss、休息层
- [ ] 切换词库清空redis
- [x] prompt：不同选项出现同样内容；选项里标明了错误选项；abcd均匀出现的伪随机方法
- [ ] 每日挑战
- [ ] 调整数值