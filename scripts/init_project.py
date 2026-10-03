"""在新工作区复制视频模板并复用本机配置；不下载依赖。"""

import argparse
import json
from pathlib import Path
import re
import shutil

from runtime_config import SKILL, read_runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--name", default="concept-video")
    parser.add_argument("--runtime", type=Path, help="指定本机配置；也可设置 EXPLAINER_RUNTIME")
    parser.add_argument("--python", type=Path, help="仅覆盖 Manim Python")
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--check", action="store_true", help="只检查路径，不创建项目")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", args.name):
        parser.error("name 须以小写字母开头，仅使用小写字母、数字和连字符，最长 64 字符。")
    try:
        runtime = read_runtime(args.runtime)
        python = Path(args.python or runtime["python"]).expanduser().resolve()
        ffmpeg = Path(args.ffmpeg or runtime["ffmpeg"]).expanduser().resolve()
        narration = runtime["narration"]
        if narration.get("backend", narration.get("installed_backend")) != "kokoro":
            raise ValueError("此配置未启用 Kokoro；请用 configure_runtime.py 配置中文配音。")
        for label, path in (("Manim Python", python), ("FFmpeg", ffmpeg),
                            ("配音 Python", Path(narration["python"])),
                            ("模型配置", Path(narration["model_directory"]) / "config.json"),
                            ("模型权重", Path(narration["model_directory"]) / "kokoro-v1_1-zh.pth"),
                            ("音色", Path(narration["model_directory"]) / "voices" / f"{narration.get('voice', 'zm_010')}.pt")):
            if not path.is_file():
                raise ValueError(f"{label} 不存在：{path}；先恢复配置路径，不会自动下载。")
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    workspace = args.workspace.expanduser().resolve()
    tools = dict(python=str(python), ffmpeg=str(ffmpeg), workspace=str(workspace),
                 project_id=args.name, output_stem=args.name, manim_version=runtime["manim_version"])
    tools["narration"] = dict(
        backend="kokoro", python=narration["python"],
        script=str(SKILL / "scripts" / "narrate_kokoro.py"),
        model_directory=narration["model_directory"],
        voice=narration.get("voice", "zm_010"), speed=narration.get("speed", 0.95),
    )
    if runtime.get("tex_bin"):
        tools["tex_bin"] = runtime["tex_bin"]
    if args.check:
        print(json.dumps(tools, ensure_ascii=False, indent=2))
        return
    project = workspace / "outputs" / f"{args.name}-project"
    if project.exists():
        parser.error(f"项目目录已存在，不覆盖：{project}。请选择其他 name 或编辑已有项目。")
    project.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL / "assets" / "project-template", project)
    (project / "tools.json").write_text(json.dumps(tools, ensure_ascii=False, indent=2), encoding="utf-8")
    lesson_path = project / "lesson.json"
    lesson = json.loads(lesson_path.read_text(encoding="utf-8-sig"))
    lesson["font"] = runtime.get("font", "Microsoft YaHei")
    lesson["voice"] = f"Kokoro v1.1-zh / {tools['narration']['voice']}"
    lesson_path.write_text(json.dumps(lesson, ensure_ascii=False, indent=2), encoding="utf-8")
    print("视频项目已创建：", project)
    print("当前模板是导数示例；新主题需要改写 lesson.json 和 scene.py。")
    print("配音后端：Kokoro 中文版 / CPU")


if __name__ == "__main__":
    main()
