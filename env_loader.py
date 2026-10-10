"""极简 .env 读取器，只用标准库，不依赖 python-dotenv。

行为约定：
    * find_env_file(start) 从 start（默认当前工作目录）向上逐级查找 .env
    * 想让「当前工作目录」和「项目根目录」都能命中，调用方连调两次即可：
        load_env() or load_env(项目根目录)
    * 默认不覆盖已存在的环境变量，即优先级：真实环境变量 > .env > 代码里的兜底值
    * 文件不存在不算错误，返回 None，由调用方决定怎么提示
"""
import os
from pathlib import Path
from typing import Dict, Optional, Union

ENV_FILENAME = ".env"


def find_env_file(start: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """从 start（默认当前工作目录）开始逐级向上查找 .env，找到就返回路径"""
    current = Path(start).resolve() if start else Path.cwd().resolve()
    for directory in [current, *current.parents]:
        candidate = directory / ENV_FILENAME
        if candidate.is_file():
            return candidate
    return None


def parse_env_file(path: Union[str, Path]) -> Dict[str, str]:
    """解析 .env 文本，返回键值字典（忽略空行与 # 注释，去掉成对引号）"""
    values: Dict[str, str] = {}
    # utf-8-sig 可同时兼容「带 BOM」和「不带 BOM」的 UTF-8 文件
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # 允许 `export KEY=VALUE` 这种写法
        if line.lower().startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        # 去掉成对的引号：KEY="a b" / KEY='a b'
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_env(start: Optional[Union[str, Path]] = None,
             override: bool = False) -> Optional[Path]:
    """加载 .env 到 os.environ。

    返回实际读取到的文件路径；没找到 .env 时返回 None。
    override=False（默认）时不覆盖 os.environ 里已有的键。
    """
    path = find_env_file(start)
    if path is None:
        return None
    for key, value in parse_env_file(path).items():
        if override or key not in os.environ:
            os.environ[key] = value
    return path
