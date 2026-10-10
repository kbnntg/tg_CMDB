# 一、使用psutil获取cpu、内存、磁盘参数
# 二、node_exporter获取采集值供Prometheus识别
# 三、把采集到的资产信息通过 HTTP 上报给 CMDB 服务端
import json
import os
import platform
import socket
import sys
import time
from pathlib import Path

import psutil
import requests
from distro import distro

# 项目根目录（service/ 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 复用项目根目录下的 .env 读取器（标准库实现，不需要 python-dotenv）
sys.path.insert(0, str(PROJECT_ROOT))
try:
    from env_loader import load_env  # noqa: E402
except ImportError:  # 只把本文件单独拷到被采集主机时，就只认环境变量
    def load_env(*_args, **_kwargs):
        return None

# 先把 .env 读进 os.environ：先查当前工作目录，再查项目根目录（文件不存在返回 None，不算错误）
ENV_FILE = load_env() or load_env(PROJECT_ROOT)

DEFAULT_SERVER_URL = "http://127.0.0.1:8888/api/v1/host/report"

# 服务端配置：支持环境变量覆盖，部署到别的机器不用改源码
_configured_url = os.getenv("CMDB_SERVER_URL", "").strip()
SERVER_URL = _configured_url or DEFAULT_SERVER_URL
if not _configured_url:
    print(f"[CMDB][WARN] 未配置 CMDB_SERVER_URL，将上报到默认地址 {DEFAULT_SERVER_URL}")
# 上报时间（秒）
REPORT_INTERVAL = int(os.getenv("CMDB_REPORT_INTERVAL", "30") or 30)
# node_exporter 默认监听端口，找不到进程时用它
NODE_EXPORTER_PORT = int(os.getenv("CMDB_NODE_EXPORTER_PORT", "9100") or 9100)


# 一、
def get_monitor():
    # 磁盘++++++++++++++++++++++++++++++++++
    disk = []
    # 获取所有磁盘分区，不包含隐藏分区
    disk_part = psutil.disk_partitions(all=False)
    for part in disk_part:
        try:
            # 磁盘使用情况
            use = psutil.disk_usage(part.mountpoint)
            disk.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "opts": part.opts,
                "total": use.total
            })
        except (PermissionError, OSError):
            # 忽略没有权限或无法访问的分区
            continue

    return disk


# 二、获取node_exporter执行进程
# 判断ps -ef的name和执行命令中是否是node_exporter，取出它监听的端口
def get_node_exporter():
    # 遍历所有进程
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        if "node_exporter" in proc.info['name'] or "node_exporter" in str(proc.info['cmdline']):
            # 查找--web.listen-address参数，找到端口号值，用切片
            for arg in proc.info["cmdline"]:
                if arg.startswith("--web.listen-address="):
                    return int(arg.split(":")[-1])
    # 没找到进程就返回默认端口
    return NODE_EXPORTER_PORT


# 三、获取操作系统
def get_os():
    release_info = distro.distro_release_info()
    return {
        # 操作系统版本、架构、系统类型
        "os_version": platform.version(),
        "os_arch": platform.machine(),
        "os_type": platform.system(),
        "distribution_name": distro.name(),
        "distribution_version": release_info.get("version_id", "")
    }


# 四、获取本地出口IP
# 使用socket：程序与网络之间的通信接口，Python代码通过这个模块能和同一台机器、
# 局域网甚至互联网上的其他设备建立链接
def get_ip_info():
    """取本机出口 IP。

    UDP connect 不会真的发包，只是让内核选一条出口路由，所以外网不可达时
    也可能成功；但在纯内网、无默认路由的环境下会失败，这里做两级兜底。
    """
    # 方式一：连 8.8.8.8 的 UDP 端口，让内核选出出口 IP
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # IPv4、UDP形式获取
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]  # 下标0：IP地址、下标1：端口号，这里只要IP地址
    except OSError:
        pass
    finally:
        if s is not None:
            s.close()

    # 方式二：解析本机主机名
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except (OSError, UnicodeError):
        pass

    # 两种方式都失败就返回空串，由上层决定不上报。
    # 不要返回「获取IP失败」这类字符串：ip 是服务端的唯一键，会被写脏数据。
    return ""


# 汇总资产信息
def collectt():
    # 采集资产信息
    hostname = socket.gethostname()
    # 返回各资源信息
    return {
        "cpu_count": psutil.cpu_count(logical=True),
        "mem_total": psutil.virtual_memory().total,
        "hostname": hostname,
        "ip": get_ip_info(),
        "disk": get_monitor(),
        "os_info": get_os(),
        "node_exporter_port": get_node_exporter(),
        "server_info": hostname
    }


def report_server(os_info):
    # 判断接收数据是否为空；没取到 IP 也不上报，避免污染服务端数据
    if not os_info or not os_info.get("ip"):
        print('采集结果不完整（未取到 IP），本次跳过上报\n')
        return False
    try:
        # requests发送Post请求
        response = requests.post(
            SERVER_URL,
            json=os_info,
            timeout=10
        )

        response.raise_for_status()  # 自动校验状态码（非200抛异常）
        # 获取json格式数据
        result = response.json()
        if result.get("code") in (0, 200):
            print(f'上报成功：{result.get("updated")}\n')
            return True
        else:
            print(f'上报失败：{result.get("msg") or result}\n')
            return False

    except Exception as e:
        print(f'上报请求失败：{e}\n')
        return False


if __name__ == '__main__':
    print(f'上报地址：{SERVER_URL}，间隔 {REPORT_INTERVAL} 秒，Ctrl+C 退出')
    # 死循环，默认 30s 采集一次：
    while True:
        try:
            print('开始采集资产信息：')
            coll = collectt()
            print(json.dumps(coll, indent=4, ensure_ascii=False))
            report_server(coll)
            time.sleep(REPORT_INTERVAL)
        except KeyboardInterrupt:
            print('\n已停止采集')
            break
