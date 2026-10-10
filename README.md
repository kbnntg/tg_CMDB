# Python_CMDB 主机配置管理系统

轻量 CMDB（配置管理数据库）：被采集主机上运行一个采集 agent，定时把 CPU / 内存 / 磁盘 / 操作系统信息上报到服务端；服务端提供资产查询、筛选、编辑、启停、批量导入导出，并自带一个 Web 管理页面。

技术栈：FastAPI + SQLAlchemy + MySQL + Vue 3（前端为单文件页面，无需构建）。

## 功能

- **资产自动上报**：agent 每 30 秒采集一次并上报，服务端按 IP 判断是新增还是更新，磁盘信息按 `(设备, 挂载点)` 做增量同步
- **Web 管理页面**：列表分页、关键字与环境/供应商/系统等条件筛选、查看磁盘详情、编辑资产属性
- **主机启停与删除**：单台操作 + 前端勾选批量删除（级联删除磁盘记录）
- **CSV 导入导出**：导出沿用当前筛选条件或仅导出勾选项；导入支持 UTF-8 / GBK 编码、逗号 / Tab / 分号 / 竖线分隔，可下载导入模板
- **node_exporter 端口探测**：自动读取进程启动参数里的监听端口，找不到则用默认端口

## 目录结构

```
Python_CMDB/
├── init_db.py                # 建表脚本
├── env_loader.py             # .env 读取器（纯标准库，无需 python-dotenv）
├── requirements.txt
├── .env.example              # 配置示例，复制为 .env 使用
├── schema/
│   ├── base.py               # ORM Base + Pydantic 请求模型
│   ├── get_db.py             # 引擎 / 会话（读环境变量，不写死口令）
│   └── models.py             # hosts、disks 实体定义
├── router/
│   ├── web_service.py        # 前端页面用的列表/详情/筛选/导入导出接口
│   └── update_service.py     # 搜索、修改、启停、删除接口
├── service/
│   ├── server_cmdb.py        # 服务端入口（FastAPI app，端口 8888）
│   ├── client_agent.py       # 采集 agent（部署在被采集主机上）
│   └── db_service.py         # 资产上报接口
└── web/
    ├── index.html            # 管理页面（Vue 3 单页）
    └── vendor/vue.global.prod.js
```

## 环境要求

- Python 3.8+
- MySQL 5.7 / 8.0

## 快速开始

**1. 安装依赖**

```bash
pip install -r requirements.txt
```

**2. 建库**（脚本只建表不建库）

```sql
CREATE DATABASE cmdb DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
```

**3. 配置连接信息**

```bash
cp .env.example .env     # Windows: copy .env.example .env
```

编辑 `.env`，把 `CMDB_DATABASE_URL` 改成你自己的地址和口令。`.env` 已被 `.gitignore` 忽略，不会提交到仓库。

`.env` 由项目自带的 `env_loader.py` 读取（纯标准库，**不需要安装 `python-dotenv`**）。它从当前工作目录和项目根目录分别向上查找 `.env`，所以无论在哪个目录启动都能读到。如果既没有环境变量、也没有 `.env`，启动时会打印一条 `[CMDB][WARN]` 提示，并回退到本机兜底连接串。

> 也可以不使用 `.env`，直接设环境变量（优先级高于 `.env`）：
> Linux: `export CMDB_DATABASE_URL="mysql+pymysql://用户:口令@主机:3306/cmdb?charset=utf8mb4"`
> Windows PowerShell: `$env:CMDB_DATABASE_URL="mysql+pymysql://用户:口令@主机:3306/cmdb?charset=utf8mb4"`

**4. 建表**

```bash
python init_db.py
```

**5. 启动服务端**（在项目根目录执行）

```bash
python -m service.server_cmdb
```

> 必须用 `-m` 这种模块方式启动：代码里用的是 `from router import ...`、`from schema import ...` 这类绝对导入，
> 直接 `python service/server_cmdb.py` 会把 `service/` 当成 `sys.path` 第一项，导致 `ModuleNotFoundError: No module named 'router'`。
> 等价写法还有 `python -m uvicorn service.server_cmdb:app --host 0.0.0.0 --port 8888`。
> 在 PyCharm 里直接运行 `server_cmdb.py` 也可以，因为 IDE 默认会把项目根目录加入 `PYTHONPATH`。

