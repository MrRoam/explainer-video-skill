"""读取机器本地配置；配置不随 skill 发布。"""

import json
import os
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
DEFAULT_RUNTIME = SKILL / "runtime.local.json"


def read_runtime(path=None):
    config = Path(path or os.environ.get("EXPLAINER_RUNTIME") or DEFAULT_RUNTIME).expanduser().resolve()
    if not config.is_file():
        raise FileNotFoundError(
            f"找不到本机配置：{config}。请先运行 scripts/configure_runtime.py；安装步骤见 README.md。"
        )
    runtime = json.loads(config.read_text(encoding="utf-8-sig"))
    for key in ("python", "ffmpeg", "tex_bin"):
        if runtime.get(key):
            runtime[key] = resolve_path(runtime[key], config.parent)
    narration = runtime.get("narration", {})
    for key in ("python", "model_directory"):
        if narration.get(key):
            narration[key] = resolve_path(narration[key], config.parent)
    return runtime


def resolve_path(value, base):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return str(path.resolve())
