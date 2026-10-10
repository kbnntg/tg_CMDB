from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class DiskRequest(BaseModel):
    device: str
    mountpoint: str
    fstype: str
    opts: str
    total: int


class HostRequest(BaseModel):
    ip: str
    hostname: str
    mem_total: int
    cpu_count: int
    node_exporter_port: int
    os_info: dict
    server_info: str
    # 表示一个主机有多个磁盘信息，使用列表
    disk: List[DiskRequest]


class HostUpdateRequest(BaseModel):
    op_group: Optional[str] = None
    dev_group: Optional[str] = None
    tags: Optional[str] = None
    environment: Optional[str] = None
    region: Optional[str] = None
    provider: Optional[str] = None
    service_type: Optional[str] = None
    business: Optional[str] = None
    serial: Optional[str] = None
