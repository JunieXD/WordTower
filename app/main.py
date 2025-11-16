from fastapi import FastAPI
from app.api.routes import auth
from app.api.routes import library
from app.api.routes import upgrade
from fastapi.middleware.cors import CORSMiddleware
from app.utils.cors import origins

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,             # 允许跨域请求的来源列表
    allow_credentials=True,            # 允许携带认证信息（如 Cookies/Authorization 头部）
    allow_methods=["*"],               # 允许所有 HTTP 方法 (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],               # 允许所有请求头部
)

app.include_router(auth.router)
app.include_router(library.router)
app.include_router(upgrade.router)