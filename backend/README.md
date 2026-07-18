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

### Debug 日志开关（终端实时输出）

默认只写入 `logs/*.log`。  
设置环境变量 `WORDTOWER_DEBUG=1` 后，会开启完整 `DEBUG` 日志，并实时打印到终端。

PowerShell 示例：

```powershell
$env:WORDTOWER_DEBUG="1"
uv run uvicorn app.main:app --reload
```

关闭调试日志：

```powershell
$env:WORDTOWER_DEBUG="0"
uv run uvicorn app.main:app --reload
```

## TODOS

- [x] 对AI返回的JSON进行check
- [x] 好友功能
- [x] 排行榜相关API
- [ ] 固定层数出现 Boss、休息层
- [x] 切换词库清空redis
- [x] prompt：不同选项出现同样内容；选项里标明了错误选项；abcd均匀出现的伪随机方法
- [x] 每日挑战
- [ ] 调整金币、经验、等级、升级/所需金币数值
- [x] 给前端返回历史答题记录
- [ ] 暴击率没有实际作用