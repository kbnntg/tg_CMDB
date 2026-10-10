from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends

from schema.get_db import create_session
from schema.base import HostRequest
from schema.models import Host, Disk

router = APIRouter(prefix='/api/v1/host')


@router.post('/report')
# 接收用户发来的数据，格式必须是实体类中定义的，db是建立会话连接
def report_host(data: HostRequest, db: Any = Depends(create_session)):
    os_info = data.os_info or {}

    # 想让SQL语句的select * from hosts h where h.ip=? and h.hostname=?
    host = db.query(Host).filter_by(ip=data.ip).first()

    # 没有就创建
    if not host:
        host = Host(
            hostname=data.hostname,
            ip=data.ip,
            cpu_count=data.cpu_count,
            mem_total=data.mem_total,
            os_type=os_info.get("os_type", ""),
            os_version=os_info.get("os_version", ""),
            os_arch=os_info.get("os_arch", ""),
            distribution_name=os_info.get("distribution_name", ""),
            distribution_version=os_info.get("distribution_version", ""),
            node_exporter_port=data.node_exporter_port,
            environment=str(data.server_info)[:50] if data.server_info else "",
            report_time=datetime.now(),
        )
        # 创建完就提交
        db.add(host)
        db.commit()
        db.refresh(host)
    else:
        # 遍历要发生改变的字段
        for f in ["hostname", "ip", "cpu_count", "mem_total", "node_exporter_port"]:
            # 获取客户端发送的
            client_value = getattr(data, f, None)
            # 如果客户发来的不为空并且与源数据不同就更新
            if client_value is not None and client_value != getattr(host, f):
                setattr(host, f, client_value)

        for f in ["os_type", "os_version", "os_arch", "distribution_name", "distribution_version"]:
            value = os_info.get(f)
            if value is not None and getattr(host, f) != value:
                setattr(host, f, value)

        host.report_time = datetime.now()
        db.commit()
        db.refresh(host)

    # 磁盘语句
    all_disklist = db.query(Disk).filter_by(host_id=host.id).all()

    # 源数据、用户数据（提交的）遍历成字典
    database_disks = {(d.device, d.mountpoint): d for d in all_disklist}
    client_disk = {(d.device, d.mountpoint): d for d in data.disk}

    try:
        # 定义两个遍历遍历客户端发来的磁盘信息
        for key, new_disk in client_disk.items():
            # key值不在源磁盘信息中就添加
            if key not in database_disks:
                db.add(Disk(
                    host_id=host.id,
                    device=new_disk.device,
                    mountpoint=new_disk.mountpoint,
                    fstype=new_disk.fstype,
                    opts=new_disk.opts,
                    total=new_disk.total,
                ))
            else:
                # 定义一个遍历获取源磁盘key值
                disk_record = database_disks[key]
                # 遍历可能发生改变的字段
                for f in ["mountpoint", "fstype", "opts", "total"]:
                    # 看看值
                    new_val = getattr(new_disk, f)
                    # 如果用户提交的不同于源磁盘的key就更新
                    if getattr(disk_record, f) != new_val:
                        setattr(disk_record, f, new_val)

        for key in database_disks.keys() - client_disk.keys():
            db.delete(database_disks[key])

        db.commit()
        db.refresh(host)
    except Exception:
        db.rollback()
        raise

    return {"code": 200, "updated": True}

# 路径：用户发起请求→到达该接口→调用实例与方法→回馈给用户
