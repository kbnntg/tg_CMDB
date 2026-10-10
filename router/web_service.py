# 前端页面（主机管理）所使用的查询 / 导出 / 批量导入接口
import csv
import io
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_, func
from sqlalchemy.exc import SQLAlchemyError

from schema.get_db import create_session
from schema.models import Host, Disk

router = APIRouter(prefix='/api/v1/host', tags=['前端页面'])


class BatchDeleteRequest(BaseModel):
    """批量删除入参：{"ids": [1, 2, 3]}"""
    ids: List[int]

# 可批量导入 / 导出的字段（顺序即 CSV 列顺序）
IMPORT_FIELDS = [
    "ip", "hostname", "environment", "provider", "os_type", "os_version",
    "os_arch", "distribution_name", "distribution_version", "cpu_count",
    "mem_total", "node_exporter_port", "region", "service_type", "business",
    "serial", "op_group", "dev_group", "tags",
]

# 字段中文名，用于导出 CSV 的表头与导入模板
FIELD_LABELS = {
    "ip": "IP地址",
    "hostname": "主机名",
    "environment": "环境",
    "provider": "供应商",
    "os_type": "操作系统类型",
    "os_version": "操作系统版本",
    "os_arch": "系统架构",
    "distribution_name": "发行版",
    "distribution_version": "发行版版本",
    "cpu_count": "CPU核心数",
    "mem_total": "内存(GB)",
    "node_exporter_port": "node_exporter端口",
    "region": "区域",
    "service_type": "服务类型",
    "business": "业务线",
    "serial": "序列号",
    "op_group": "运维组",
    "dev_group": "开发组",
    "tags": "标签",
}


def _gb(value) -> str:
    """字节转 GB，保留一位小数"""
    if value is None:
        return "0"
    try:
        return f"{round(int(value) / 1024 ** 3, 1)}"
    except (TypeError, ValueError):
        return "0"


def _fmt_time(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value or ""


def _host_to_dict(host: Host, disks: Optional[list] = None) -> dict:
    """把 ORM 对象转成前端直接可用的字典"""
    data = {
        "id": host.id,
        "ip": host.ip,
        "hostname": host.hostname,
        "cpu_count": host.cpu_count,
        "mem_total": host.mem_total,
        "mem_total_gb": _gb(host.mem_total),
        "node_exporter_port": host.node_exporter_port,
        "os_type": host.os_type,
        "os_version": host.os_version,
        "os_arch": host.os_arch,
        "distribution_name": host.distribution_name,
        "distribution_version": host.distribution_version,
        "environment": host.environment,
        "region": host.region,
        "provider": host.provider,
        "service_type": host.service_type,
        "business": host.business,
        "serial": host.serial,
        "op_group": host.op_group,
        "dev_group": host.dev_group,
        "tags": host.tags,
        "enabled": bool(host.enabled),
        "report_time": _fmt_time(host.report_time),
        "create_time": _fmt_time(host.create_time),
        "update_time": _fmt_time(host.update_time),
    }
    if disks is not None:
        data["disks"] = [
            {
                "device": d.device,
                "mountpoint": d.mountpoint,
                "fstype": d.fstype,
                "opts": d.opts,
                "total": d.total,
                "total_gb": _gb(d.total),
            }
            for d in disks
        ]
    return data


def _apply_filters(query, q=None, environment=None, provider=None, os_type=None, enabled=None):
    """统一的筛选逻辑，列表 / 导出 / 统计共用"""
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Host.ip.like(like), Host.hostname.like(like),
                                 Host.environment.like(like), Host.business.like(like)))
    if environment:
        query = query.filter(Host.environment == environment)
    if provider:
        query = query.filter(Host.provider == provider)
    if os_type:
        query = query.filter(Host.os_type == os_type)
    if enabled is not None:
        query = query.filter(Host.enabled.is_(enabled))
    return query


