"""数据库连接与会话管理。

连接串不写死在代码里，按下面的优先级取：
    1. 环境变量 CMDB_DATABASE_URL
    2. 项目根目录下的 .env 文件（用 env_loader 读取，不需要装 python-dotenv）
    3. 代码里的兜底值（只指向本机、不含真实凭据），并打印醒目警告
可参考根目录的 .env.example 进行配置。
"""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from env_loader import load_env

# 先把 .env 读进 os.environ：先查当前工作目录，再查项目根目录（文件不存在返回 None，不算错误）
ENV_FILE = load_env() or load_env(Path(__file__).resolve().parent.parent)

# 兜底值只指向本机、不含任何真实凭据；开发/生产环境请用环境变量或 .env 覆盖
DEFAULT_DATABASE_URL = "mysql+pymysql://root:root@127.0.0.1:3306/cmdb?charset=utf8mb4"

DATABASE_URL = os.getenv("CMDB_DATABASE_URL", "").strip()

# 既没有环境变量、也没有 .env 时不要把问题藏起来：明确告诉你正在用一个兜底连接串
if not DATABASE_URL:
    DATABASE_URL = DEFAULT_DATABASE_URL
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    print(
        "[CMDB][WARN] 未配置 CMDB_DATABASE_URL（环境变量和 {0} 都没有），\n"
        "            已回退到本机兜底连接串：{1}\n"
        "            如果这不是你要连的库，请创建 .env 或先设置 CMDB_DATABASE_URL。".format(
            _env_path, DEFAULT_DATABASE_URL
        )
    )

# 设 CMDB_DB_ECHO=1 可打印所有 SQL，便于排查问题
DB_ECHO = os.getenv("CMDB_DB_ECHO", "0").strip().lower() in ("1", "true", "yes", "on")

engine = create_engine(
    DATABASE_URL,
    echo=DB_ECHO,
    # 取连接前先探活，避免 MySQL 空闲断开后第一次请求报错
    pool_pre_ping=True,
    # 每小时回收一次连接，绕过 MySQL 默认的 wait_timeout
    pool_recycle=3600,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_session():
    """FastAPI 依赖：每个请求一个会话，请求结束自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