访问 `http://<服务端IP>:8888/` 即为管理页面。健康检查：`GET /api/v1/healthy`。

**6. 在被采集主机上启动 agent**（同样在项目根目录执行）

```bash
# 指向服务端真实地址
export CMDB_SERVER_URL="http://<服务端IP>:8888/api/v1/host/report"
python -m service.client_agent
```

> agent 也可以直接 `python service/client_agent.py` 运行；它不依赖项目内的模块，
> 只把 `client_agent.py` 单独拷到被采集主机上同样能跑（此时不读 `.env`，只认环境变量）。

## 配置项

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `CMDB_DATABASE_URL` | `mysql+pymysql://root:root@127.0.0.1:3306/cmdb?charset=utf8mb4` | SQLAlchemy 连接串 |
| `CMDB_DB_ECHO` | `0` | 设为 `1` 打印所有 SQL |
| `CMDB_SERVER_URL` | `http://127.0.0.1:8888/api/v1/host/report` | agent 上报地址 |
| `CMDB_REPORT_INTERVAL` | `30` | agent 上报间隔（秒） |
| `CMDB_NODE_EXPORTER_PORT` | `9100` | 探测不到 node_exporter 进程时的兜底端口 |

> 取值优先级：**真实环境变量 > 项目根目录 `.env` > 上表中的默认值**。
> `.env` 会先按当前工作目录逐级向上找，找不到再按项目根目录逐级向上找。

## 接口一览

服务端启动后可在 `/docs` 查看 FastAPI 自动生成的文档。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/healthy` | 健康检查 |
| POST | `/api/v1/host/report` | agent 上报资产（新增或更新） |
| GET | `/api/v1/host/list` | 主机列表（分页 + 筛选） |
| GET | `/api/v1/host/detail/{host_id}` | 主机详情（含磁盘） |
| GET | `/api/v1/host/options` | 筛选项字典与总数统计 |
| GET | `/api/v1/host/search` | 按主机名/环境模糊搜索 |
| POST | `/api/v1/host/{host_id}` | 修改资产属性 |
| POST | `/api/v1/host/{host_id}/enable` \| `/disable` | 启用 / 禁用主机 |
| POST | `/api/v1/host/{host_id}/delete` | 删除单台主机 |
| POST | `/api/v1/host/batch/delete` | 批量删除 |
| GET | `/api/v1/host/export` | 导出 CSV |
| GET | `/api/v1/host/import/template` | 下载导入模板 |
| POST | `/api/v1/host/import` | 批量导入（CSV / multipart / JSON） |

## 数据表

- **hosts**：`ip`（唯一键）、`hostname`、`mem_total`（字节）、`cpu_count`、`node_exporter_port`、`os_type` / `os_version` / `os_arch`、`distribution_name` / `distribution_version`、`environment`、`region`、`provider`、`service_type`、`business`、`serial`、`op_group`、`dev_group`、`tags`、`enabled`，以及 `report_time` / `create_time` / `update_time`
- **disks**：`host_id`（外键）、`device`、`mountpoint`、`fstype`、`total`、`opts`

## 安全与使用限制

**这个项目没有任何鉴权，请只在内网部署，不要直接暴露到公网。** 任何能访问 8888 端口的人都可以查询、修改甚至删除全部资产数据。

其他需要注意的点：

- 数据库口令一律通过环境变量 / `.env` 提供，**不要把口令写回 `get_db.py`**，也不要把 `.env` 提交进仓库
- `.idea/` 已在 `.gitignore` 中忽略（其中的 `deployment.xml` 会暴露服务器地址和登录方式）
- CORS 当前是 `allow_origins=["*"]`，生产环境建议收紧为前端实际域名；注意 `allow_credentials=True` 与通配符来源组合在浏览器侧并不生效
- 上报接口以 `ip` 作为唯一键，agent 取不到 IP 时会跳过本次上报，避免写入脏数据
- `GET /api/v1/host/search` 会就地把 `mem_total` 格式化成 `"16 GB"` 字符串返回，属于直接修改 ORM 对象的老写法，建议后续改为构造独立字典返回

## 第三方资源

`web/vendor/vue.global.prod.js` 为 Vue.js v3.5.43 生产版（MIT License），直接内置以便页面离线可用。
