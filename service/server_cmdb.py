# 服务端接口
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from router import update_service
from router import web_service
from service import db_service

# 前端静态文件目录（web/index.html 为管理页面入口）
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="CMDB配置管理系统", version="1.0")


# 对外访问接口
@app.get('/api/v1/healthy', summary='健康检查')
def healthy():
    return {"code": 200, "status": 'ok'}


# 引入路由
app.include_router(db_service.router)
# 注意顺序：web_service 里有静态路径 /list、/import 等，
# 必须排在 update_service 的动态路径 /{host_id} 之前，
# 否则 POST /api/v1/host/import 会被 /{host_id} 抢先匹配而报 422。
app.include_router(web_service.router)
app.include_router(update_service.Router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产allow_origins=["https://aiops.example.com"]   # ← 只允许这一个来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载前端页面：访问 http://IP:8888/ 即为主机管理页面
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get('/', include_in_schema=False)
def index():
    return FileResponse(WEB_DIR / "index.html")


if __name__ == '__main__':
    uvicorn.run(app=app, host='0.0.0.0', port=8888)