# 主机列表（分页 + 筛选）
@router.get('/list', summary='主机列表（分页/筛选）')
def list_host(
        q: Optional[str] = None,
        environment: Optional[str] = None,
        provider: Optional[str] = None,
        os_type: Optional[str] = None,
        enabled: Optional[bool] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=200),
        db: Any = Depends(create_session),
):
    query = db.query(Host)
    query = _apply_filters(query, q, environment, provider, os_type, enabled)
    total = query.count()
    hosts = (query.order_by(Host.id.asc())
             .offset((page - 1) * page_size).limit(page_size).all())
    return {
        "code": 0,
        "data": {
            "items": [_host_to_dict(h) for h in hosts],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, -(-total // page_size)),
        },
    }


# 主机详情（含磁盘）
@router.get('/detail/{host_id}', summary='主机详情')
def detail_host(host_id: int, db: Any = Depends(create_session)):
    host = db.query(Host).filter(Host.id == host_id).first()
    if not host:
        return {"code": -1, "msg": "数据为空"}
    disks = db.query(Disk).filter(Disk.host_id == host.id).all()
    return {"code": 0, "data": _host_to_dict(host, disks)}


# 筛选项字典（环境 / 供应商 / 操作系统 / 业务线 / 运维组）
@router.get('/options', summary='筛选项')
def host_options(db: Any = Depends(create_session)):
    def distinct(column):
        rows = db.query(column).filter(column.isnot(None), column != '').distinct().all()
        return sorted({r[0] for r in rows if r[0]})

    return {
        "code": 0,
        "data": {
            "environment": distinct(Host.environment),
            "provider": distinct(Host.provider),
            "os_type": distinct(Host.os_type),
            "business": distinct(Host.business),
            "op_group": distinct(Host.op_group),
            "dev_group": distinct(Host.dev_group),
            "total": db.query(func.count(Host.id)).scalar() or 0,
            "enabled": db.query(func.count(Host.id)).filter(Host.enabled.is_(True)).scalar() or 0,
        },
    }


# 批量删除主机（前端勾选后一次请求删完；单台删除仍用 /{host_id}/delete）
@router.post('/batch/delete', summary='批量删除主机')
def batch_delete_host(data: BatchDeleteRequest, db: Any = Depends(create_session)):
    ids = list(dict.fromkeys(data.ids))  # 去重且保持顺序
    if not ids:
        return {"code": -1, "msg": "未指定要删除的主机"}

    try:
        hosts = db.query(Host).filter(Host.id.in_(ids)).all()
        if not hosts:
            return {"code": -1, "msg": "没有匹配到可删除的主机"}

        found_ids = [h.id for h in hosts]
        # 保留一份用于返回提示
        deleted = [{"id": h.id, "ip": h.ip, "hostname": h.hostname} for h in hosts]
        # 统计并级联删除该主机下的磁盘记录
        disk_count = (db.query(func.count(Disk.id))
                      .filter(Disk.host_id.in_(found_ids)).scalar() or 0)
        db.query(Disk).filter(Disk.host_id.in_(found_ids)).delete(synchronize_session=False)
        for host in hosts:
            db.delete(host)
        db.commit()

        missing = len(ids) - len(found_ids)
        msg = f"已删除 {len(found_ids)} 台主机"
        if missing:
            msg += f"，另有 {missing} 台不存在已跳过"
        return {"code": 0, "msg": msg,
                "data": {"deleted": len(found_ids), "disks": disk_count,
                         "missing": missing, "items": deleted}}

    except SQLAlchemyError as e:
        db.rollback()
        return {"code": -1, "msg": f"数据库操作失败：{str(e)}"}


# 导出 CSV（沿用当前筛选条件）
@router.get('/export', summary='导出CSV')
def export_host(
        q: Optional[str] = None,
        environment: Optional[str] = None,
        provider: Optional[str] = None,
        os_type: Optional[str] = None,
        enabled: Optional[bool] = None,
        ids: Optional[str] = None,  # 勾选导出："1,2,3"
        db: Any = Depends(create_session),
):
    query = db.query(Host)
    id_list = [int(i) for i in ids.split(',') if i.strip().isdigit()] if ids else []
    if id_list:
        query = query.filter(Host.id.in_(id_list))
    else:
        query = _apply_filters(query, q, environment, provider, os_type, enabled)
    hosts = query.order_by(Host.id.asc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([FIELD_LABELS[f] for f in IMPORT_FIELDS])
    for h in hosts:
        row = []
        for f in IMPORT_FIELDS:
            value = getattr(h, f)
            row.append(_gb(value) if f == "mem_total" else ("" if value is None else value))
        writer.writerow(row)

    filename = f"hosts_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    # 加 BOM，Excel 打开中文表头不乱码
    content = '\ufeff' + buffer.getvalue()
    return StreamingResponse(
        iter([content.encode('utf-8')]),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


# 批量导入模板（取库里第一条数据作为示例）
@router.get('/import/template', summary='批量导入模板')
def import_template(db: Any = Depends(create_session)):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([FIELD_LABELS[f] for f in IMPORT_FIELDS])
    sample = db.query(Host).order_by(Host.id.asc()).first()
    if sample:
        row = []
        for f in IMPORT_FIELDS:
            value = getattr(sample, f)
            row.append(_gb(value) if f == "mem_total" else ("" if value is None else value))
        writer.writerow(row)
    else:
        writer.writerow(["10.0.0.1", "demo-host", "测试环境", "自建", "Linux", "CentOS 7.9",
                         "x86_64", "CentOS", "7.9", "16", "32", "9100", "华东", "物理机",
                         "核心业务", "SN-0001", "运维一组", "开发一组", "core"])
    content = '\ufeff' + buffer.getvalue()
    return StreamingResponse(
        iter([content.encode('utf-8')]),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="host_import_template.csv"'},
    )


def _parse_int(value):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _coerce(field: str, raw):
    """把 CSV 里的字符串转成模型需要的类型"""
    if raw is None or str(raw).strip() == "":
        return None
    text = str(raw).strip()
    if field in ("cpu_count", "node_exporter_port"):
        return _parse_int(text)
    if field == "mem_total":
        gb = _parse_int(text)
        return None if gb is None else gb * 1024 ** 3  # 模板里按 GB 填
    return text


def _decode_csv(raw: bytes) -> str:
    """解码 CSV 文本：优先 UTF-8，其次 GBK（Windows 下 Excel 另存常是 GBK）"""
    for encoding in ('utf-8-sig', 'gbk'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def _sniff_delimiter(sample: str) -> str:
    """
    识别分隔符：逗号 / Tab / 分号 / 竖线。
    Excel 在中文 Windows 上「另存为 CSV」常产出 Tab 分隔的文件，
    只按逗号解析会导致整个文件解析不出任何一行。
    """
    if '\t' in sample:
        return '\t'
    try:
        return csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
    except csv.Error:
        pass
    # 退化策略：数第一行里哪种分隔符最多
    first_line = sample.splitlines()[0] if sample.splitlines() else ''
    counts = {d: first_line.count(d) for d in (',', '\t', ';', '|')}
    best = max(counts, key=counts.get)
    return best if counts[best] else ','


def _csv_rows_to_items(text: str):
    """把 CSV 文本按表头（中文名或字段名）映射成字段字典列表"""
    label_to_field = {v: k for k, v in FIELD_LABELS.items()}
    delimiter = _sniff_delimiter(text[:4096])
    items = []
    for line in csv.DictReader(io.StringIO(text), delimiter=delimiter):
        item = {}
        for key, value in line.items():
            if key is None:
                continue
            # 表头可能带 BOM、空格或全角空格
            key = key.strip().strip('\ufeff').strip()
            field = key if key in IMPORT_FIELDS else label_to_field.get(key)
            if field and value is not None:
                item[field] = value
        if item:
            items.append(item)
    return items


# 批量导入（CSV 文本 / multipart 上传 / JSON）
@router.post('/import', summary='批量导入')
async def import_host(
        request: Request,
        db: Any = Depends(create_session),
):
    content_type = (request.headers.get('content-type') or '').lower()
    normalized = []

    if 'application/json' in content_type:
        # JSON 批量导入：{"items": [{...}, ...]}
        payload = await request.json()
        rows = payload.get('items') if isinstance(payload, dict) else payload
        normalized = [
            {k: v for k, v in r.items() if k in IMPORT_FIELDS}
            for r in (rows or []) if isinstance(r, dict)
        ]
    else:
        raw = None
        if 'multipart/form-data' in content_type:
            # 浏览器表单上传。注意：Starlette 解析表单依赖 python-multipart，
            # 该库缺失时 request.form() 会抛 AssertionError，这里给出明确提示而不是 500。
            try:
                form = await request.form()
            except AssertionError:
                return {
                    "code": -1,
                    "msg": "服务端未安装 python-multipart，无法解析表单上传；"
                           "请改用「选择CSV文件」按钮（以文本方式提交）或在前端粘贴 CSV 内容",
                }
            upload = form.get('file') or form.get('upload')
            if hasattr(upload, 'read'):
                raw = await upload.read()
        else:
            # text/csv 或 text/plain：整个 body 就是 CSV 文本
            raw = await request.body()

        if not raw:
            return {"code": -1, "msg": "请选择要导入的 CSV 文件"}
        normalized = _csv_rows_to_items(_decode_csv(raw))

    if not normalized:
        return {
            "code": -1,
            "msg": "没有解析到可导入的数据。请确认：① 文件编码为 UTF-8 或 GBK；"
                   "② 含表头行（如「IP地址,主机名,环境」）；③ 分隔符为逗号或 Tab",
        }

    created, updated, skipped, errors = 0, 0, 0, []
    for index, item in enumerate(normalized, start=1):
        values = {f: _coerce(f, item.get(f)) for f in IMPORT_FIELDS}
        ip = values.get("ip")
        if not ip:
            skipped += 1
            errors.append(f"第{index}行：缺少 IP地址，已跳过")
            continue
        try:
            host = db.query(Host).filter(Host.ip == ip).first()
            if host:
                for field, value in values.items():
                    if value is not None:
                        setattr(host, field, value)
                host.report_time = datetime.now()
                updated += 1
            else:
                host = Host(**{k: v for k, v in values.items() if v is not None})
                if host.enabled is None:
                    host.enabled = True
                host.report_time = datetime.now()
                db.add(host)
                created += 1
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            skipped += 1
            errors.append(f"第{index}行（{ip}）：{e.__class__.__name__}")

    return {
        "code": 0,
        "msg": f"导入完成：新增 {created} 台，更新 {updated} 台，跳过 {skipped} 台",
        "data": {"created": created, "updated": updated, "skipped": skipped, "errors": errors[:20]},
    }
