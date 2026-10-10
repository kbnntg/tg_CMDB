"""建表脚本：按 schema/models.py 里的实体定义，在目标库里创建表。

用法（在项目根目录执行）：
    python init_db.py           # 只创建缺失的表，已存在的表不动，不丢数据
    python init_db.py --drop    # 先删除再重建（会清空数据，需二次确认）

注意：脚本只建表、不建库，请先确保 MySQL 里已有 cmdb 这个 database（见 README）。
"""
import sys

from schema import models  # noqa: F401  必须导入，否则 Base.metadata 里一张表都没有
from schema.base import Base
from schema.get_db import DATABASE_URL, engine


def mask_url(url: str) -> str:
    """打印连接串前把口令打成 ***，避免日志泄露"""
    if "//" in url and "@" in url:
        head, tail = url.split("//", 1)
        userinfo, host = tail.split("@", 1)
        if ":" in userinfo:
            return f"{head}//{userinfo.split(':', 1)[0]}:***@{host}"
    return url


def main():
    drop = "--drop" in sys.argv
    print(f"目标数据库：{mask_url(DATABASE_URL)}")

    if drop:
        print("--drop：以下已存在的表将被删除并重建")
        for name in Base.metadata.tables:
            print(f"  - {name}")
        if input("确认继续请输入 yes：").strip().lower() != "yes":
            print("已取消，未做任何修改")
            return
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)
    print("建表完成，当前表：", ", ".join(sorted(Base.metadata.tables)))


if __name__ == "__main__":
    main()
