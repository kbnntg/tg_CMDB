# 一、创建实体类
# 主机host
from datetime import datetime

from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from schema.base import Base


class Host(Base):
    # 对应表明
    __tablename__ = "hosts"
    # 字段：属性名词 = 类型 + 约束
    # Column创建字段（Integer就是int，primary_key就是主键，authincrement自增长
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    ip = Column(String(50), comment='IP地址', unique=True)
    hostname = Column(String(50), comment="主机名")
    mem_total = Column(BigInteger, comment="总内存")
    cpu_count = Column(Integer, comment="CPU 核心数")
    node_exporter_port = Column(Integer, comment="node_exporter 端口")
    distribution_name = Column(String(50), comment="发行版名称")
    distribution_version = Column(String(50), comment="发行版版本")
    os_version = Column(String(200), comment="操作系统版本")
    os_arch = Column(String(20), comment="操作系统架构（如 x86_64）")
    os_type = Column(String(50), comment="操作系统类型")
    environment = Column(String(50), comment="环境")
    region = Column(String(50), comment="区域")
    provider = Column(String(50), comment="提供商")
    service_type = Column(String(50), comment="服务类型")
    business = Column(String(50), comment="业务线")
    serial = Column(String(50), comment="序列号")
    op_group = Column(String(50), default="", comment="运维组")
    dev_group = Column(String(50), default="", comment="开发组")
    tags = Column(String(512), default="", comment="标签")
    enabled = Column(Boolean, default=True, comment="是否启用")

    report_time = Column(DateTime, default=datetime.now, comment="上报时间")
    create_time = Column(DateTime, default=datetime.now, comment="首次创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="最后更新时间")

    # 实体关联,relationship(关联实体类名称，关联的实体类对应属性名称，是否级联）
    disks = relationship("Disk", back_populates="hosts", cascade="all, delete")


# 磁盘Disk
class Disk(Base):
    __tablename__ = "disks"
    id = Column(Integer, primary_key=True, comment="ID")
    device = Column(String(255), comment="设备名称")
    mountpoint = Column(String(50), comment="挂载点")
    fstype = Column(String(50), comment="文件系统类型")
    total = Column(BigInteger, comment="总大小")
    opts = Column(String(255), comment="挂载选项")

    # 外键，与host的id进行外键关联
    host_id = Column(Integer, ForeignKey("hosts.id"), comment='关联主机ID')

    # relationship
    hosts = relationship("Host", back_populates="disks")
