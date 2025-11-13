from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# --- [新增/修改部分 1: 路径和模块导入] ---
import sys
import os

# 1. 调整 Python 导入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 2. 导入您的项目核心组件 (SQLModel 和 Engine)
from sqlmodel import SQLModel
from app.db.database import engine 

# 3. 导入所有模型 (关键: 确保它们都被注册到 SQLModel.metadata)
from app.models import *
# ---------------------------------------------


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# add your model's MetaData object here
# for 'autogenerate' support
# --- [修改部分 2: 设置 target_metadata] ---
target_metadata = SQLModel.metadata
# ----------------------------------------

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # 保持不变，但为了防止配置混乱，最好是从你的 engine 获取 url
    url = config.get_main_option("sqlalchemy.url") or str(engine.url) 
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        template_args={
            'imports': ['import sqlmodel'],  # 告诉 Alembic 在脚本顶部添加 'import sqlmodel'
        }
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # --- [修改部分 3: 使用导入的 engine] ---
    # 不再使用 engine_from_config，而是直接使用在项目代码中创建好的 engine
    connectable = engine 
    # ----------------------------------------

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            render_as_batch=True, # 推荐为 SQLite/MySQL 等方言添加此项
            template_args={
                'imports': ['import sqlmodel'],  # 告诉 Alembic 在脚本顶部添加 'import sqlmodel'
            }
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()