# 对主机参数进行配置修改模块
from typing import Optional, Any

from fastapi import Depends, APIRouter
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from schema import get_db
from schema.base import HostUpdateRequest
from schema.get_db import create_session
from schema.models import Host

# 定义路由
Router = APIRouter(prefix='/api/v1/host')


# 查找host主机
@Router.get('/search')
def search_host(q: Optional[str] = None, db: Any = Depends(create_session)):
    hosts = db.query(Host)
    # 判断条件
    if q is None:
        hosts = hosts.all()
    else:
        hosts = hosts.filter(
            or_(
                Host.hostname.like(f"%{q}%"),
                Host.environment.like(f"%{q}%")
            )
        ).all()

    for host in hosts:
        # 内存
        host.mem_total = round(host.mem_total / 1024 ** 3)
        host.mem_total = f"{host.mem_total} GB"
        # 时间格式
        if host.create_time is not None:
            host.create_time = host.create_time.strftime("%Y-%m-%d %H:%M:%S")
        if host.update_time is not None:
            host.update_time = host.update_time.strftime("%Y-%m-%d %H:%M:%S")
        if host.report_time is not None:
            host.report_time = host.report_time.strftime("%Y-%m-%d %H:%M:%S")

    return {"code": 0, "data": hosts}


# 修改主机资源
@Router.post('/{host_id}')
def update_host(host_id: int, data: HostUpdateRequest, db: Any = Depends(create_session)):
    try:
        # 查找对应的host_id主机，找出第一个主机
        hosts = db.query(Host).filter(Host.id == host_id).first()
        if not hosts:
            return {"code": -1, "msg": "数据为空"}
        else:
            # 遍历主机的字典
            for key, value in data.model_dump(exclude_none=True).items():
                # 修改后提交
                setattr(hosts, key, value)
            db.commit()
            db.refresh(hosts)
            return {"code": 0, "msg": "更新成功", "data": hosts}
    except SQLAlchemyError as e:
        db.rollback()  # 回滚
        return {"code": -1, "msg": "数据错误"}


# 禁用主机
@Router.post('/{host_id}/disable')
def disable_host(host_id: int, db: Any = Depends(create_session)):
    try:
        hosts = db.query(Host).filter(Host.id == host_id).first()
        if not hosts:
            return {"code": -1, "msg": '数据为空'}
        hosts.enabled = False
        db.commit()
        db.refresh(hosts)
        return {"code": 0, "msg": f"主机 {hosts.ip} 禁用成功", "data": hosts}

    except SQLAlchemyError as e:
        db.rollback()
        # raise HTTPException(status_code=500, detail=f"数据库操作失败：{str(e)}")
        return {"code": -1, "msg": f"数据库操作失败：{str(e)}"}


# 启用主机
@Router.post('/{host_id}/enable')
def enable_host(host_id: int, db: Any = Depends(create_session)):
    try:
        hosts = db.query(Host).filter(Host.id == host_id).first()
        if not hosts:
            return {"code": -1, "msg": '数据为空'}
        hosts.enabled = True
        db.commit()
        db.refresh(hosts)
        return {"code": 0, "msg": f"主机 {hosts.ip} 启用成功", "data": hosts}

    except SQLAlchemyError as e:
        db.rollback()
        # raise HTTPException(status_code=500, detail=f"数据库操作失败：{str(e)}")
        return {"code": -1, "msg": f"数据库操作失败：{str(e)}"}


# 删除主机
@Router.post('/{host_id}/delete')
def delete_host(host_id: int, db: Any = Depends(create_session)):
    try:
        hosts = db.query(Host).filter(Host.id == host_id).first()
        if not hosts:
            return {'code': -1, 'msg': '没有这台主机'}

        # 提前留一份
        ip, hostname = hosts.ip, hosts.hostname
        db.delete(hosts)
        db.commit()
        return {'code': 0, 'msg': f'主机 {ip}（{hostname}）已删除', 'data': {'id': host_id}}

    except SQLAlchemyError as e:
        db.rollback()
        # raise HTTPException(status_code=500, detail=f"数据库操作失败：{str(e)}")
        return {"code": -1, "msg": f"数据库操作失败：{str(e)}"}
